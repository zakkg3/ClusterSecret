import kopf
# import kubernetes.client
import re
import yaml
# import hpc_redmine
# import redminer
# import os


@kopf.on.create('clustersecret.io', 'v1', 'clustersecret')
def create_fn(spec,logger=None,body=None,**kwargs):
    # logger.debug("========= printing kwargs ========")
    # logger.debug(kwargs)
    # logger.debug("========= printing body =========")
    # logger.debug(body)

    #logger.debug("========= issues_config =========")
    # del issues_config[project]  DELETEd from obj.
    # del issues_config[]
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
        avoid = '*'
        logger.debug("matching all namespaces.")

    return True
