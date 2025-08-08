/*
Copyright 2024.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package controller

import (
	"cmp"
	"context"
	"fmt"
	"slices"
	"strings"
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/builder"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/event"
	"sigs.k8s.io/controller-runtime/pkg/handler"
	"sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/predicate"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	clustersecretiov2 "github.com/zakkg3/ClusterSecret/api/v2"
	"github.com/zakkg3/ClusterSecret/internal/util"
)

var (
	secretOwnerKey      = ".metadata.controller"
	csecSecretRefKey    = ".spec.template.dataFrom[*].secretRef.name"
	csecSecretKeyRefKey = ".spec.template.dataValueFrom.*.secretKeyRef.name"
	apiGVStr            = clustersecretiov2.GroupVersion.String()

	// typeReadyClusterSecret represents the status of the ClusterSecret reconciliation
	typeReadyClusterSecret = "Ready"

	labelManagedBy           = "app.kubernetes.io/managed-by"
	labelManagedByValue      = "ClusterSecrets"
	annotationCreatedBy      = "clustersecret.io/created-by"
	annotationCreatedByValue = "ClusterSecrets"
	annotationVersion        = "clustersecret.io/version"
	annotationLastSync       = "clustersecret.io/last-sync"
	annotationLastSyncFormat = time.RFC3339Nano
)

// ClusterSecretReconciler reconciles a ClusterSecret object
type ClusterSecretReconciler struct {
	client.Client
	Scheme  *runtime.Scheme
	Version string
}

//+kubebuilder:rbac:groups=clustersecret.io,resources=clustersecrets,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=clustersecret.io,resources=clustersecrets/status,verbs=get;update;patch
//+kubebuilder:rbac:groups=clustersecret.io,resources=clustersecrets/finalizers,verbs=update
//+kubebuilder:rbac:groups=core,resources=secrets,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=core,resources=namespaces,verbs=get;list;watch

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.
//
// For more details, check Reconcile and its Result here:
// - https://pkg.go.dev/sigs.k8s.io/controller-runtime@v0.17.2/pkg/reconcile
func (r *ClusterSecretReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	log := log.FromContext(ctx)

	// Get csec Instance
	csec := &clustersecretiov2.ClusterSecret{}

	if err := r.Get(ctx, req.NamespacedName, csec); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	if len(csec.Status.Conditions) == 0 {
		meta.SetStatusCondition(&csec.Status.Conditions, metav1.Condition{
			Type:    typeReadyClusterSecret,
			Status:  metav1.ConditionUnknown,
			Reason:  "Reconciling",
			Message: "Starting reconciliation",
		})
		if err := r.Status().Update(ctx, csec); err != nil {
			log.Error(err, "unable to update ClusterSecret status")
			return ctrl.Result{}, err
		}

		// Need to refetch as the status was updated, and therefore so was the generation
		if err := r.Get(ctx, req.NamespacedName, csec); err != nil {
			return ctrl.Result{}, client.IgnoreNotFound(err)
		}
	}

	// Remove the old Python controller's kopf stuff
	if removeKopfRemenants(csec) {
		if err := r.Update(ctx, csec); err != nil {
			return ctrl.Result{}, client.IgnoreNotFound(err)
		}

		log.V(1).Info("cleaned up fields set by older Kopf-based ClusterSecret operator (that was used in ClusterSecret v0.0.11 and below)")

		// Get the updated version
		if err := r.Get(ctx, req.NamespacedName, csec); err != nil {
			return ctrl.Result{}, client.IgnoreNotFound(err)
		}
	}

	var childSecrets corev1.SecretList
	if err := r.List(ctx, &childSecrets, client.MatchingFields{secretOwnerKey: req.Name}); err != nil {
		log.Error(err, "unable to list child Secrets")
		return ctrl.Result{}, err
	}

	var namespaces corev1.NamespaceList
	if err := r.List(ctx, &namespaces); err != nil {
		log.Error(err, "unable to list Namespaces")
		return ctrl.Result{}, err
	}

	var matchedNamespaces []string
	var avoidedNamespaces []string

	var readySecrets int32
	var unwantedSecrets []*corev1.Secret
	var outOfSyncSecrets []*corev1.Secret
	var namespacesWithMissingSecret []string

	var expectedSecret *corev1.Secret

	updateReconcilingStatus := func(cond metav1.ConditionStatus, format string, args ...any) error {
		var updateErr error
		const maxAttempts = 3
		for attempt := range maxAttempts {
			if updateErr != nil {
				log.V(1).Info("failed to update ClusterSecret status, retrying", "error", updateErr, "attempt", attempt, "maxAttempts", maxAttempts)
			}

			// Need to refetch as the status was updated, and therefore so was the generation
			if err := r.Get(ctx, req.NamespacedName, csec); err != nil {
				return client.IgnoreNotFound(err)
			}

			if expectedSecret != nil {
				csec.Status.DataCount = int32(len(expectedSecret.Data))
			}
			csec.Status.MatchingNamespacesCount = int32(len(matchedNamespaces))
			csec.Status.MatchingNamespaces = matchedNamespaces
			csec.Status.ReadySecretsCount = readySecrets
			csec.Status.ReadySecretsRatio = fmt.Sprintf("%d/%d",
				csec.Status.ReadySecretsCount,
				csec.Status.MatchingNamespacesCount)

			meta.SetStatusCondition(&csec.Status.Conditions, metav1.Condition{
				Type:    typeReadyClusterSecret,
				Status:  cond,
				Reason:  "Reconciling",
				Message: fmt.Sprintf(format, args...),
			})
			updateErr = r.Status().Update(ctx, csec)
			if updateErr == nil {
				return nil
			}
		}
		if updateErr != nil {
			log.Error(updateErr, "unable to update ClusterSecret status")
			return updateErr
		}
		return nil
	}

	for _, ns := range namespaces.Items {
		match, err := matchesNamespace(csec.Spec.NamespaceSelectorTerms, &ns)
		if err != nil {
			log.Error(err, "unable to evaluate regexp")
			return ctrl.Result{}, err
		}

		if match {
			matchedNamespaces = append(matchedNamespaces, ns.Name)
		} else {
			avoidedNamespaces = append(avoidedNamespaces, ns.Name)
		}
	}
	slices.Sort(matchedNamespaces)
	slices.Sort(avoidedNamespaces)

	expectedSecret, err := r.constructSecret(ctx, csec)
	if err != nil {
		if err := updateReconcilingStatus(metav1.ConditionFalse,
			"Failed to construct secret (%s) for custom resource (%s): %s",
			expectedSecret.Name, csec.Name, err,
		); err != nil {
			return ctrl.Result{}, err
		}

		// Log error, but don't return it, as we don't want to retry reconcile
		// immediately when we know the secret creation doesn't work.
		log.Error(err, "unable to construct secrets in ClusterSecret")
		return ctrl.Result{}, nil
	}

	for i, sec := range childSecrets.Items {
		if slices.Contains(avoidedNamespaces, sec.Namespace) {
			unwantedSecrets = append(unwantedSecrets, &childSecrets.Items[i])
		}

		diff := getSecretDiff(&sec, expectedSecret)
		switch diff {
		case "":
			log.V(2).Info("secret is up-to-date")
			readySecrets++
		default:
			log.V(1).Info("secret is out of sync", "cause", diff)
			outOfSyncSecrets = append(outOfSyncSecrets, &childSecrets.Items[i])
		}
	}

	for _, ns := range matchedNamespaces {
		if !slices.ContainsFunc(childSecrets.Items, func(sec corev1.Secret) bool {
			return sec.Namespace == ns
		}) {
			namespacesWithMissingSecret = append(namespacesWithMissingSecret, ns)
		}
	}

	// apply changes

	var reconcileErrors []string

	for _, sec := range unwantedSecrets {
		if err := r.Delete(ctx, sec, client.PropagationPolicy(metav1.DeletePropagationBackground)); client.IgnoreNotFound(err) != nil {
			log.Error(err, "unable to delete secret", "secret", sec)
			reconcileErrors = append(reconcileErrors, fmt.Sprintf("- remove secret from namespace (%s): %s", sec.Namespace, err))
			continue
		}
		log.V(0).Info("deleted secret", "secret", sec)
	}

	for _, sec := range outOfSyncSecrets {
		if err := r.reconcileOutOfDateSecret(ctx, req, sec, expectedSecret); err != nil {
			reconcileErrors = append(reconcileErrors, fmt.Sprintf("- update outdated secret in namespace (%s): %s", sec.Namespace, err))
			continue
		}

		readySecrets++
	}

	for _, ns := range namespacesWithMissingSecret {
		if err := r.reconcileMissingSecret(ctx, req, ns, expectedSecret); err != nil {
			reconcileErrors = append(reconcileErrors, fmt.Sprintf("- add secret to namespace (%s): %s", ns, err))
			continue
		}

		readySecrets++
	}

	if len(reconcileErrors) != 0 {
		if err := updateReconcilingStatus(metav1.ConditionTrue,
			"Failed to reconcile secret (%s) for custom resource (%s):\n%s",
			expectedSecret.Name, csec.Name, strings.Join(reconcileErrors, "\n"),
		); err != nil {
			return ctrl.Result{}, err
		}
		return ctrl.Result{}, nil
	}

	if err := updateReconcilingStatus(metav1.ConditionTrue,
		"Secrets for custom resource (%s) on %d namespaces created successfully",
		csec.Name, csec.Status.MatchingNamespacesCount,
	); err != nil {
		return ctrl.Result{}, err
	}

	return ctrl.Result{}, nil
}

func removeKopfRemenants(csec *clustersecretiov2.ClusterSecret) bool {
	changed := false

	oldFinalizerIndex := slices.Index(csec.Finalizers, "kopf.zalando.org/KopfFinalizerMarker")
	if oldFinalizerIndex != -1 {
		csec.Finalizers = append(csec.Finalizers[:oldFinalizerIndex], csec.Finalizers[oldFinalizerIndex+1:]...)
		changed = true
	}

	if _, isSet := csec.Annotations["kopf.zalando.org/last-handled-configuration"]; isSet {
		delete(csec.Annotations, "kopf.zalando.org/last-handled-configuration")
		changed = true
	}

	return changed
}

func (r *ClusterSecretReconciler) constructSecret(ctx context.Context, csec *clustersecretiov2.ClusterSecret) (*corev1.Secret, error) {
	secMetadata := cmp.Or(csec.Spec.Template.Metadata, &clustersecretiov2.SecretTemplateMetadata{})
	expectedSecret := &corev1.Secret{
		ObjectMeta: metav1.ObjectMeta{
			Name:        cmp.Or(secMetadata.Name, csec.Name),
			Labels:      secMetadata.Labels,
			Annotations: secMetadata.Annotations,
		},
		Type: cmp.Or(csec.Spec.Template.Type, "Opaque"),
	}
	if expectedSecret.Annotations == nil {
		expectedSecret.Annotations = map[string]string{}
	}
	if expectedSecret.Labels == nil {
		expectedSecret.Labels = map[string]string{}
	}

	expectedSecret.Annotations[annotationCreatedBy] = annotationCreatedByValue
	expectedSecret.Annotations[annotationVersion] = cmp.Or(r.Version, "unknown")
	// Delete it, as the user should not be able to set it, and we only set it on update
	delete(expectedSecret.Annotations, annotationLastSync)

	// only set if user doesn't set it
	if _, isSet := expectedSecret.Labels[labelManagedBy]; isSet {
		expectedSecret.Labels[labelManagedBy] = labelManagedByValue
	}

	// first load data from secrets
	for i, dataFrom := range csec.Spec.DataFrom {
		data, err := r.constructSecretDataFrom(ctx, &dataFrom)
		if err != nil {
			return expectedSecret, fmt.Errorf("spec.template.dataFrom[%d]: %w", i, err)
		}
		expectedSecret.Data = util.AppendMap(expectedSecret.Data, data)
	}

	// then load data keys from secrets
	for k, dataValueFrom := range csec.Spec.DataValueFrom {
		value, err := r.constructSecretDataValueFrom(ctx, &dataValueFrom)
		if err != nil {
			return expectedSecret, fmt.Errorf("spec.template.dataFrom.%s: %w", k, err)
		}
		if expectedSecret.Data == nil {
			expectedSecret.Data = map[string][]byte{}
		}
		expectedSecret.Data[k] = value
	}

	// lastly set data keys from ClusterSecret
	// (.stringData is not used here, as that's converted into .data in a webhook)
	expectedSecret.Data = util.AppendMap(expectedSecret.Data, csec.Spec.Template.Data)
	return expectedSecret, nil
}

func (r *ClusterSecretReconciler) constructSecretDataFrom(ctx context.Context, dataFrom *clustersecretiov2.DataFrom) (map[string][]byte, error) {
	if dataFrom == nil {
		return nil, fmt.Errorf("unexpected nil")
	}
	if dataFrom.SecretRef == nil {
		return nil, fmt.Errorf("field .secretRef must be set")
	}
	if dataFrom.SecretRef.Name == "" {
		return nil, fmt.Errorf("secretRef: field .name must be set")
	}
	if dataFrom.SecretRef.Namespace == "" {
		return nil, fmt.Errorf("secretRef: field .namespace must be set")
	}

	sec := &corev1.Secret{}
	name := types.NamespacedName{Name: dataFrom.SecretRef.Name, Namespace: dataFrom.SecretRef.Namespace}
	if err := r.Get(ctx, name, sec); err != nil {
		return nil, fmt.Errorf("get secret (%s) from namespace (%s): %w", dataFrom.SecretRef.Name, dataFrom.SecretRef.Namespace, err)
	}

	return sec.Data, nil
}

func (r *ClusterSecretReconciler) constructSecretDataValueFrom(ctx context.Context, dataValueFrom *clustersecretiov2.DataValueFrom) ([]byte, error) {
	if dataValueFrom == nil {
		return nil, fmt.Errorf("unexpected nil")
	}
	if dataValueFrom.SecretKeyRef == nil {
		return nil, fmt.Errorf("field .secretKeyRef must be set")
	}
	if dataValueFrom.SecretKeyRef.Name == "" {
		return nil, fmt.Errorf("secretKeyRef: field .name must be set")
	}
	if dataValueFrom.SecretKeyRef.Namespace == "" {
		return nil, fmt.Errorf("secretKeyRef: field .namespace must be set")
	}
	if dataValueFrom.SecretKeyRef.Key == "" {
		return nil, fmt.Errorf("secretKeyRef: field .key must be set")
	}

	sec := &corev1.Secret{}
	name := types.NamespacedName{Name: dataValueFrom.SecretKeyRef.Name, Namespace: dataValueFrom.SecretKeyRef.Namespace}
	if err := r.Get(ctx, name, sec); err != nil {
		return nil, fmt.Errorf("get secret (%s) from namespace (%s): %w", dataValueFrom.SecretKeyRef.Name, dataValueFrom.SecretKeyRef.Namespace, err)
	}

	value, ok := sec.Data[dataValueFrom.SecretKeyRef.Key]
	if !ok {
		return nil, fmt.Errorf("secret (%s) from namespace (%s) does not contain the data key (%s)", dataValueFrom.SecretKeyRef.Name, dataValueFrom.SecretKeyRef.Namespace, dataValueFrom.SecretKeyRef.Key)
	}

	return value, nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *ClusterSecretReconciler) SetupWithManager(mgr ctrl.Manager) error {
	if err := mgr.GetFieldIndexer().IndexField(context.Background(), &corev1.Secret{}, secretOwnerKey, func(rawObj client.Object) []string {
		// grab the secret object, extract the owner...
		job := rawObj.(*corev1.Secret)
		owner := metav1.GetControllerOf(job)
		if owner == nil {
			return nil
		}
		// ...make sure it's a ClusterSecret...
		if owner.APIVersion != apiGVStr || owner.Kind != "ClusterSecret" {
			return nil
		}
		// ...and if so, return it
		return []string{owner.Name}
	}); err != nil {
		return err
	}

	if err := mgr.GetFieldIndexer().IndexField(context.Background(), &clustersecretiov2.ClusterSecret{}, csecSecretRefKey, func(rawObj client.Object) []string {
		csec := rawObj.(*clustersecretiov2.ClusterSecret)
		names := make([]string, 0, len(csec.Spec.DataFrom))
		for _, dataFrom := range csec.Spec.DataFrom {
			if dataFrom.SecretRef != nil && dataFrom.SecretRef.Name != "" {
				names = append(names, dataFrom.SecretRef.Name)
			}
		}
		return names
	}); err != nil {
		return err
	}

	if err := mgr.GetFieldIndexer().IndexField(context.Background(), &clustersecretiov2.ClusterSecret{}, csecSecretKeyRefKey, func(rawObj client.Object) []string {
		csec := rawObj.(*clustersecretiov2.ClusterSecret)
		names := make([]string, 0, len(csec.Spec.DataValueFrom))
		for _, dataValueFrom := range csec.Spec.DataValueFrom {
			if dataValueFrom.SecretKeyRef != nil && dataValueFrom.SecretKeyRef.Name != "" {
				names = append(names, dataValueFrom.SecretKeyRef.Name)
			}
		}
		return names
	}); err != nil {
		return err
	}

	return ctrl.NewControllerManagedBy(mgr).
		For(&clustersecretiov2.ClusterSecret{}).
		Owns(&corev1.Secret{}).
		Watches(
			&corev1.Namespace{},
			handler.EnqueueRequestsFromMapFunc(r.findObjectsForNamespace),
			builder.WithPredicates(createdOrDeletedPredicate),
		).
		Watches(
			&corev1.Secret{},
			handler.EnqueueRequestsFromMapFunc(r.findObjectsForSecrets),
			builder.WithPredicates(predicate.ResourceVersionChangedPredicate{}),
		).
		Complete(r)
}

func (r *ClusterSecretReconciler) findObjectsForNamespace(ctx context.Context, obj client.Object) []reconcile.Request {
	ns := obj.(*corev1.Namespace)

	log := log.FromContext(ctx)
	attachedClusterSecrets := &clustersecretiov2.ClusterSecretList{}
	listOps := &client.ListOptions{}
	if err := r.List(ctx, attachedClusterSecrets, listOps); err != nil {
		return []reconcile.Request{}
	}

	requests := make([]reconcile.Request, 0, len(attachedClusterSecrets.Items))
	for _, item := range attachedClusterSecrets.Items {
		isMatch, err := matchesNamespace(item.Spec.NamespaceSelectorTerms, ns)
		if err != nil {
			log.Error(err, "unable to match ClusterSecret on namespace")
			continue
		}
		if !isMatch {
			continue
		}
		requests = append(requests, reconcile.Request{
			NamespacedName: types.NamespacedName{
				Name:      item.GetName(),
				Namespace: item.GetNamespace(),
			},
		})
	}
	return requests
}

func (r *ClusterSecretReconciler) findObjectsForSecrets(ctx context.Context, obj client.Object) []reconcile.Request {
	sec := obj.(*corev1.Secret)

	attachedClusterSecrets := &clustersecretiov2.ClusterSecretList{}
	listOps := &client.ListOptions{}
	if err := r.List(ctx, attachedClusterSecrets, listOps); err != nil {
		return []reconcile.Request{}
	}

	requests := make([]reconcile.Request, 0, len(attachedClusterSecrets.Items))
	for _, csec := range attachedClusterSecrets.Items {
		if isOwnedBy(&csec, sec) {
			// Already managed via the operator
			continue
		}

		expectedSecret, err := r.constructSecret(ctx, &csec)
		if err != nil && expectedSecret == nil {
			// Skip on error, unless we got a half-created secret
			continue
		}
		if sec.GetName() == expectedSecret.Name {
			requests = append(requests, reconcile.Request{
				NamespacedName: types.NamespacedName{
					Name:      csec.GetName(),
					Namespace: csec.GetNamespace(),
				},
			})
			continue
		}

		// check if used by .spec.template.dataFrom
		for _, dataFrom := range csec.Spec.DataFrom {
			if dataFrom.SecretRef == nil {
				continue
			}
			if dataFrom.SecretRef.Name != sec.GetName() || dataFrom.SecretRef.Namespace != sec.GetNamespace() {
				continue
			}
			requests = append(requests, reconcile.Request{
				NamespacedName: types.NamespacedName{
					Name:      csec.GetName(),
					Namespace: csec.GetNamespace(),
				},
			})
		}

		// check if used by .spec.template.dataValueFrom
		for _, dataValueFrom := range csec.Spec.DataValueFrom {
			if dataValueFrom.SecretKeyRef == nil {
				continue
			}
			if dataValueFrom.SecretKeyRef.Name != sec.GetName() || dataValueFrom.SecretKeyRef.Namespace != sec.GetNamespace() {
				continue
			}
			requests = append(requests, reconcile.Request{
				NamespacedName: types.NamespacedName{
					Name:      csec.GetName(),
					Namespace: csec.GetNamespace(),
				},
			})
		}
	}
	return requests
}

func isOwnedBy(parent, ref client.Object) bool {
	objKind := parent.GetObjectKind().GroupVersionKind()
	ownerRefs := ref.GetOwnerReferences()
	for _, ownerRef := range ownerRefs {
		if ownerRef.Kind == objKind.Kind && ownerRef.UID == parent.GetUID() {
			return true
		}
	}
	return false
}

var createdOrDeletedPredicate = predicate.Funcs{
	CreateFunc:  func(event.CreateEvent) bool { return true },
	DeleteFunc:  func(event.DeleteEvent) bool { return true },
	UpdateFunc:  func(event.UpdateEvent) bool { return false },
	GenericFunc: func(event.GenericEvent) bool { return false },
}
