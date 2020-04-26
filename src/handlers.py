import kopf
import re
import yaml
from kubernetes import client, watch, config

@kopf.on.create('clustersecret.io', 'v1', 'clustersecret')
def create_fn(spec,logger=None,body=None,**kwargs):
    logger.debug (spec)
    
    try:
        nss = body.get('matchNamespace')
    except KeyError:
        nss = '*'
        logger.debug("matching all namespaces.")
    logger.debug(f'nss: {nss}')
    try:
        avoid = body.get('avoidNamespaces')
    except KeyError:
        avoid = ''
        logger.debug("not avoiding namespaces")
    
    sync_secret(name,matchNamespace,avoidNamespaces)
    return True




def sync_secret(name,matchNamespace,avoidNamespaces):
    # config.load_kube_config()
    v1 = client.CoreV1Api()
    nss = v1.list_namespace()
    
    for ns in nss.items():
        print (ns.metadata.name)   
    
