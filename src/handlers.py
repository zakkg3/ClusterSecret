import logging
from typing import Dict, Any, List, Optional
import kopf
from kubernetes import client
from csHelper import delete_secret, get_ns_list, sync_secret, patch_clustersecret_status, create_secret_metadata, \
    secret_exists

# In-memory dictionary for all ClusterSecrets in the Cluster. UID -> ClusterSecret Body
csecs: Dict[str, Any] = {}
v1 = client.CoreV1Api()
custom_objects_api = client.CustomObjectsApi()


@kopf.on.delete(
    group='clustersecret.io',
    version='v1',
    kind='clustersecrets'
)
def on_delete(
        body: Dict[str, Any],
        uid: str,
        name: str,
        logger: logging.Logger,
        **_
):
    syncedns = body.get('status', {}).get('create_fn', {}).get('syncedns', [])
    for ns in syncedns:
        logger.info(f'deleting secret {name} from namespace {ns}')
        delete_secret(logger, ns, name, v1)

    # Delete from memory to prevent syncing with new namespaces
    try:
        csecs.pop(uid)
        logger.debug(f"csec {uid} deleted from memory ok")
    except KeyError as k:
        logger.info(f" This csec were not found in memory, maybe it was created in another run: {k}")


@kopf.on.field(
    group='clustersecret.io',
    version='v1',
    kind='clustersecrets',
    field='matchNamespace'
)
def on_field_match_namespace(
        old: Optional[List[str]],
        new: List[str],
        name: str,
        namespace: str,
        body,
        uid: str,
        logger: logging.Logger,
        **_
):
    logger.debug(f'Namespaces changed: {old} -> {new}')

    if old is not None:
        logger.debug(f'Updating Object body == {body}')

        try:
            syncedns = body['status']['create_fn']['syncedns']
        except KeyError:
            logger.error('No Synced or status Namespaces found')
            syncedns = []

        updated_matched = get_ns_list(logger, body, v1)
        to_add = set(updated_matched).difference(set(syncedns))
        to_remove = set(syncedns).difference(set(updated_matched))

        logger.debug(f'Add secret to namespaces: {to_add}, remove from: {to_remove}')

        for secret_namespace in to_add:
            sync_secret(logger, secret_namespace, body, v1)
        for secret_namespace in to_remove:
            delete_secret(logger, secret_namespace, name, v1=v1)

        # Store status in memory
        csecs[uid] = {
            'body': body,
            'syncedns': updated_matched
        }

        # Patch synced_ns field
        logger.debug(f'Patching clustersecret {name} in namespace {namespace}')
        patch_clustersecret_status(
            logger=logger,
            namespace=namespace,
            name=name,
            new_status={'create_fn': {'syncedns': updated_matched}},
            custom_objects_api=custom_objects_api
        )
    else:
        logger.debug('This is a new object')


@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='data')
def on_field_data(
        old: Dict[str, str],
        new: Dict[str, str],
        body: Dict[str, Any],
        name: str,
        logger: logging.Logger,
        **_
):
    logger.debug(f'Data changed: {old} -> {new}')
    if old is None:
        logger.debug('This is a new object')
        return

    logger.debug(f'Updating Object body == {body}')
    syncedns = body.get('status', {}).get('create_fn', {}).get('syncedns', [])

    secret_type = body.get('type', default='Opaque')

    for ns in syncedns:
        logger.info(f'Re Syncing secret {name} in ns {ns}')
        body = client.V1Secret(
            api_version='v1',
            data=new,
            kind='Secret',
            metadata=create_secret_metadata(name=name, namespace=ns),
            type=secret_type
        )
        # Ensuring the secret still exist.
        if secret_exists(logger=logger, name=name, namespace=ns, v1=v1):
            response = v1.replace_namespaced_secret(name=name, namespace=ns, body=body)
        else:
            response = v1.create_namespaced_secret(namespace=ns, body=body)
        logger.debug(response)


@kopf.on.resume('clustersecret.io', 'v1', 'clustersecrets')
@kopf.on.create('clustersecret.io', 'v1', 'clustersecrets')
async def create_fn(uid: str, logger: logging.Logger, body: Dict[str, Any], **_):
    # warning this is debug!
    logger.debug(
        """
      #########################################################################
      # DEBUG MODE ON - NOT FOR PRODUCTION                                    #
      # On this mode secrets are leaked to stdout, this is not safe!. NO-GO ! #
      #########################################################################
    """
    )

    # get all ns matching.
    matchedns = get_ns_list(logger, body, v1)

    # sync in all matched NS
    logger.info(f'Syncing on Namespaces: {matchedns}')
    for namespace in matchedns:
        sync_secret(logger, namespace, body, v1)

    # store status in memory
    csecs[uid] = {
        'body': body,
        'syncedns': matchedns
    }

    return {'syncedns': matchedns}


@kopf.on.create('', 'v1', 'namespaces')
async def namespace_watcher(logger: logging.Logger, meta: kopf.Meta, **_):
    """Watch for namespace events
    """
    new_ns = meta.name
    logger.debug(f"New namespace created: {new_ns} re-syncing")
    v1 = client.CoreV1Api()
    ns_new_list = []
    for key, cluster_secret in csecs.items():
        obj_body = cluster_secret['body']

        matcheddns = cluster_secret['syncedns']
        logger.debug(f"Old matched namespace: {matcheddns} - name: {cluster_secret['body']['metadata']['name']}")
        ns_new_list = get_ns_list(logger, obj_body, v1)
        logger.debug(f"new matched list: {ns_new_list}")
        if new_ns in ns_new_list:
            logger.debug(f"Cloning secret {cluster_secret['body']['metadata']['name']} into the new namespace {new_ns}")
            sync_secret(
                logger=logger,
                namespace=new_ns,
                body=cluster_secret['body'],
                v1=v1
            )
            # if there is a new matching ns, refresh memory
            csecs[key]['syncedns'] = ns_new_list

    # update ns_new_list on the object so then we also delete from there
    return {'syncedns': ns_new_list}
