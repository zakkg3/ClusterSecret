import kopf
import re
import yaml
from kubernetes import client, watch, config

@kopf.on.create('clustersecret.io', 'v1', 'clustersecrets')
def create_fn(spec,logger=None,body=None,**kwargs):
    logger.debug (f'spec: {spec}')
    logger.debug ('----------')
    logger.debug (f'body: {body}')
    logger.debug ('###################2')
    logger.debug (f"name: {body['metadata']['name']}")
    
    try:
        matchNamespace = body.get('matchNamespace')
    except KeyError:
        matchNamespace = '*'
        logger.debug("matching all namespaces.")
    logger.debug(f'nss: {matchNamespace}')
    try:
        avoidNamespaces = body.get('avoidNamespaces')
    except KeyError:
        avoidNamespaces = ''
        logger.debug("not avoiding namespaces")
    try:
        name = body['metadata']['name']
    except KeyError:
        logger.debug("No name ?")
        return 1 #raise something here
        
    sync_secret(name,matchNamespace,avoidNamespaces)
    return True




def sync_secret(name,matchNamespace,avoidNamespaces):
    # config.load_kube_config()
    v1 = client.CoreV1Api()
    nss = v1.list_namespace().items
    
    for ns in nss:
        print (ns.metadata.name)
