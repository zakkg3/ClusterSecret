"""
Constants used by the project
"""

CREATE_BY_ANNOTATION = 'clustersecret.io/created-by'
CREATE_BY_AUTHOR = 'ClusterSecrets'
LAST_SYNC_ANNOTATION = 'clustersecret.io/last-sync'
VERSION_ANNOTATION = 'clustersecret.io/version'

CLUSTER_SECRET_LABEL = "clustersecret.io"

BLOCKED_ANNOTATIONS = ["kopf.zalando.org", "kubectl.kubernetes.io"]

BLOCKED_LABELS = ["app.kubernetes.io"]
