#  ClusterSecret 
[*clustersecret.io*](https://clustersecret.io/)

Global inter-namespace cluster secrets - Secrets that work across namespaces.

ClusterSecret operator makes sure all the matching namespaces have the secret available. New namespaces, if they match the pattern, will also have the secret.
Any change on the ClusterSecret will update all related secrets. Deleting the ClusterSecret deletes "child" secrets (all cloned secrets) too.

Full documentation available at [https://clustersecret.io](https://clustersecret.io/)

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



## Requirements

Current is 0.0.10 tested on > 1.27.1
Version 0.0.9 is tested for Kubernetes >= 1.19 up to 1.27.1

For older kubernes (<1.19) use the image tag "0.0.6" in  yaml/02_deployment.yaml

## Install

```bash
helm repo add clustersecret https://charts.clustersecret.com/
helm install clustersecret clustersecret/cluster-secret --version 0.4.2 -n clustersecret --create-namespace
```
