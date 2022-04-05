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
