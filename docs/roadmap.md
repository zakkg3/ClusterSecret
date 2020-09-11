# todo / roadmap:


## idempotent

1- on_resume recreate/refresh csec touple with all the csecs in the cluster and  (like syncedns) the secret sources list.

## for implement source: namespace/secret 

1- like we keep synced namespaces (csec[uid][syncedns]) we keep track of csec[sources] for all of them. 

2- create a new function to watch: on_filed (secret, if name == csec[*][sources]) and react.


## BadgeApp best practices

### Automated test suite  / Static & Dynamic code analysis

The project MUST use at least one automated test suite that is publicly released as FLOSS (this test suite may be maintained as a separate FLOSS project)
At least one static code analysis tool (beyond compiler warnings and "safe" language modes) MUST be applied to any proposed major production release of the software before its release, if there is at least one FLOSS tool that implements this criterion in the selected language.

### New functionality testing

The project MUST have a general policy (formal or not) that as major new functionality is added to the software produced by the project, tests of that functionality should be added to an automated test suite

### warning flags

The project MUST enable one or more compiler warning flags, a "safe" language mode, or use a separate "linter" tool to look for code quality errors or common simple mistakes, if there is at least one FLOSS tool that can implement this criterion in the selected language.


### Use basic good cryptographic practices

Encrypt at rest. treat the clustersecret object as a secret!
Storing of passwords: the passwords MUST be stored as iterated hashes with a per-user salt by using a key stretching (iterated) algorithm (e.g., Argon2id, Bcrypt, Scrypt, or PBKDF2). See also OWASP Password Storage Cheat Sheet.
