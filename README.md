# ClusterSecret
![CI](https://github.com/zakkg3/ClusterSecret/workflows/CI/badge.svg) [![Docker Repository on Quay](https://quay.io/repository/clustersecret/clustersecret/status "Docker Repository on Quay")](https://quay.io/repository/clustersecret/clustersecret) [![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/clustersecret)](https://artifacthub.io/packages/search?repo=clutersecret)[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/4283/badge)](https://bestpractices.coreinfrastructure.org/projects/4283) [![License](http://img.shields.io/:license-apache-blue.svg)](http://www.apache.org/licenses/LICENSE-2.0.html) [![Kubernetes - v1.24.15 | v1.25.11 | v1.26.6 | v1.27.3](https://img.shields.io/static/v1?label=Kubernetes&message=v1.24.15+|+v1.25.11+|+v1.26.6+|+v1.27.3&color=2ea44f)](https://)
---

[*clustersecret.com*](https://clustersecret.com/)

Kubernetes Cluster wide secrets

The clusterSecret operator makes sure all the matching namespaces have the secret available and up to date.

 - New namespaces, if they match the pattern, will also have the secret.
 - Any change on the ClusterSecret will update all related secrets. Including changing the match pattern. 
 - Deleting the ClusterSecret deletes "child" secrets (all cloned secrets) too.

Full documentation is available at [https://clustersecret.com](https://clustersecret.com/)

<img src="https://github.com/zakkg3/ClusterSecret/blob/master/docs/clusterSecret.png" alt="Clustersecret diagram">

---

Here is how it looks like:

```yaml
kind: ClusterSecret
apiVersion: clustersecret.io/v1
metadata:
  namespace: clustersecret
  name: default-wildcard-certifiate
matchNamespace:
  - prefix_ns-*
  - anothernamespace
avoidNamespaces:
  - supersecret-ns
data:
  tls.crt: BASE64
  tls.key: BASE64
```


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

If this is helpful, consider supporting the project :)

<a href="https://buymeacoffee.com/4s0l9aymb" target="_blank"><img src="https://buymeacoffee.com/assets/img/custom_images/yellow_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>


# installation

## Requirements

Current version `0.0.14` is tested for Kubernetes >= 1.19 up to 1.27.3
For older Kubernetes (<1.19) use the image tag `0.0.6` in your helm values file.

architectures available (0.0.14):

SHA256 ed12e8f3e630 | linux | 386
SHA256 91b0285f5398 | linux | amd64
SHA256 cad79c68cb8c | linux | s390x
SHA256 637f3be7850a | linux | arm64

## Install

# Using the official helm chart

```bash
helm repo add clustersecret https://charts.clustersecret.com/
helm install clustersecret clustersecret/cluster-secret --version 0.4.3 -n clustersecret --create-namespace
```

# with just kubectl

clone the repo and apply

```bash
cd ClusterSecret
kubectl apply -f ./yaml
```
 
# quick start:

create a ClusterSecret object yaml like the one above, or in the example in yaml/Object_example/obj.yaml and apply it in your cluster `kubectl apply -f yaml/Object_example/obj.yaml`

The ClusterSecret operator will pick it up and will create the secret in every matching namespace:  match `matchNamespace` but not matching  `avoidNamespaces` RegExp's.

You can specify multiple matching or non-matching RegExp. By default, it will match all, the same as defining matchNamespace = * 

## Get the clustersecrets

```bash
$> kubectl get csec -n clustersecret
NAME            TYPE
global-secret
```

## Minimal example

```yaml
apiVersion: clustersecret.io/v1
kind: ClusterSecret
metadata:
  name: global-secret
  namespace: my-fav-namespce
data:
  username: MTIzNDU2Cg==
  password: Nzg5MTAxMTIxMgo=
```

## Secret Types

By default, ClusterSecret creates secrets with `type: Opaque`. To create other secret types (e.g., `kubernetes.io/dockerconfigjson`, `kubernetes.io/tls`), you must explicitly set the `type` field:

```yaml
apiVersion: clustersecret.io/v1
kind: ClusterSecret
metadata:
  name: registry-credentials
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded-docker-config>
```

**Important notes:**
- The `type` field is **case-sensitive** - use lowercase `type`, not `Type`
- When using `valueFrom` to reference a source secret, the type is **not** automatically inherited - you must explicitly set it on the ClusterSecret

### Using valueFrom

You can reference an existing secret instead of embedding data directly:

```yaml
apiVersion: clustersecret.io/v1
kind: ClusterSecret
metadata:
  name: registry-credentials
type: kubernetes.io/dockerconfigjson    # Must be set explicitly
data:
  valueFrom:
    secretKeyRef:
      namespace: source-namespace
      name: source-secret-name
      keys:                              # Optional: specify which keys to copy
        - .dockerconfigjson
```

## Configuration

### Environment Variables

The operator can be configured via the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `LOG_ENCODER` | Output format: `plain` or `json` | `plain` |
| `LOG_FORMAT` | Python format string (only used when `LOG_ENCODER=plain`) | `%(asctime)s - %(name)s - %(levelname)s - %(message)s` |
| `LOG_INCLUDE_KOPF` | Include Kopf framework logs: `true` or `false` | `false` |
| `REPLACE_EXISTING` | Replace existing secrets not managed by ClusterSecret: `true` or `false` | `false` |
| `BLOCKED_LABELS` | Comma-separated list of label prefixes to filter from synced secrets | `app.kubernetes.io` |

**Note:** When `LOG_LEVEL` is set to `DEBUG`, a warning will be logged: "DEBUG logging enabled - ONLY use in NON-PROD, leaks sensitive information"

When using the Helm chart, these can be configured via the `logging` values block. See the [chart README](charts/cluster-secret/README.md) for details.

## Development

### Local Testing with Podman

The Makefile uses podman for local builds and testing. On Linux with recent Ubuntu/AppArmor, you may encounter:

```
cannot clone: Permission denied
Error: cannot re-exec process
```

This is caused by AppArmor restricting unprivileged user namespaces. Fix with:

```bash
sudo sysctl kernel.apparmor_restrict_unprivileged_userns=0
```

To make it permanent:

```bash
echo "kernel.apparmor_restrict_unprivileged_userns=0" | sudo tee /etc/sysctl.d/99-podman.conf
```

### Make Targets

```bash
make start-test-env  # Create Kind cluster with podman
make test            # Run unit and helm tests
make build           # Build container image
make stop-test-env   # Delete Kind cluster
```

## Images

Images are built and pushed on tag ('git tag') with GitHub Actions. You can find them here:

https://quay.io/repository/clustersecret/clustersecret

## Known bugs:

 - check this on the issues tab

# Roadmap:

TO-DO: enable super linter -> DISABLE_ERRORS
 
 

# Support
 
 If you need help, you can start with the troubleshooting guide: Run it in debug mode.
 You can open issues and we will try to address them. 

 That said, if you have questions, or just want to establish contact, reach out one way or another. [https://flag5.com](https://flag5.com) || nico at flag5.com
 
 Global inter-namespace cluster secrets - Secrets that work across namespaces  - Cluster wide secrets
