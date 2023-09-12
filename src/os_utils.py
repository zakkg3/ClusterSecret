import os


def get_version() -> str:
    """
    Wrapper for CLUSTER_SECRET_VERSION variable environment
    """
    return os.getenv('CLUSTER_SECRET_VERSION', '0')


def get_replace_existing() -> bool:

    replace_existing = os.getenv('REPLACE_EXISTING', 'false')
    return replace_existing.lower() == 'true'
