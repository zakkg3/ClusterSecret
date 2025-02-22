import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Mapping, Tuple, Iterator
import re

import kopf
from kubernetes.client import CoreV1Api, CustomObjectsApi, exceptions, V1ObjectMeta, rest, V1Secret

from os_utils import get_blocked_labels, get_replace_existing, get_version
from consts import CREATE_BY_ANNOTATION, LAST_SYNC_ANNOTATION, VERSION_ANNOTATION, BLOCKED_ANNOTATIONS, \
    CREATE_BY_AUTHOR, CLUSTER_SECRET_LABEL


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
    # Get matchNamespace or default to all
    match_namespace = body.get('matchNamespace', ['.*'])

    # Get avoidNamespaces or default to None
    avoid_namespaces = body.get('avoidNamespaces', None)

    # Collect all namespaces names
    nss = [ns.metadata.name for ns in v1.list_namespace().items]
    matched_ns = []
    avoided_ns = []

    # Iterate over all matchNamespace
    for match_ns in match_namespace:
        matched_ns.extend([ns for ns in nss if re.match(match_ns, ns)])
        logger.debug(f'Matched namespaces: {", ".join(matched_ns)} match pattern: {match_ns}')

    # If avoidNamespaces is None simply return our matched list
    if not avoid_namespaces:
        return matched_ns

    # Iterate over all avoidNamespaces
    for avoid_ns in avoid_namespaces:
        avoided_ns.extend([ns for ns in nss if re.match(avoid_ns, ns)])
        logger.debug(f'Skipping namespaces: {", ".join(avoided_ns)} avoid pattern: {avoid_ns}')

    return list(set(matched_ns) - set(avoided_ns))


def read_data_secret(
        logger: logging.Logger,
        name: str,
        namespace: str,
        v1: CoreV1Api,
) -> Dict[str, str]:
    """Gets the data from the 'name' secret in namespace
    """
    data = {}
    logger.debug(f'Reading {name} from ns {namespace}')
    try:
        secret = v1.read_namespaced_secret(name, namespace)

        logger.debug(f'Obtained secret {secret}')
        data = secret.data
    except exceptions.ApiException as e:
        logger.error('Error reading secret')
        logger.debug(f'error: {e}')
        if e == '404':
            logger.error(f'Secret {name} in ns {namespace} not found.')
        raise kopf.TemporaryError('Error reading secret')
    return data


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
    except exceptions.ApiException as e:
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


def secret_metadata(
        logger: logging.Logger,
        name: str,
        namespace: str,
        v1: CoreV1Api,
) -> Optional[V1ObjectMeta]:
    try:
        secret = v1.read_namespaced_secret(name, namespace)
        return secret.metadata
    except exceptions.ApiException as e:
        if e.status == 404:
            return None
        logger.warning(f'Cannot read the secret {e}.')
        raise kopf.TemporaryError(f'Error reading secret {e}')


def sync_secret(
        logger: logging.Logger,
        namespace: str,
        body: Dict[str, Any],
        v1: CoreV1Api,
):
    """Creates a given secret on a given namespace
    """
    if 'metadata' not in body:
        raise kopf.TemporaryError('Metadata is required.')

    if 'name' not in body['metadata']:
        raise kopf.TemporaryError('Property name is missing in metadata.')

    cs_metadata: Dict[str, Any] = body.get('metadata')
    sec_name = cs_metadata.get('name')
    annotations = cs_metadata.get('annotations', None)
    labels = cs_metadata.get('labels', None)

    try:
        v1.read_namespace(name=namespace)
    except exceptions.ApiException as e:
        logger.debug(f'Namespace {namespace} not found while syncing secret {sec_name}. Never mind on this rare situation it will be handled in other place.')
        if e.status == 404:
            return

    if 'data' not in body:
        raise kopf.TemporaryError('Property data is missing.')

    data: Dict[str, Any] = body['data']

    if 'valueFrom' in data:
        if len(data.keys()) > 1:
            logger.error('Data keys with ValueFrom error, enable debug for more details')
            logger.debug(f'keys: {data.keys()}  len {len(data.keys())}')
            raise kopf.TemporaryError('ValueFrom can not coexist with other keys in the data')

        secret_key_ref: Dict[str, Any] = data.get('valueFrom', {}).get('secretKeyRef', {})
        ns_from: str = secret_key_ref.get('namespace', None)
        name_from: str = secret_key_ref.get('name', None)
        keys: Optional[List[str]] = secret_key_ref.get('keys', None)

        if ns_from is None or name_from is None:
            logger.error('ERROR reading data from remote secret, enable debug for more details')
            logger.debug(f'Deta details: {data}')
            raise kopf.TemporaryError('Can not get Values from external secret')

        # Filter the keys in data based on the keys list provided
        raw_data = read_data_secret(logger, name_from, ns_from, v1)
        if keys is not None:
            data = {key: value for key, value in raw_data.items() if key in keys}
        else:
            data = raw_data

    logger.debug(f'Going to create with data: {data}')
    secret_type = body.get('type', 'Opaque')

    body = V1Secret()
    body.metadata = create_secret_metadata(
        name=sec_name,
        namespace=namespace,
        annotations=annotations,
        labels=labels,
    )
    body.type = secret_type
    body.data = data
    logger.info(f'Syncing secret {sec_name} in namespace {namespace}.')
    logger.debug(f'V1Secret= {body}')

    try:
        # Get metadata from secrets (if exist)
        metadata = secret_metadata(logger, name=sec_name, namespace=namespace, v1=v1)

        # If nothing returned, the secret does not exist, creating it then
        if metadata is None:
            logger.info(f'Creating new secret {sec_name} in namespace {namespace}.')
            logger.debug(f'response is {v1.create_namespaced_secret(namespace, body)}')
            return

        if metadata.annotations is None or metadata.annotations.get(CREATE_BY_ANNOTATION) is None:
            logger.info(f'Secret {sec_name} already exist in namespace {namespace} and is not managed by ClusterSecret.')

            # If we should not overwrite existing secrets
            if not get_replace_existing():
                logger.info(f'Secret {sec_name} in namespace {namespace} will not be replaced. You can enforce this by setting env REPLACE_EXISTING to true.')
                return

        logger.info(f'Replacing secret {sec_name} in namespace {namespace}.')
        v1.replace_namespaced_secret(
            name=sec_name,
            namespace=namespace,
            body=body,
        )
    except exceptions.ApiException as e:
        logger.error('Can not create a secret, it is base64 encoded? Enable debug for details.')
        logger.debug(f'data: {data}')
        logger.debug(f'Kube exception {e}')


def create_secret_metadata(
        name: str,
        namespace: str,
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
        CREATE_BY_ANNOTATION: CREATE_BY_AUTHOR,
        VERSION_ANNOTATION: get_version(),
        LAST_SYNC_ANNOTATION: datetime.now().isoformat(),
    }

    _annotations = filter_dict(BLOCKED_ANNOTATIONS, base_annotations, annotations)
    _labels = filter_dict(get_blocked_labels(), base_labels, labels)
    return V1ObjectMeta(
        name=name,
        namespace=namespace,
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
    except exceptions.ApiException as e:
        # Properly handle API exceptions
        raise exceptions.ApiException(f'Error while retrieving custom objects: {e}')
