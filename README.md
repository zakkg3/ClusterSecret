# ClusterSecret
Introduce Kubernetes ClusterSecret 


Global inter-namespace cluster secrets - Secrets that work across namespaces 

```
apiVersion: v2
kind: ClusterSecret
type: kubernetes.io/tls
metadata:
  name: default-wildcard-certifiate
matchLabels:
  domain: example.com 
matchNamespace:
  - prefix_ns-*
  - anothernamespace
avoidNamespaces:
  - supersecret-ns
data:
  tls.crt: ...
  tls.key: ...
```

ClusterSecret operator will make shure all the matching namespaces will have the secret available.
Any change on the secret will be replicated to all the matching namespaces


https://github.com/kubernetes/kubernetes/issues/70147
https://github.com/kubernetes/kubernetes/issues/62153



#dev:

## delete pod to restart all:

```
k delete pod -n clustersecret  $(k get pods -n clustersecret -o jsonpath='{.items[*].metadata.name}')
```


## logs

```
k logs -n clustersecret  $(k get pods -n clustersecret -o jsonpath='{.items[*].metadata.name}')
```
