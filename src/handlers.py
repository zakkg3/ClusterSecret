import kopf
import re
from kubernetes import client, config


@kopf.on.delete('clustersecret.io', 'v1', 'clustersecrets')
def on_delete(spec,body,name,logger=None, **_):
    syncedns = body['status']['create_fn']['syncedns']
    v1 = client.CoreV1Api()
    for ns in syncedns:
        logger.info(f'deleting secret {name} from naespace {ns}')
        v1.delete_namespaced_secret(name,ns)
        
@kopf.on.field('clustersecret.io', 'v1', 'clustersecrets', field='data')
def on_field_data(old, new, body,name,logger=None, **_):
    logger.debug('----------------')
    logger.info(f'Data changed: {old} -> {new}')
    syncedns = body['status']['create_fn']['syncedns']
    v1 = client.CoreV1Api()
    for ns in syncedns:
        logger.info(f'patching secret {name} in ns {ns}')
        metadata = {'name': name, 'namespace': ns}
        api_version = 'v1'
        kind = 'Secret'
        data = new
        body = client.V1Secret(api_version, data , kind, metadata, type='kubernetes.io/tls')
        # response = v1.patch_namespaced_secret(name,ns,body)
        response = v1.replace_namespaced_secret(name,ns,body)
        logger.debug(response)
        
    

@kopf.on.resume('clustersecret.io', 'v1', 'clustersecrets')
@kopf.on.create('clustersecret.io', 'v1', 'clustersecrets')
def create_fn(spec,logger=None,body=None,**kwargs):

    try:
        matchNamespace = body.get('matchNamespace')
    except KeyError:
        matchNamespace = '*'
        logger.debug("matching all namespaces.")
    logger.debug(f'Matching namespaces: {matchNamespace}')
    
    try:
        avoidNamespaces = body.get('avoidNamespaces')
    except KeyError:
        avoidNamespaces = ''
        logger.debug("not avoiding namespaces")
        
    try:
        name = body['metadata']['name']
        logger.debug (f"name: {name}")
    except KeyError:
        logger.debug("No name ?")
        raise kopf.TemporaryError("can not get the name.")

    try:
        data = body.get('data')
    except KeyError:
        data = ''
        logger.debug("Empty secret??")

    v1 = client.CoreV1Api()
    
    matchedns = get_ns_list(v1,logger,matchNamespace,avoidNamespaces)
    
    #sync in all matched NS
    for ns in matchedns:
        create_secret(v1,logger,ns,name,data)
    return {'syncedns': matchedns}




def get_ns_list(v1,logger,matchNamespace,avoidNamespaces):
    nss = v1.list_namespace().items
    matchedns = []
    avoidedns = []
    
    for matchns in matchNamespace:
        for ns in nss:
            if re.match(matchns, ns.metadata.name):
                matchedns.append(ns.metadata.name)
                logger.info(f'Matched namespaces: {ns.metadata.name} matchpathern: {matchns}')   
    for avoidns in avoidNamespaces:
        for ns in nss:
            if re.match(avoidns, ns.metadata.name):
                avoidedns.append(ns.metadata.name)
                logger.info(f'Skipping namespaces: {ns.metadata.name} avoidpatrn: {avoidns}')  
    # purge
    for ns in matchedns:
        if ns in avoidedns:
            matchedns.remove(ns)
    
    logger.info(f'Syncing on Namespaces: {matchedns}')
    return matchedns
    
            
def create_secret(v1,logger,namespace,name,data):
    metadata = {'name': name, 'namespace': namespace}
    api_version = 'v1'
    kind = 'Secret'
    body = client.V1Secret(api_version, data , kind, metadata, type='kubernetes.io/tls')
    # kopf.adopt(body)
    try:
        api_response = v1.create_namespaced_secret(namespace, body)
    except client.rest.ApiException as e:
        if e.reason == 'Conflict':
            logger.info(f"Conflict creating the secret: It may be already a `{name}` secret in namespace: '{namespace}'")
            return 0
        logger.error(f'Can not create a secret, it is base64 encoded? data: {data}')
        logger.error(f'Kube exception {e}')
        return 1
    return 0
                
