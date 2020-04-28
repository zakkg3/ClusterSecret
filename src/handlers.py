import kopf
import re
# import yaml
from kubernetes import client, watch, config

@kopf.on.create('clustersecret.io', 'v1', 'clustersecrets')
def create_fn(spec,logger=None,body=None,**kwargs):
    # logger.debug (f'spec: {spec}')
    # logger.debug ('----------')
    # logger.debug (f'body: {body}')
    # logger.debug ('###################')
    # logger.debug (f"name: {body['metadata']['name']}")
    
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
        return 1 #raise something here

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
    return True




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
    
    logger.info(f'Syncing with Namespaces: {matchedns}')
    return matchedns
    
            
def create_secret(v1,logger,namespace,name,data):
    metadata = {'name': name, 'namespace': namespace}
    # data=  {'tls.crt': '###BASE64 encoded crt###', 'tls.key': '###BASE64 encoded Key###'}
    api_version = 'v1'
    kind = 'Secret'
    body = client.V1Secret(api_version, data , kind, metadata, type='kubernetes.io/tls')
    try:
        api_response = v1.create_namespaced_secret(namespace, body)
    except client.rest.ApiException as e:
        logger.error(f'Can not create a secret, it is base64 encoded? data: {data}')
        return 1
    
    # logger.debug(f"Api response: {api_response}")
    return 0
                
