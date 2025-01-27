import logging
import sys
from typing import Any, Dict, List, Optional

import kopf
from kubernetes import client, config

from cache import Cache, MemoryCache
from kubernetes_utils import delete_secret, get_ns_list, sync_secret, sync_clustersecret, patch_clustersecret_status, \
    create_secret_metadata, secret_exists, secret_belongs, get_custom_objects_by_kind
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
    # Delete from memory to prevent syncing with new namespaces
    try:
        csecs_cache.remove_cluster_secret(uid)
    except KeyError as k:
        logger.info(f'This csec was not found in memory, maybe it was created in another run: {k}')
        return
    logger.debug(f'csec {uid} deleted from memory ok')


@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='matchNamespace')
@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='avoidNamespaces')
@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='matchLabels')
@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='matchedSetsJoin')
def on_match_fields(
    old: Optional[List[str]],
    new: List[str],
    name: str,
    body,
    uid: str,
    logger: logging.Logger,
    **_,
):
    if old is None:
        logger.debug('This is a new object: Ignoring.')
        return

    logger.debug(f'Updating Object body == {body}')

    syncedns = body.get('status', {}).get('syncedns', [])

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
        new_status={'syncedns': updated_matched},
        custom_objects_api=custom_objects_api,
    )


@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='data')
@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='fromSecret')
def on_field_data(
    old: Dict[str, str],
    new: Dict[str, str],
    body: Dict[str, Any],
    uid,
    logger: logging.Logger,
    **_,
):
    logger.debug(f'Data changed: {old} -> {new}')
    if old is None:
        logger.debug('This is a new object: Ignoring')
        return

    cached_cluster_secret = csecs_cache.get_cluster_secret(uid)
    if cached_cluster_secret is None:
        logger.error('Received an event for an unknown ClusterSecret.')

    sync_clustersecret(logger, body, csecs_cache, v1, custom_objects_api)


@kopf.on.create('clustersecret.io', 'v1', 'clustersecrets')
async def create_fn(
    logger: logging.Logger,
    body: Dict[str, Any],
    **_
):
    sync_clustersecret(logger, body, csecs_cache, v1, custom_objects_api)


@kopf.on.event('', 'v1', 'namespaces')
def on_namespace_event(
    logger: logging.Logger,
    event,
    **_
):
    """Watch for namespace events
    """
    event_type = event.get('type', None)

    # Ignore events without type (sent on operator startup)
    if event_type == None: return

    meta = event.get('object',{}).get('metadata',{})
    ns = meta.get('name')
    is_delete = event_type == 'DELETED' or 'deletionTimestamp' in meta
    logger.debug(f'Namespace event: {ns} re-syncing')
    for cluster_secret in csecs_cache.all_cluster_secret():
        obj_body = cluster_secret.body
        name = cluster_secret.name

        matchedns = cluster_secret.synced_namespace

        logger.debug(f'Old matched namespace: {matchedns} - name: {name}')
        is_match = False if is_delete else secret_belongs(logger, obj_body, ns, meta.get('labels',{}))
        if is_match and not ns in matchedns:
            logger.debug(f'Cloning secret {name} into namespace {ns}')
            matchedns.append(ns)
            sync_secret(
                logger=logger,
                namespace=ns,
                body=obj_body,
                v1=v1,
            )

        elif not is_match and ns in matchedns:
            matchedns.remove(ns)
            if is_delete:
                logger.debug(f'Forgetting deleted namespace {ns}, matched by clustersecret {name}')
            else:
                delete_secret(logger, ns, name, v1)

        else:
            # Return without updating cache when nothing happened
            return

        cluster_secret.synced_namespace = matchedns
        csecs_cache.set_cluster_secret(cluster_secret)

        patch_clustersecret_status(
            logger=logger,
            name=cluster_secret.name,
            new_status={'syncedns': matchedns},
            custom_objects_api=custom_objects_api,
        )


@kopf.on.event('', 'v1', 'secrets')
def on_secret_event(
    logger: logging.Logger,
    event,
    **_,
):
    # Ignore events without type (sent on operator startup)
    if event.get('type') == None: return

    meta = event.get('object',{}).get('metadata',{})
    ns_name = meta.get('namespace')
    sec_name = meta.get('name')

    # If secret is managed by a clustersecret
    sec_owners = [owner for owner in meta.get('ownerReferences',[]) if owner.get('kind') == 'ClusterSecret']
    for owner in sec_owners:
        cluster_secret = csecs_cache.get_cluster_secret(owner.get('uid'))
        sec_ns = v1.read_namespace(ns_name)
        if (cluster_secret and
            not sec_ns.metadata.deletion_timestamp and
            secret_belongs(logger, cluster_secret.body, ns_name, sec_ns.metadata.labels)
        ):
            sync_secret(
                logger=logger,
                namespace=ns_name,
                body=cluster_secret.body,
                v1=v1,
            )

    # If secret is the data source for a clustersecret
    for cluster_secret in csecs_cache.all_cluster_secret():
        csec_from_secret = cluster_secret.body.get('fromSecret')
        if (csec_from_secret and
            csec_from_secret.get('name') == sec_name and
            csec_from_secret.get('namespace') == ns_name
        ):
            logger.info(f'Event on source secret for clustersecret {cluster_secret.name}')
            sync_clustersecret(logger, cluster_secret.body, csecs_cache, v1, custom_objects_api)


@kopf.on.startup()
async def startup_fn(
    logger: logging.Logger,
    settings: kopf.OperatorSettings,
    **_
):
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

    for cluster_secret in cluster_secrets:
        sync_clustersecret(logger, cluster_secret, csecs_cache, v1, custom_objects_api)
