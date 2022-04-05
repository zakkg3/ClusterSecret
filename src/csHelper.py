import kopf
import re
from kubernetes import client

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

def read_data_secret(logger,name,namespace,v1):
    """Gets the data from the 'name' secret in namspace
    """
    data={}
    logger.debug(f'Reading {name} from ns {namespace}')
    try: 
        secret = v1.read_namespaced_secret(name, namespace)
        logger.debug(f'Obtained secret {secret}')
        data = secret.data
    except client.exceptions.ApiException as e:
        logger.error(f'Error reading secret {e}')
        if e == "404":
            logger.error(f"Secret {name} in ns {namespace} not found!")
        raise kopf.TemporaryError("Error reading secret")
    return data
    
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
            logger.error(f'Data keys with ValueFrom error: {data.keys()}  len {len(data.keys())}')
            raise kopf.TemporaryError("ValueFrom can not coexist with other keys in the data")
            
        try:
            ns_from = data['valueFrom']['secretKeyRef']['namespace']
            name_from = data['valueFrom']['secretKeyRef']['name']
            # key_from = data['ValueFrom']['secretKeyRef']['name']
            # to-do specifie keys. for now. it will clone all.
            logger.debug(f'Taking value from secret {name_from} from namespace {ns_from} - All keys')
            data = read_data_secret(logger,name_from,ns_from,v1)
        except KeyError:
            logger.error (f'ERROR reading data from remote secret = {data}')
            raise kopf.TemporaryError("Can not get Values from external secret")

    logger.debug(f'Going to create with data: {data}')
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
            logger.info(f"secret `{sec_name}` already exist in namesace '{namespace}'")
            return 0
        logger.error(f'Can not create a secret, it is base64 encoded? data: {data}')
        logger.error(f'Kube exception {e}')
        return 1
    return 0
