import kopf
from kubernetes import client, config
from csHelper import *

csecs = {} # all cluster secrets.

@kopf.on.delete('clustersecret.io', 'v1', 'clustersecrets')
def on_delete(spec,uid,body,name,logger=None, **_):
    try:
        syncedns = body['status']['create_fn']['syncedns']
    except KeyError:
        syncedns=[]
    v1 = client.CoreV1Api()
    for ns in syncedns:
        logger.info(f'deleting secret {name} from namespace {ns}')
        delete_secret(logger, ns, name, v1)
        
    #delete also from memory: prevent syncing with new namespaces
    try:
        csecs.pop(uid)
        logger.debug(f"csec {uid} deleted from memory ok")
    except KeyError as k:
        logger.info(f" This csec were not found in memory, maybe it was created in another run: {k}")

@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='matchNamespace')
def on_field_match_namespace(old, new, name, namespace, body, uid, logger=None, **_):
    logger.debug(f'Namespaces changed: {old} -> {new}')

    if old is not None:
        logger.debug(f'Updating Object body == {body}')

        try:
            syncedns = body['status']['create_fn']['syncedns']
        except KeyError:
            logger.error('No Synced or status Namespaces found')
            syncedns = []

        v1 = client.CoreV1Api()
        updated_matched = get_ns_list(logger, body, v1)
        to_add = set(updated_matched).difference(set(syncedns))
        to_remove = set(syncedns).difference(set(updated_matched))

        logger.debug(f'Add secret to namespaces: {to_add}, remove from: {to_remove}')

        for secret_namespace in to_add:
            create_secret(logger, secret_namespace, body)
        for secret_namespace in to_remove:
            delete_secret(logger, secret_namespace, name)

        # Store status in memory
        csecs[uid] = {
            'body': body,
            'syncedns': updated_matched
        }

        # Patch synced_ns field
        logger.debug(f'Patching clustersecret {name} in namespace {namespace}')
        patch_clustersecret_status(logger, namespace, name, {'create_fn': {'syncedns': updated_matched}})
    else:
        logger.debug('This is a new object')


@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='data')
def on_field_data(old, new, body,name,logger=None, **_):
    logger.debug(f'Data changed: {old} -> {new}')
    if old is not None:
        logger.debug(f'Updating Object body == {body}')

        try:
            syncedns = body['status']['create_fn']['syncedns']
        except KeyError:
            logger.error('No Synced or status Namespaces found')
            syncedns=[]
            
        v1 = client.CoreV1Api()

        secret_type = 'Opaque'
        if 'type' in body:
            secret_type = body['type']

        for ns in syncedns:
            logger.info(f'Re Syncing secret {name} in ns {ns}')
            metadata = {'name': name, 'namespace': ns}
            api_version = 'v1'
            kind = 'Secret'
            data = new
            body = client.V1Secret(
                api_version=api_version,
                data=data,
                kind=kind,
                metadata=metadata,
                type=secret_type
            )
            # Ensuring the secret still exist.
            if secret_exist(logger=logger, name=name,  namespace=ns, v1=client):
                response = v1.replace_namespaced_secret(name=name, namespace=ns, body=body)
            else:
                response = v1.create_namespaced_secret(namespace=ns, body=body)
            logger.debug(response)
    else:
        logger.debug('This is a new object')

@kopf.on.resume('clustersecret.io', 'v1', 'clustersecrets')
@kopf.on.create('clustersecret.io', 'v1', 'clustersecrets')
async def create_fn(spec,uid,logger=None,body=None,**kwargs):
    v1 = client.CoreV1Api()
    
    # warning this is debug!
    logger.debug("""
      #########################################################################
      # DEBUG MODE ON - NOT FOR PRODUCTION                                    #
      # On this mode secrets are leaked to stdout, this is not safe!. NO-GO ! #
      #########################################################################
    """
    )
    
    #get all ns matching.
    matchedns = get_ns_list(logger,body,v1)
        
    #sync in all matched NS
    logger.info(f'Syncing on Namespaces: {matchedns}')
    for namespace in matchedns:
        create_secret(logger,namespace,body,v1)
    
    #store status in memory
    csecs[uid]={}
    csecs[uid]['body']=body
    csecs[uid]['syncedns']=matchedns

    return {'syncedns': matchedns}

@kopf.on.create('', 'v1', 'namespaces')
async def namespace_watcher(spec,patch,logger,meta,body,**kwargs):
    """Watch for namespace events
    """
    new_ns = meta['name']
    logger.debug(f"New namespace created: {new_ns} re-syncing")
    v1 = client.CoreV1Api()
    ns_new_list = []
    for k,v in csecs.items():
        obj_body = v['body']
        #logger.debug(f'k: {k} \n v:{v}')
        matcheddns = v['syncedns']
        logger.debug(f"Old matched namespace: {matcheddns} - name: {v['body']['metadata']['name']}")
        ns_new_list=get_ns_list(logger,obj_body,v1)
        logger.debug(f"new matched list: {ns_new_list}")
        if new_ns in ns_new_list:
            logger.debug(f"Cloning secret {v['body']['metadata']['name']} into the new namespace {new_ns}")
            create_secret(logger,new_ns,v['body'],v1)
            # if there is a new matching ns, refresh memory
            v['syncedns'] = ns_new_list
            
    # update ns_new_list on the object so then we also delete from there
    return {'syncedns': ns_new_list}
