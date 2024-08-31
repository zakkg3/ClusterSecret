# ClusterSecret
![CI](https://github.com/zakkg3/ClusterSecret/workflows/CI/badge.svg) [![Docker Repository on Quay](https://quay.io/repository/clustersecret/clustersecret/status "Docker Repository on Quay")](https://quay.io/repository/clustersecret/clustersecret) [![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/clustersecret)](https://artifacthub.io/packages/search?repo=clustersecret) [![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/4283/badge)](https://bestpractices.coreinfrastructure.org/projects/4283) [![License](http://img.shields.io/:license-apache-blue.svg)](http://www.apache.org/licenses/LICENSE-2.0.html) [![Kubernetes - v1.24.15 | v1.25.11 | v1.26.6 | v1.27.3](https://img.shields.io/static/v1?label=Kubernetes&message=v1.24.15+|+v1.25.11+|+v1.26.6+|+v1.27.3&color=2ea44f)](https://)
---

## Kubernetes ClusterSecret 
[*clustersecret.com*](https://clustersecret.com/)

Cluster wide secrets

ClusterSecret operator makes sure all the matching namespaces have the secret available and up to date.

 - New namespaces, if they match the pattern, will also have the secret.
 - Any change on the ClusterSecret will update all related secrets. Including changing the match pattern. 
 - Deleting the ClusterSecret deletes "child" secrets (all cloned secrets) too.

Full documentation available at [https://clustersecret.com](https://clustersecret.com/)

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


# installation

## Requirements

Current version `0.0.10` is tested for Kubernetes >= 1.19 up to 1.27.3
For ARM architectures use `<tag>_arm32` tag

For older kubernetes (<1.19) use the image tag `0.0.6` in your helm values file.

## Install

# Using the official helm chart

```bash
helm repo add clustersecret https://charts.clustersecret.io/
helm install clustersecret clustersecret/cluster-secret --version 0.4.0 -n clustersecret --create-namespace
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

You can specify multiple matching or non-matching RegExp. By default it will match all, same as defining matchNamespace = * 

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

## images

Images are build and push on tag ('git tag') with Github Actions. You can find them here:

https://quay.io/repository/clustersecret/clustersecret

## default archs  :
 
the following archetecures:

 - linux/386
 - linux/amd64

are under the image:tag : `quay.io/clustersecret/clustersecret:0.0.10`
 
Alternative architecrues:
 

## Known bugs:

 - check this on issues tab

# Roadmap:

TO-DO: enable super linter -> DISABLE_ERRORS
 
 

# Support
 
 If you need support, start with the troubleshooting guide: Run it in debug mode.
 You can open issues and we will try to address them. 

 That said, if you have questions, or just want to establish contact, reach out one way or another. [https://flag5.com](https://flag5.com) || nico at flag5.com
 
 Global inter-namespace cluster secrets - Secrets that work across namespaces  - Cluster wide secrets
