#  ClusterSecret
[*clustersecret.com*](https://clustersecret.com/)

Global inter-namespace cluster secrets - Secrets that work across namespaces.

ClusterSecret operator makes sure all the matching namespaces have the secret available. New namespaces, if they match the pattern, will also have the secret.
Any change on the ClusterSecret will update all related secrets. Deleting the ClusterSecret deletes "child" secrets (all cloned secrets) too.

Full documentation available at [https://clustersecret.com](https://clustersecret.com/)

<img src="https://github.com/zakkg3/ClusterSecret/blob/master/docs/clusterSecret.png" alt="Clustersecret diagram">

---

Here is how it looks like:

```yaml
kind: ClusterSecret
apiVersion: clustersecret.io/v1
metadata:
  name: default-wildcard-certifiate
matchNamespace:
  - prefix-ns-*
  - anothernamespace
avoidNamespaces:
  - supersecret-ns
data:
  tls.crt: BASE64
  tls.key: BASE64
```

## Secret Types

To create non-Opaque secrets, explicitly set the `type` field (lowercase, case-sensitive):

```yaml
apiVersion: clustersecret.io/v1
kind: ClusterSecret
metadata:
  name: registry-credentials
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded>
```

When using `valueFrom` to reference a source secret, the type is **not** inherited - you must set it explicitly on the ClusterSecret.

## Use cases.


Use it for certificates, registry pulling credentials and so on.

when you need a secret in more than one namespace. you have to:

1- Get the secret from the origin namespace.
2- Edit the  the secret with the new namespace.
3- Re-create the new secret in the new namespace.


This could be done with one command:

```bash
kubectl get secret <secret-name> -n <source-namespace> -o yaml \
| sed s/"namespace: <source-namespace>"/"namespace: <destination-namespace>"/\
| kubectl apply -n <destination-namespace> -f -
```

Clustersecrets automates this. It keep track of any modification in your secret and it will also react to new namespaces.



## Requirements

Current is 0.0.14 tested on > 1.27.1
Version 0.0.9 is tested for Kubernetes >= 1.19 up to 1.27.1

For older kubernes (<1.19) use the image tag "0.0.6" in  yaml/02_deployment.yaml

## Install

```bash
helm repo add clustersecret https://charts.clustersecret.com/
helm install clustersecret clustersecret/cluster-secret --version 0.4.3 -n clustersecret --create-namespace
```

## Configuration

### Logging

The operator's logging behavior can be configured via the `logging` values:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `logging.level` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `logging.encoder` | Output format: `plain` or `json` | `plain` |
| `logging.format` | Python format string (only used when `encoder` is `plain`) | `%(asctime)s - %(name)s - %(levelname)s - %(message)s` |
| `logging.includeKopf` | Include Kopf framework logs | `false` |

Example:

```yaml
logging:
  level: DEBUG
  encoder: json
  includeKopf: true
```

**Note:** When `LOG_LEVEL` is set to `DEBUG`, a warning will be logged: "DEBUG logging enabled - ONLY use in NON-PROD, leaks sensitive information"
