import logging
import sys
from typing import Any, Dict, List, Optional

import kopf
from kubernetes import client, config

from cache import Cache, MemoryCache
from kubernetes_utils import delete_secret, get_ns_list, sync_secret, patch_clustersecret_status, get_custom_objects_by_kind
from models import BaseClusterSecret

# In-memory dictionary for all ClusterSecrets in the Cluster. UID -> ClusterSecret Body
csecs_cache: Cache = MemoryCache()

from os_utils import in_cluster

if "unittest" not in sys.modules:
    # Loading kubeconfig
    if in_cluster():
        # Loading kubeconfig
        config.load_incluster_config()
    else:
        # Loading using the local kubevonfig.
        config.load_kube_config()

v1 = client.CoreV1Api()
custom_objects_api = client.CustomObjectsApi()


@kopf.on.delete('clustersecret.io', 'v1', 'clustersecrets')
def on_delete(
    body: Dict[str, Any],
    uid: str,
    name: str,
    logger: logging.Logger,
    **_,
):
    syncedns = body.get('status', {}).get('create_fn', {}).get('syncedns', [])
    for ns in syncedns:
        logger.info(f'deleting secret {name} from namespace {ns}')
        delete_secret(logger, ns, name, v1)

    # Delete from memory to prevent syncing with new namespaces
    try:
        csecs_cache.remove_cluster_secret(uid)
    except KeyError as k:
        logger.info(f'This csec were not found in memory, maybe it was created in another run: {k}')
        return
    logger.debug(f'csec {uid} deleted from memory ok')


@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='avoidNamespaces')
@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='matchNamespace')
def on_fields_avoid_or_match_namespace(
    old: Optional[List[str]],
    new: List[str],
    name: str,
    body,
    uid: str,
    logger: logging.Logger,
    reason: kopf.Reason,
    **_,
):
    if reason == "create":
        logger.debug('This is a new object: Ignoring.')
        return

    logger.debug(f'Avoid or match namespaces changed: {old} -> {new}')
    logger.debug(f'Updating Object body == {body}')

    syncedns = body.get('status', {}).get('create_fn', {}).get('syncedns', [])

    updated_matched = get_ns_list(logger, body, v1)
    to_add = set(updated_matched).difference(set(syncedns))
    to_remove = set(syncedns).difference(set(updated_matched))

    logger.debug(f'Add secret to namespaces: {to_add}, remove from: {to_remove}')

    for secret_namespace in to_add:
        sync_secret(logger, secret_namespace, body, v1)

    for secret_namespace in to_remove:
        delete_secret(logger, secret_namespace, name, v1)

    cached_cluster_secret = csecs_cache.get_cluster_secret(uid)
    if cached_cluster_secret is None:
        logger.error('Received an event for an unknown ClusterSecret.')

    # Updating the cache
    csecs_cache.set_cluster_secret(BaseClusterSecret(
        uid=uid,
        name=name,
        body=body,
        synced_namespace=updated_matched,
    ))

    # Patch synced_ns field
    logger.debug(f'Patching clustersecret {name}')
    patch_clustersecret_status(
        logger=logger,
        name=name,
        new_status={'create_fn': {'syncedns': updated_matched}},
        custom_objects_api=custom_objects_api,
    )


@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='data')
def on_field_data(
    old: Dict[str, str],
    new: Dict[str, str],
    body: Dict[str, Any],
    name: str,
    uid: str,
    logger: logging.Logger,
    reason: kopf.Reason,
    **_,
):
    if reason == "create":
        logger.debug('This is a new object: Ignoring')
        return

    logger.debug(f'Data changed: {old} -> {new}')
    logger.debug(f'Updating Object body == {body}')
    syncedns = body.get('status', {}).get('create_fn', {}).get('syncedns', [])

    cached_cluster_secret = csecs_cache.get_cluster_secret(uid)
    if cached_cluster_secret is None:
        logger.error('Received an event for an unknown ClusterSecret.')

    for ns in syncedns:
        logger.info(f'Re Syncing secret {name} in ns {ns}')
        sync_secret(logger, ns, body, v1)

    # Updating the cache
    csecs_cache.set_cluster_secret(BaseClusterSecret(
        uid=uid,
        name=name,
        body=body,
        synced_namespace=syncedns,
    ))


@kopf.on.resume('clustersecret.io', 'v1', 'clustersecrets')
@kopf.on.create('clustersecret.io', 'v1', 'clustersecrets')
async def create_fn(
    logger: logging.Logger,
    uid: str,
    name: str,
    body: Dict[str, Any],
    **_
):
    # get all ns matching.
    matchedns = get_ns_list(logger, body, v1)

    # sync in all matched NS
    logger.info(f'Syncing on Namespaces: {matchedns}')
    for ns in matchedns:
        sync_secret(logger, ns, body, v1)

    # Updating the cache
    csecs_cache.set_cluster_secret(BaseClusterSecret(
        uid=uid,
        name=name,
        body=body,
        synced_namespace=matchedns,
    ))

    # return for what ??? Should be deleted ??
    return {'syncedns': matchedns}


@kopf.on.create('', 'v1', 'namespaces')
@kopf.on.delete('', 'v1', 'namespaces')
async def namespace_watcher(logger: logging.Logger, reason: kopf.Reason, meta: kopf.Meta, **_):
    """Watch for namespace events
    """
    if reason not in ["create", "delete"]:
        logger.error(f'Function "namespace_watcher" was called with incorrect reason: {reason}')
        return
    
    ns_name = meta.name
    logger.info(f'Namespace {"created" if reason == "create" else "deleted"}: {ns_name}. Re-syncing')
    
    ns_list_new = []
    for cached_cluster_secret in csecs_cache.all_cluster_secret():
        body = cached_cluster_secret.body
        name = cached_cluster_secret.name
        ns_list_synced = cached_cluster_secret.synced_namespace
        ns_list_new = get_ns_list(logger, body, v1)
        ns_list_changed = False

        logger.debug(f'ClusterSecret: {name}. Old matched namespaces: {ns_list_synced}')
        logger.debug(f'ClusterSecret: {name}. New matched namespaces: {ns_list_new}')
        
        if reason == "create" and ns_name in ns_list_new:
            logger.info(f'Cloning secret {name} into the new namespace: {ns_name}')
            sync_secret(
                logger=logger,
                namespace=ns_name,
                body=body,
                v1=v1,
            )
            ns_list_changed = True
        
        if reason == "delete" and ns_name in ns_list_synced:
            logger.info(f'Secret {name} removed from deleted namespace: {ns_name}')
            # Ensure that deleted namespace will not come in new list - on moment when this event handled by kopf the namespace in kubernetes can still exists
            if ns_name in ns_list_new:
                ns_list_new.remove(ns_name)
            ns_list_changed = True

        # Update ClusterSecret only if there are changes in list of his namespaces
        if ns_list_changed:
            # Update in-memory cache
            cached_cluster_secret.synced_namespace = ns_list_new
            csecs_cache.set_cluster_secret(cached_cluster_secret)

            # Update the list of synced namespaces in kubernetes object
            logger.debug(f'Patching ClusterSecret: {name}')
            patch_clustersecret_status(
                logger=logger,
                name=name,
                new_status={'create_fn': {'syncedns': ns_list_new}},
                custom_objects_api=custom_objects_api,
            )
        else:
            logger.debug(f'There are no changes in the list of namespaces for ClusterSecret: {name}')


@kopf.on.startup()
async def startup_fn(logger: logging.Logger, **_):
    logger.debug(
        """
      #########################################################################
      # DEBUG MODE ON - NOT FOR PRODUCTION                                    #
      # On this mode secrets are leaked to stdout, this is not safe!. NO-GO ! #
      #########################################################################
    """,
    )

    cluster_secrets = get_custom_objects_by_kind(
        group='clustersecret.io',
        version='v1',
        plural='clustersecrets',
        custom_objects_api=custom_objects_api,
    )

    logger.info(f'Found {len(cluster_secrets)} existing cluster secrets.')
    for item in cluster_secrets:
        metadata = item.get('metadata')
        csecs_cache.set_cluster_secret(
            BaseClusterSecret(
                uid=metadata.get('uid'),
                name=metadata.get('name'),
                body=item,
                synced_namespace=item.get('status', {}).get('create_fn', {}).get('syncedns', []),
            )
        )
