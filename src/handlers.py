import kopf
import re
from kubernetes import client, config


@kopf.on.delete('clustersecret.io', 'v1', 'clustersecrets')
def on_delete(spec,uid,body,name,logger=None, **_):
    try:
        syncedns = body['status']['create_fn']['syncedns']
    except KeyError:
        syncedns=[]
    v1 = client.CoreV1Api()
    for ns in syncedns:
        logger.info(f'deleting secret {name} from namespace {ns}')
        try:
            v1.delete_namespaced_secret(name,ns)
        except client.rest.ApiException as e:
            if e.status == 404:
                logger.warning(f"The namespace {ns} may not exist anymore: Not found")
            else:
                logger.warning(f" Something wierd deleting the secret: {e}")
        
    #delete also from memory: prevent syncing with new namespaces
    try:
        csecs.pop(uid)
        logger.debug(f"csec {uid} deleted from memory ok")
    except KeyError as k:
        logger.info(f" This csec were not found in memory, maybe it was created in another run: {k}")

@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='data')
def on_field_data(old, new, body,name,logger=None, **_):
    logger.debug(f'Data changed: {old} -> {new}')
    if old is not None:
        syncedns = body['status']['create_fn']['syncedns']
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
                data=data ,
                kind=kind,
                metadata=metadata,
                type = secret_type
            )
            response = v1.replace_namespaced_secret(name,ns,body)
            logger.debug(response)
    else:
        logger.debug('This is a new object')

csecs = {} # all cluster secrets.

@kopf.on.resume('clustersecret.io', 'v1', 'clustersecrets')
@kopf.on.create('clustersecret.io', 'v1', 'clustersecrets')
async def create_fn(spec,uid,logger=None,body=None,**kwargs):
    v1 = client.CoreV1Api()
    
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

def get_ns_list(logger,body,v1=None):
    """Returns a list of namespaces where the secret should be matched
    """
    if v1 is None:
        v1 = client.CoreV1Api()
        logger.debug('new client - fn get_ns_list')
    
    try:
        matchNamespace = body.get('matchNamespace')
    except KeyError:
        matchNamespace = '*'
        logger.debug("matching all namespaces.")
    logger.debug(f'Matching namespaces: {matchNamespace}')
    
    if matchNamespace is None:  # if delted key (issue 26)
        matchNamespace = '*'
    
    try:
        avoidNamespaces = body.get('avoidNamespaces')
    except KeyError:
        avoidNamespaces = ''
        logger.debug("not avoiding namespaces")

    nss = v1.list_namespace().items
    matchedns = []
    avoidedns = []

    for matchns in matchNamespace:
        for ns in nss:
            if re.match(matchns, ns.metadata.name):
                matchedns.append(ns.metadata.name)
                logger.debug(f'Matched namespaces: {ns.metadata.name} matchpathern: {matchns}')
    if avoidNamespaces:
        for avoidns in avoidNamespaces:
            for ns in nss:
                if re.match(avoidns, ns.metadata.name):
                    avoidedns.append(ns.metadata.name)
                    logger.debug(f'Skipping namespaces: {ns.metadata.name} avoidpatrn: {avoidns}')  
    # purge
    for ns in matchedns.copy():
        if ns in avoidedns:
            matchedns.remove(ns)

    return matchedns
    
            
def create_secret(logger,namespace,body,v1=None):
    """Creates a given secret on a given namespace
    """
    if v1 is None:
        v1 = client.CoreV1Api()
        logger.debug('new client - fn create secret')
    try:
        sec_name = body['metadata']['name']
    except KeyError:
        logger.debug("No name in body ?")
        raise kopf.TemporaryError("can not get the name.")
    try:
        data = body.get('data')
    except KeyError:
        data = ''
        logger.error("Empty secret?? could not get the data.")
    
    if 'valueFrom' in data:
        if len(data.keys()) > 1:
            raise kopf.TemporaryError("ValueFrom can not coexist with other keys in the data")
            
        try:
            ns_from = data['ValueFrom']['namespace']
            name_from = data['ValueFrom']['name']
        except KeyError:
            logger.error("Can not get Values from external secret")
            # to-do keys_from
        logger.debug(f'Take value from secret {name_from} from namespace {ns_from}')
        # data = read_data_secret(name,namespace)
        #here - doing the valuform thing. but first fix and update all.
        
    secret_type = 'Opaque'
    if 'type' in body:
        secret_type = body['type']
    body  = client.V1Secret()
    body.metadata = client.V1ObjectMeta(name=sec_name)
    body.type = secret_type
    body.data = data
    # kopf.adopt(body)
    logger.info(f"cloning secret in namespace {namespace}")
    try:
        api_response = v1.create_namespaced_secret(namespace, body)
    except client.rest.ApiException as e:
        if e.reason == 'Conflict':
            logger.warning(f"secret `{sec_name}` already exist in namesace '{namespace}'")
            return 0
        logger.error(f'Can not create a secret, it is base64 encoded? data: {data}')
        logger.error(f'Kube exception {e}')
        return 1
    return 0

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
