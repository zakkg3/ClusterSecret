import os
from datetime import datetime
from kubernetes.client import V1ObjectMeta

from consts import CREATE_BY_ANNOTATION, LAST_SYNC_ANNOTATION, VERSION_ANNOTATION


def get_version() -> str:
    return os.getenv('CLUSTER_SECRET_VERSION', '0')


def get_replace_existing() -> bool:
    replace_existing = os.getenv('REPLACE_EXISTING', 'false')
    return replace_existing.lower() == 'true'


def create_secret_metadata(name: str, namespace: str) -> V1ObjectMeta:
    return V1ObjectMeta(
        name=name,
        namespace=namespace,
        annotations={
            CREATE_BY_ANNOTATION: "ClusterSecrets",
            VERSION_ANNOTATION: get_version(),
            LAST_SYNC_ANNOTATION: datetime.now().isoformat()
        }
    )
