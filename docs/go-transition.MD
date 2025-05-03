# ClusterSecret: Python to Go Transition

## Current Status

The ClusterSecret operator is currently in a transition phase from a Python-based implementation (using the Kubernetes Operator Pythonic Framework, Kopf) to a Go-based implementation (using Kubebuilder). This document summarizes the current state of this transition and what remains to be completed.

## Background

ClusterSecret is a Kubernetes operator that allows you to define secrets once and have them automatically propagated to multiple namespaces based on matching patterns. It solves the common problem of needing to maintain identical secrets across different namespaces.

## Implementation Comparison

### Python Implementation (Current Production Version)

- Built using Kopf (Kubernetes Operator Pythonic Framework)
- Fully functional with all features described in the README
- Supports pattern matching for namespaces via `matchNamespace` and `avoidNamespaces` fields
- Handles secret propagation, updates, and deletion
- Referenced in the deployment YAML files (e.g., in `yaml/02_deployment.yaml`)

### Go Implementation (In Development)

- Built using Kubebuilder and controller-runtime
- Basic structure is in place:
  - main.go: Sets up the controller manager
  - controllers/clustersecret_controller.go: Contains the controller implementation (incomplete)
  - v1alpha1/clustersecret_types.go: Defines the ClusterSecret type (incomplete)
- The CRD in the Go implementation is different from the production CRD:
  - Go CRD: `cache.clustersecret.io_clustersecrets.yaml`
  - Production CRD: `clustersecret.io/v1`
- The Reconcile function in the controller is currently a stub that doesn't implement the actual business logic

## How the Go Implementation Works

The Go implementation follows the standard Kubernetes operator pattern using controller-runtime:

1. **Controller Registration**: In main.go, a ClusterSecretReconciler is created and registered with the manager.
   ```go
   if err = (&controllers.ClusterSecretReconciler{
       Client: mgr.GetClient(),
       Scheme: mgr.GetScheme(),
   }).SetupWithManager(mgr); err != nil {
       setupLog.Error(err, "unable to create controller", "controller", "ClusterSecret")
       os.Exit(1)
   }
   ```

2. **Manager Start**: The manager is started, which runs all registered controllers in separate goroutines.
   ```go
   setupLog.Info("starting manager")
   if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
       setupLog.Error(err, "problem running manager")
       os.Exit(1)
   }
   ```

3. **Controller Setup**: The controller is set up to watch for changes to ClusterSecret resources and Secret resources that are owned by a ClusterSecret.
   ```go
   func (r *ClusterSecretReconciler) SetupWithManager(mgr ctrl.Manager) error {
       return ctrl.NewControllerManagedBy(mgr).
           For(&cachev1alpha1.ClusterSecret{}).
           Owns(&v1.Secret{}). 
           Complete(r)
   }
   ```

4. **Reconciliation Logic**: The Reconcile function is where the actual business logic would be implemented, but it's currently incomplete.

## What Needs to Be Completed

1. **Update the ClusterSecret Type**: The ClusterSecret type in v1alpha1/clustersecret_types.go needs to be updated to include the `matchNamespace` and `avoidNamespaces` fields that are present in the production CRD.

2. **Implement the Reconcile Function**: The Reconcile function in controllers/clustersecret_controller.go needs to be implemented to:
   - Get the ClusterSecret resource
   - Find all namespaces that match the patterns in `matchNamespace` and don't match patterns in `avoidNamespaces`
   - Create or update secrets in those namespaces
   - Delete secrets from namespaces that no longer match

3. **Add Finalizers**: Implement finalizers to handle cleanup when a ClusterSecret is deleted.

4. **Add Status Updates**: Update the status of the ClusterSecret resource to reflect the current state of the propagation.

5. **Add Tests**: Add unit and integration tests to ensure the Go implementation works correctly.

6. **Update Documentation**: Update the documentation to reflect the new Go implementation.

## Conclusion

The transition from Python to Go is a significant undertaking, but it will provide benefits in terms of performance, resource usage, and maintainability. The current state of the Go implementation provides a good foundation, but significant work remains to be done to achieve feature parity with the Python implementation.

## CRD Version 2 Design

The Go implementation introduces a new v2 of the ClusterSecret CRD with significant improvements over v1. Here's a comparison:

### v1 vs v2 Format

**v1 Format (Current Python Implementation)**:
```yaml
apiVersion: clustersecret.io/v1
kind: ClusterSecret
metadata:
  name: clustersecret-v1-sample
matchNamespace:
  - foo.*
avoidNamespaces:
  - kube-.*
type: Opaque
data:
  a: bG9yZW0K
```

**v2 Format (New Go Implementation)**:
```yaml
apiVersion: clustersecret.io/v2
kind: ClusterSecret
metadata:
  name: clustersecret-v2-sample
spec:
  matchNamespaces:
    - foo.*
  avoidNamespaces:
    - kube-.*
  template:
    data:
      a: bG9yZW0K
```

### Enhanced Namespace Selection

The v2 CRD introduces Kubernetes-style selectors for more powerful namespace selection:

```yaml
spec:
  namespaceSelectorTerms:
    - matchFields:
        # Select namespaces by name using regex
        - key: metadata.name
          operator: InRegex
          values:
            - foo.*
        - key: metadata.name
          operator: NotInRegex
          values:
            - kube-.*
    - matchExpressions:
        # Select namespaces by labels
        - key: environment
          operator: In
          values:
            - prod
            - staging
        # Support for numeric comparisons
        - key: my-int-label
          operator: Gt
          values:
            - "25"
```

This provides much more flexibility in selecting namespaces based on both names and labels, similar to how pod node affinities work in Kubernetes.

### Enhanced Secret Data References

The v2 CRD introduces improved ways to reference data from existing secrets:

1. **dataFrom** - Load all keys from referenced secrets:
```yaml
spec:
  dataFrom:
    - secretRef:
        name: source-secret
        namespace: default
```

2. **dataValueFrom** - Load specific keys from secrets with optional renaming:
```yaml
spec:
  dataValueFrom:
    foo:
      secretKeyRef:
        name: source-secret-1
        namespace: default
        key: foo
    renamed-moo:
      secretKeyRef:
        name: source-secret-2
        namespace: default
        key: moo
```

### Seamless Conversion Support

The Go implementation leverages Kubebuilder's conversion support to provide seamless migration from v1 to v2:
- Deploying a v1 ClusterSecret makes it available as both v1 and v2 simultaneously
- The operator internally processes everything as v2
- Users can migrate at their own pace

## To-Do List for Go Implementation

### Core Functionality
 - Complete the implementation of the v2 CRD with proper spec validation
 - Implement the enhanced namespace selection using namespaceSelectorTerms
 - Implement the core reconciliation logic for secret propagation
 - Add support for secret updates and propagation of changes
 - Implement cleanup of secrets when ClusterSecret is deleted
 - Add finalizers for proper resource cleanup

### Advanced Features
 - Complete the implementation of dataFrom and dataValueFrom functionality
 - Support for immutable secrets
 - Implement annotation and label propagation to child secrets
 - Add support for watching namespace creation to automatically propagate secrets to new namespaces
 - Implement the `REPLACE_EXISTING` environment variable functionality

### Testing & Quality
 - Implement e2e tests similar to those in the conformance directory
 - Add unit tests for all components to prevent regressions
 - Implement linting and other code quality checks
 - Add integration tests with different Kubernetes versions

### Deployment & Compatibility
 - Finalize the v1 to v2 conversion logic
 - Ensure backward compatibility with existing v1 resources
 - Update Helm charts for the Go implementation
 - Support multi-architecture builds (amd64, arm64, s390x, etc.)
 - Add migration path from Python to Go implementation

### Documentation
 - Update all documentation to reflect the Go implementation and v2 CRD
 - Document the new namespace selection features
 - Document the enhanced secret data reference features
 - Add developer documentation for contributing to the Go codebase
 - Document the architecture and design decisions
 - Update examples to use both v1 and v2 CRD formats
