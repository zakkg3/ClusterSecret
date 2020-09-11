# todo / roadmap:


## idempotent

1- on_resume recreate/refresh csec touple with all the csecs in the cluster and  (like syncedns) the secret sources list.

## for implement source: namespace/secret 

1- like we keep synced namespaces (csec[uid][syncedns]) we keep track of csec[sources] for all of them. 

2- create a new function to watch: on_filed (secret, if name == csec[*][sources]) and react.
