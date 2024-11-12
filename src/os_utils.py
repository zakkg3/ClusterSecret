import os
from functools import cache

from consts import BLOCKED_LABELS


@cache
def get_version() -> str:
    """
    Wrapper for CLUSTER_SECRET_VERSION variable environment
    """
    return os.getenv('CLUSTER_SECRET_VERSION', '0')


@cache
def get_replace_existing() -> bool:
    replace_existing = os.getenv('REPLACE_EXISTING', 'false')
    return replace_existing.lower() == 'true'


@cache
def get_blocked_labels() -> list[str]:
    blocked_labels = os.getenv('BLOCKED_LABELS')

    if not blocked_labels:
        return BLOCKED_LABELS

    return [label.strip() for label in blocked_labels.split(',')]

@cache
def in_cluster() -> bool:
    """
    Whether we are running in cluster (on the pod)  or outside (debug mode.)
    """
    return os.getenv('KUBERNETES_SERVICE_HOST', None) is not None
