import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Mapping, Tuple, Iterator
from cache import Cache
import re

import kopf
from kubernetes.client import CoreV1Api, CustomObjectsApi, exceptions, V1ObjectMeta, V1OwnerReference, rest, V1Secret

from models import BaseClusterSecret
from os_utils import get_replace_existing, get_version
from consts import VERSION_ANNOTATION, BLACK_LISTED_ANNOTATIONS, BLACK_LISTED_LABELS, CLUSTER_SECRET_LABEL


def patch_clustersecret_status(
        logger: logging.Logger,
        name: str,
        new_status,
        custom_objects_api: CustomObjectsApi,
):
    """Patch the status of a given clustersecret object
    """
    group = 'clustersecret.io'
    version = 'v1'
    plural = 'clustersecrets'

    # Retrieve the clustersecret object
    clustersecret = custom_objects_api.get_cluster_custom_object(
        group=group,
        version=version,
        plural=plural,
        name=name,
    )

    # Update the status field
    clustersecret['status'] = new_status
    logger.debug(f'Updated clustersecret manifest: {clustersecret}')

    # Perform a patch operation to update the custom resource
    return custom_objects_api.patch_cluster_custom_object(
        group=group,
        version=version,
        plural=plural,
        name=name,
        body=clustersecret,
    )


def get_ns_list(
        logger: logging.Logger,
        body: Dict[str, Any],
        v1: CoreV1Api,
) -> List[str]:
    """Returns a list of namespaces where the secret should be matched
    """
    # Get matchLabels or default to empty dict
    match_labels = body.get('matchLabels', {})

    # Get matchedSetsJoin or default to "union"
    matched_sets_join = body.get('matchedSetsJoin', 'union')

    # Get matchNamespace or set default based on match_labels and join strategy
    match_namespace = body.get('matchNamespace', [] if (match_labels and matched_sets_join == 'union') else ['.*'])

    # Get avoidNamespaces or default to empty list
    avoid_namespaces = body.get('avoidNamespaces', [])

    # Collect all namespace names and labels
    ns_with_labels = {ns.metadata.name:ns.metadata.labels for ns in v1.list_namespace().items}
    nss = ns_with_labels.keys()
    matched_ns = []
    avoided_ns = []

    # Iterate over all matchNamespace
    for match_ns in match_namespace:
        matched_ns.extend([ns for ns in nss if re.match(match_ns, ns)])
        logger.debug(f'Matched namespaces: [{", ".join(matched_ns)}] match pattern: {match_ns}')

    # Iterate over all matchLabels
    for label_key,label_value in match_labels.items():
      label_ns = [ns for ns,labels in ns_with_labels.items() if
                   label_key in labels and
                   labels[label_key] == label_value]
      logger.debug(f'Matched namespaces: [{", ".join(label_ns)}] match label: {label_key}: {label_value}')

      if matched_sets_join == 'intersection':
        matched_ns = list(set(matched_ns).intersection(set(label_ns)))
        logger.debug(f'Intersection: [{", ".join(matched_ns)}]')
        if matched_ns == []:
          return []
      else:
        matched_ns.extend(label_ns)
        logger.debug(f'Union: [{", ".join(matched_ns)}]')
    
    for avoid_ns in avoid_namespaces:
        avoided_ns.extend([ns for ns in nss if re.match(avoid_ns, ns)])
        logger.debug(f'Skipping namespaces: {", ".join(avoided_ns)} avoid pattern: {avoid_ns}')

    return list(set(matched_ns) - set(avoided_ns))


def delete_secret(
        logger: logging.Logger,
        namespace: str,
        name: str,
        v1: CoreV1Api,
):
    """Deletes a given secret from a given namespace
    """
    logger.info(f'deleting secret {name} from namespace {namespace}')
    try:
        v1.delete_namespaced_secret(name, namespace)
    except rest.ApiException as e:
        if e.status == 404:
            logger.warning(f'The namespace {namespace} may not exist anymore: Not found')
        else:
            logger.warning('Something weird deleting the secret')
            logger.debug(f'details: {e}')


def secret_exists(
        logger: logging.Logger,
        name: str,
        namespace: str,
        v1: CoreV1Api,
):
    return secret_metadata(
        logger=logger,
        name=name,
        namespace=namespace,
        v1=v1,
    ) is not None


def secret_belongs(
        logger: logging.Logger,
        csec_body: Dict[str, Any],
        ns_name: str,
        ns_labels: Dict[str, str],
):
    # Get avoidNamespaces or default to empty list
    avoid_namespaces = csec_body.get('avoidNamespaces', [])

    for avoid_ns in avoid_namespaces:
        if re.match(avoid_ns, ns_name):
            return False

    # Get matchLabels or default to empty dict
    match_labels = csec_body.get('matchLabels', {})

    # Get matchedSetsJoin or default to "union"
    matched_sets_join = csec_body.get('matchedSetsJoin', 'union')

    # Get matchNamespace or set default based on match_labels and join strategy
    match_namespace = csec_body.get('matchNamespace', [] if (match_labels and matched_sets_join == 'union') else ['.*'])

    is_match = False
    for match_ns in match_namespace:
        if re.match(match_ns, ns_name):
            is_match = True
            break

    if matched_sets_join == 'intersection' and is_match:
        for label_key,label_value in match_labels.items():
            if not (label_key in ns_labels and ns_labels[label_key] == label_value):
                is_match = False
                break
    elif matched_sets_join == 'union' and not is_match:
        for label_key,label_value in match_labels.items():
            if label_key in ns_labels and ns_labels[label_key] == label_value:
                is_match = True
                break

    return is_match


def sync_clustersecret(
        logger: logging.Logger,
        body: Dict[str, Any],
        csecs_cache: Cache,
        v1: CoreV1Api,
        custom_objects_api: CustomObjectsApi,
):
    meta = body.get('metadata',{})
    name = meta.get('name')

    # get all ns matching.
    matchedns = get_ns_list(logger, body, v1)

    # sync in all matched NS
    logger.info(f'Syncing on Namespaces: {matchedns}')
    for ns in matchedns:
        sync_secret(logger, ns, body, v1)

    # Updating the cache
    csecs_cache.set_cluster_secret(BaseClusterSecret(
        uid=meta.get('uid'),
        name=name,
        body=body,
        synced_namespace=matchedns,
    ))

    # Patch synced_ns field
    logger.debug(f'Patching clustersecret {name}')
    patch_clustersecret_status(
        logger=logger,
        name=name,
        new_status={'syncedns': matchedns},
        custom_objects_api=custom_objects_api,
    )


def sync_secret(
        logger: logging.Logger,
        namespace: str,
        body: Dict[str, Any],
        v1: CoreV1Api,
):
    """Creates a given secret on a given namespace
    """
    cs_metadata: Dict[str, Any] = body.get('metadata')
    sec_name = cs_metadata.get('name')
    annotations = cs_metadata.get('annotations', None)
    labels = cs_metadata.get('labels', None)

    if 'data' in body:
        data = body.get('data')
    elif 'fromSecret' in body:
        secret_key_ref: Dict[str, Any] = body.get('fromSecret', {})
        from_ns: str = secret_key_ref.get('namespace')
        from_name: str = secret_key_ref.get('name')
        keys: Optional[List[str]] = secret_key_ref.get('keys')

        # Filter the keys in data based on the keys list provided
        try:
            from_secret = v1.read_namespaced_secret(from_name, from_ns)
            logger.debug(f'Obtained secret {from_secret}')
            raw_data = from_secret.data
        except exceptions.ApiException as e:
            logger.error(f'Cannot read source secret {from_name} in namespace {from_ns}. enable debug for details')
            logger.debug(f'Kube exception {e}')
            return
        if keys is not None:
            data = {key: value for key, value in raw_data.items() if key in keys}
        else:
            data = raw_data

    else:
        return

    logger.debug(f'Going to create with data: {data}')
    sec_type = body.get('type', 'Opaque')

    sec_body = V1Secret()
    sec_body.metadata = create_secret_metadata(
        name=sec_name,
        namespace=namespace,
        csec_body=body,
        annotations=annotations,
        labels=labels,
    )
    sec_body.type = sec_type
    sec_body.data = data
    logger.info(f'syncing secret {sec_name} in namespace {namespace}')
    logger.debug(f'V1Secret= {sec_body}')

    try:
        # Get secret
        try:
            secret = v1.read_namespaced_secret(sec_name, namespace)
        except exceptions.ApiException as e:
            if e.status == 404:
                secret = None
            else:
                logger.error(f'Cannot read secret {sec_name} in namespace {namespace}. enable debug for details')
                logger.debug(f'Kube exception {e}')
                return

        # If nothing returned, the secret does not exist, creating it then
        if secret is None:
            logger.info('Using create_namespaced_secret')
            logger.debug(f'response is {v1.create_namespaced_secret(namespace, sec_body)}')
            return

        metadata = secret.metadata
        if not metadata.owner_references or metadata.owner_references[0].kind != 'ClusterSecret':
            logger.warning(
                f"secret `{sec_name}` already exist in namespace '{namespace}' and is not managed by ClusterSecret",
            )

            if not get_replace_existing():
                logger.info(
                    f'secret `{sec_name}` will not be replaced. '
                    'You can enforce this by setting env REPLACE_EXISTING to true.',
                )
                return

        if (secret.data != sec_body.data or
            not secret.metadata.labels.items() >= sec_body.metadata.labels.items() or
            not secret.metadata.annotations.items() >= sec_body.metadata.annotations.items() or
            secret.metadata.owner_references != sec_body.metadata.owner_references
        ):
            logger.info(f'Replacing secret {sec_name}')
            v1.replace_namespaced_secret(
                name=sec_name,
                namespace=namespace,
                body=sec_body,
            )
    except rest.ApiException as e:
        logger.error('Can not create a secret, it is base64 encoded? enable debug for details')
        logger.debug(f'data: {data}')
        logger.debug(f'Kube exception {e}')


def create_secret_metadata(
        name: str,
        namespace: str,
        csec_body: Dict[str, Any],
        annotations: Optional[Mapping[str, str]] = None,
        labels: Optional[Mapping[str, str]] = None,
) -> V1ObjectMeta:
    """Create Kubernetes metadata objects.

    Parameters
    ----------
    name: str
        The name of the Kubernetes secret.
    namespace: str
        The namespace where the secret will be place.
    csec_body: Dict[str, Any]
        The body of the clustersecret
    labels: Optional[Dict[str, str]]
        The secret labels.
    annotations: Optional[Dict[str, str]]
        The secrets annotations.

    Returns
    -------
    V1ObjectMeta
        Kubernetes metadata object with ClusterSecret annotations.
    """

    def filter_dict(
            prefixes: List[str],
            base: Dict[str, str],
            source: Optional[Mapping[str, str]] = None
    ) -> Iterator[Tuple[str, str]]:
        """ Remove potential useless / dangerous annotations and labels"""
        for item in base.items():
            yield item
        if source is not None:
            for item in source.items():
                key, _ = item
                if not any(key.startswith(prefix) for prefix in prefixes):
                    yield item

    base_labels = {
        CLUSTER_SECRET_LABEL: 'true'
    }
    base_annotations = {
        VERSION_ANNOTATION: get_version(),
    }

    # Create directly instead of with kopf.adopt to handle namespace events
    owner_reference = V1OwnerReference(
        api_version = csec_body.get('apiVersion', None),
        block_owner_deletion = True,
        controller = True,
        kind = csec_body.get('kind', None),
        name = csec_body.get('metadata', {}).get('name', None),
        uid = csec_body.get('metadata', {}).get('uid', None)
    )

    _annotations = filter_dict(BLACK_LISTED_ANNOTATIONS, base_annotations, annotations)
    _labels = filter_dict(BLACK_LISTED_LABELS, base_labels, labels)
    return V1ObjectMeta(
        name=name,
        namespace=namespace,
        owner_references=[owner_reference],
        annotations=dict(_annotations),
        labels=dict(_labels),
    )


def get_custom_objects_by_kind(
        group: str,
        version: str,
        plural: str,
        custom_objects_api: CustomObjectsApi,
) -> List[dict]:
    """
    Retrieve all CustomObjectsApi objects across all namespaces based on the provided group, version, and kind.

    Args:
        group (str): The API group of the custom object.
        version (str): The API version of the custom object.
        plural (str): The plural of the custom object.
        custom_objects_api (CustomObjectsApi): The Kubernetes CustomObjectsApi.

    Returns:
        List[dict]: A list of custom objects (in dict format) matching the provided group, version, and plural.

    Raises:
        ApiException: If there is an issue communicating with the Kubernetes API server.
    """
    try:
        # Retrieve all custom objects matching the group, version, and kind
        custom_objects = custom_objects_api.list_cluster_custom_object(
            group=group,
            version=version,
            plural=plural,
        )

        return custom_objects['items']
    except rest.ApiException as e:
        # Properly handle API exceptions
        raise rest.ApiException(f'Error while retrieving custom objects: {e}')
