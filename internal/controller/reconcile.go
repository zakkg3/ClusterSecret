package controller

import (
	"context"
	"fmt"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"

	clustersecretiov2 "github.com/zakkg3/ClusterSecret/api/v2"
)

func (r *ClusterSecretReconciler) reconcileOutOfDateSecret(ctx context.Context, req ctrl.Request, sec, expectedSecret *corev1.Secret) error {
	log := log.FromContext(ctx)

	// Get csec Instance
	csec := &clustersecretiov2.ClusterSecret{}

	if err := r.Get(ctx, req.NamespacedName, csec); err != nil {
		return client.IgnoreNotFound(err)
	}

	switch {
	case sec.Name != expectedSecret.Name:
		if err := r.Delete(ctx, sec, client.PropagationPolicy(metav1.DeletePropagationBackground)); client.IgnoreNotFound(err) != nil {
			return fmt.Errorf("renaming secret: unable to delete old secret: %w", err)
		}
		log.V(1).Info("deleted old secret to rename secret", "secret", sec, "newName", expectedSecret.Name)

		newSecret := expectedSecret.DeepCopy()
		newSecret.Namespace = sec.Namespace
		newSecret.Annotations[annotationLastSync] = time.Now().Format(annotationLastSyncFormat)
		if err := ctrl.SetControllerReference(csec, newSecret, r.Scheme); err != nil {
			return fmt.Errorf("renaming secret: unable to construct new secret: %w", err)
		}

		if err := r.Create(ctx, newSecret); err != nil {
			return fmt.Errorf("renaming secret: unable to create new secret: %w", err)
		}
		log.V(0).Info("renamed secret", "secret", newSecret)
		return nil

	default:
		expectedCopy := expectedSecret.DeepCopy()
		sec.Labels = expectedCopy.Labels
		sec.Annotations = expectedCopy.Annotations
		sec.Annotations[annotationLastSync] = time.Now().Format(annotationLastSyncFormat)
		sec.Data = expectedCopy.Data
		sec.Type = expectedCopy.Type

		if err := r.Update(ctx, sec); err != nil {
			return fmt.Errorf("updating secret: unable to update secret: %w", err)
		}
		log.V(0).Info("updated secret", "secret", sec)
		return nil
	}
}

func (r *ClusterSecretReconciler) reconcileMissingSecret(ctx context.Context, req ctrl.Request, ns string, expectedSecret *corev1.Secret) error {
	log := log.FromContext(ctx)

	// Get csec Instance
	csec := &clustersecretiov2.ClusterSecret{}

	if err := r.Get(ctx, req.NamespacedName, csec); err != nil {
		return client.IgnoreNotFound(err)
	}

	newSecret := expectedSecret.DeepCopy()
	newSecret.Namespace = ns
	newSecret.Annotations[annotationLastSync] = time.Now().Format(annotationLastSyncFormat)

	oldSecret := &corev1.Secret{}
	// NOTE: intentionally checking "err == nil" here instead of "err != nil"
	if err := r.Get(ctx, client.ObjectKeyFromObject(newSecret), oldSecret); err == nil {
		// There's one already here.
		// Check if it was created by old Python/kopf-based ClusterSecret operator
		// (this new Go-based operator relies on ownerReference instead of annotation)
		if createdBy, ok := oldSecret.Annotations[annotationCreatedBy]; ok && createdBy == annotationCreatedByValue {
			if err := r.Delete(ctx, oldSecret); client.IgnoreNotFound(err) != nil {
				return fmt.Errorf("replace existing secret that was already managed by ClusterSecret: %w", err)
			}
			log.V(1).Info("replaced previous secret that was probably managed by older version of ClusterSecret", "oldSecret", oldSecret)
		}
	}

	if err := ctrl.SetControllerReference(csec, newSecret, r.Scheme); err != nil {
		return fmt.Errorf("create secret: unable to construct secret: %w", err)
	}

	if err := r.Create(ctx, newSecret); err != nil {
		return fmt.Errorf("unable to create secret: %w", err)
	}
	log.V(0).Info("created secret", "secret", newSecret)

	return nil
}
