# ClusterSecret
Introduce Kubernetes ClusterSecret 


Global inter-namespace cluster secrets - Secrets that work across namespaces 

```
Kind: ClusterSecret
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

ClusterSecret operator makes sure all the matching namespaces have the secret available. New namespaces, if they match the pattern, will also have the secret.
Any change on the ClusterSecret will update all related secrets. Deleting the ClusterSecret deletes "child" secrets (all cloned secrets) too.

Use it for certificates, registry pulling credentials and so on.

## Use case.

when you need a secret in more than one namespace. you need to get the secret from the origin namespace, edit the  the secret with the new namespace and create the new one. This could be done with one command:

```
kubectl get secret <secret-name> -n <source-namespace> -o yaml \
| sed s/"namespace: <source-namespace>"/"namespace: <destination-namespace>"/\
| kubectl apply -n <destination-namespace> -f -
```

But if you want to automate the cloning of secrets into a set of namespaces (a regex pattern). ClusterSecret is the way to go.


# installation

## tl;dr

```
kubectl apply -f ./yaml
```

## step by step

To instal ClusterSecret operator we need to create (in this order):

 - RBAC resources (avoid if you are not running RBAC) to allow the operator to create/update/patch secrets: yaml/00_
 - Custom resource definition for the ClusterSecret resource: yaml/01_crd.yaml
 - The ClusterSecret operator itself: yaml/02_deployment.yaml
 
 
# quick start:

create a ClusterSecret object yaml like the one above, or in the example in yaml/Object_example/obj.yaml and apply it in your cluster `kubectl apply -f yaml/Object_example/obj.yaml`

The ClusterSecret operator will pick it up and will create the secret in every matching namespace:  match `matchNamespace` but not matching  `avoidNamespaces` RegExp's.

You can specify multiple matching or non-matching RegExp. By default it will match all, same as defining matchNamespace = * 

## Get the clustersecrets

```
$> kubectl get csec -n clustersecret
NAME            TYPE
global-secret
```

## Minimal example

```
apiVersion: clustersecret.io/v1
kind: ClusterSecret
metadata:
  name: global-secret
  namespace: my-fav-namespce
data:
  username: MTIzNDU2Cg==
  password: Nzg5MTAxMTIxMgo=
```

# Debugging.


**NOTE**: in **debug mode** object data (the secret) are sent to stdout, potentially logs are being collected by Loki / Elasticsearch or any log management platform -> **Not for production!**.

Overwirte deployment entrypoint (Kubernetes `command`) from `kopf run /src/handlers.py` to `kopf run /src/handlers.py --verbose`

# Dev: Run it in your terminal.

For development you dont want to build/push/recreate pod every time. Instead we can run the operator locally:

Once you have the config in place (kubeconfig) you can just install the requirementes (pip install /base-image/requirements.txt) and then run the operator from your machine (usefull for debbuging.)

```
kopf run ./src/handlers.py --verbose
```

 Make sure to have the proper RBAC in place (`k apply -f yaml/00_rbac.yaml`) and also the CRD definition (`k apply -f yaml/01_crd.yaml`)



 
# Roadmap:
 - implement `source` to specify a source secret to sync instead of `data` field. (https://github.com/zakkg3/ClusterSecret/issues/3)
 - set type of secret (ie tls)
 - set annotations and labels
 
 
