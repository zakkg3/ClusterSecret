// SPDX-FileCopyrightText: 2020 The Kubernetes Authors
// SPDX-FileCopyrightText: 2024 Kalle Fagerberg
// SPDX-FileCopyrightText: 2024 Nicolas Kowenski
// SPDX-License-Identifier: MIT

package v2

import (
	"cmp"
	"context"
	"fmt"
	"regexp"
	"strconv"

	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/util/validation/field"
	ctrl "sigs.k8s.io/controller-runtime"
	logf "sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/webhook"
	"sigs.k8s.io/controller-runtime/pkg/webhook/admission"

	clustersecretiov2 "github.com/zakkg3/ClusterSecret/api/v2"
)

// nolint:unused
// log is for logging in this package.
var clustersecretlog = logf.Log.WithName("clustersecret-resource")

// SetupClusterSecretWebhookWithManager registers the webhook for ClusterSecret in the manager.
func SetupClusterSecretWebhookWithManager(mgr ctrl.Manager) error {
	return ctrl.NewWebhookManagedBy(mgr).For(&clustersecretiov2.ClusterSecret{}).
		WithValidator(&ClusterSecretCustomValidator{}).
		WithDefaulter(&ClusterSecretCustomDefaulter{}).
		Complete()
}

// TODO(user): EDIT THIS FILE!  THIS IS SCAFFOLDING FOR YOU TO OWN!

// +kubebuilder:webhook:path=/mutate-clustersecret-io-v2-clustersecret,mutating=true,failurePolicy=fail,sideEffects=None,groups=clustersecret.io,resources=clustersecrets,verbs=create;update,versions=v2,name=mclustersecret-v2.kb.io,admissionReviewVersions=v1

// ClusterSecretCustomDefaulter struct is responsible for setting default values on the custom resource of the
// Kind ClusterSecret when those are created or updated.
//
// NOTE: The +kubebuilder:object:generate=false marker prevents controller-gen from generating DeepCopy methods,
// as it is used only for temporary operations and does not need to be deeply copied.
type ClusterSecretCustomDefaulter struct {
	// TODO(user): Add more fields as needed for defaulting
}

var _ webhook.CustomDefaulter = &ClusterSecretCustomDefaulter{}

// Default implements webhook.CustomDefaulter so a webhook will be registered for the Kind ClusterSecret.
func (d *ClusterSecretCustomDefaulter) Default(ctx context.Context, obj runtime.Object) error {
	clustersecret, ok := obj.(*clustersecretiov2.ClusterSecret)

	if !ok {
		return fmt.Errorf("expected an ClusterSecret object but got %T", obj)
	}
	clustersecretlog.Info("Defaulting for ClusterSecret", "name", clustersecret.GetName())

	clustersecret.Spec.Template.Type = cmp.Or(clustersecret.Spec.Template.Type, "Opaque")

	if clustersecret.Spec.Template.StringData != nil {
		if clustersecret.Spec.Template.Data == nil {
			clustersecret.Spec.Template.Data = make(map[string][]byte, len(clustersecret.Spec.Template.StringData))
		}
		for k, v := range clustersecret.Spec.Template.StringData {
			clustersecret.Spec.Template.Data[k] = []byte(v)
		}
		clustersecret.Spec.Template.StringData = nil
	}

	if clustersecret.Status.ReadySecretsRatio == "" {
		clustersecret.Status.ReadySecretsRatio = "0/0"
	}

	return nil
}

// NOTE: The 'path' attribute must follow a specific pattern and should not be modified directly here.
// Modifying the path for an invalid path can cause API server errors; failing to locate the webhook.
// +kubebuilder:webhook:path=/validate-clustersecret-io-v2-clustersecret,mutating=false,failurePolicy=fail,sideEffects=None,groups=clustersecret.io,resources=clustersecrets,verbs=create;update,versions=v2,name=vclustersecret-v2.kb.io,admissionReviewVersions=v1

// ClusterSecretCustomValidator struct is responsible for validating the ClusterSecret resource
// when it is created, updated, or deleted.
//
// NOTE: The +kubebuilder:object:generate=false marker prevents controller-gen from generating DeepCopy methods,
// as this struct is used only for temporary operations and does not need to be deeply copied.
type ClusterSecretCustomValidator struct {
	// TODO(user): Add more fields as needed for validation
}

var _ webhook.CustomValidator = &ClusterSecretCustomValidator{}

// ValidateCreate implements webhook.CustomValidator so a webhook will be registered for the type ClusterSecret.
func (v *ClusterSecretCustomValidator) ValidateCreate(ctx context.Context, obj runtime.Object) (admission.Warnings, error) {
	clustersecret, ok := obj.(*clustersecretiov2.ClusterSecret)
	if !ok {
		return nil, fmt.Errorf("expected a ClusterSecret object but got %T", obj)
	}
	clustersecretlog.Info("Validation for ClusterSecret upon creation", "name", clustersecret.GetName())

	return v.validate(clustersecret)
}

// ValidateUpdate implements webhook.CustomValidator so a webhook will be registered for the type ClusterSecret.
func (v *ClusterSecretCustomValidator) ValidateUpdate(ctx context.Context, oldObj, newObj runtime.Object) (admission.Warnings, error) {
	clustersecret, ok := newObj.(*clustersecretiov2.ClusterSecret)
	if !ok {
		return nil, fmt.Errorf("expected a ClusterSecret object for the newObj but got %T", newObj)
	}
	clustersecretlog.Info("Validation for ClusterSecret upon update", "name", clustersecret.GetName())

	return v.validate(clustersecret)
}

func (v *ClusterSecretCustomValidator) validate(r *clustersecretiov2.ClusterSecret) (admission.Warnings, error) {
	path := field.NewPath("spec", "nodeSelectorTerms")
	for termIdx, term := range r.Spec.NamespaceSelectorTerms {
		termPath := path.Index(termIdx)
		for exprIdx, expr := range term.MatchFields {
			exprPath := termPath.Child("matchFields").Index(exprIdx)
			if err := validateMatchField(expr, exprPath); err != nil {
				return nil, err
			}
		}
		for exprIdx, expr := range term.MatchExpressions {
			exprPath := termPath.Child("matchExpressions").Index(exprIdx)
			if err := validateMatchField(expr, exprPath); err != nil {
				return nil, err
			}
		}
	}

	return nil, nil
}

var validMatchFieldOperators = []string{
	string(clustersecretiov2.NamespaceSelectorOpIn),
	string(clustersecretiov2.NamespaceSelectorOpNotIn),
	string(clustersecretiov2.NamespaceSelectorOpInRegex),
	string(clustersecretiov2.NamespaceSelectorOpNotInRegex),
	string(clustersecretiov2.NamespaceSelectorOpExists),
	string(clustersecretiov2.NamespaceSelectorOpDoesNotExist),
	string(clustersecretiov2.NamespaceSelectorOpGt),
	string(clustersecretiov2.NamespaceSelectorOpLt),
}

func validateMatchField(expr clustersecretiov2.NamespaceSelectorRequirement, path *field.Path) error {
	switch expr.Operator {
	case clustersecretiov2.NamespaceSelectorOpIn, clustersecretiov2.NamespaceSelectorOpNotIn:
		if len(expr.Values) == 0 {
			return field.Invalid(path.Child("values"), expr.Values, "must have one element")
		}

	case clustersecretiov2.NamespaceSelectorOpInRegex, clustersecretiov2.NamespaceSelectorOpNotInRegex:
		if len(expr.Values) == 0 {
			return field.Invalid(path.Child("values"), expr.Values, "must have one element")
		}

		for i, v := range expr.Values {
			if _, err := regexp.Compile(v); err != nil {
				return field.Invalid(path.Child("values").Index(i), expr.Values, err.Error())
			}
		}

	case clustersecretiov2.NamespaceSelectorOpLt, clustersecretiov2.NamespaceSelectorOpGt:
		if len(expr.Values) == 0 {
			return field.Invalid(path.Child("values"), expr.Values, "must have one element")
		}
		if len(expr.Values) > 1 {
			return field.TooMany(path.Child("values"), len(expr.Values), 1)
		}

		if _, err := strconv.ParseInt(expr.Values[0], 10, 0); err != nil {
			return field.Invalid(path.Child("values").Index(0), expr.Values[0], err.Error())
		}

	case clustersecretiov2.NamespaceSelectorOpExists, clustersecretiov2.NamespaceSelectorOpDoesNotExist:
		if len(expr.Values) > 0 {
			return field.TooMany(path.Child("values"), len(expr.Values), 0)
		}

	default:
		return field.NotSupported(path.Child("operator"), expr.Operator, validMatchFieldOperators)
	}
	return nil
}

// ValidateDelete implements webhook.CustomValidator so a webhook will be registered for the type ClusterSecret.
func (v *ClusterSecretCustomValidator) ValidateDelete(ctx context.Context, obj runtime.Object) (admission.Warnings, error) {
	clustersecret, ok := obj.(*clustersecretiov2.ClusterSecret)
	if !ok {
		return nil, fmt.Errorf("expected a ClusterSecret object but got %T", obj)
	}
	clustersecretlog.Info("Validation for ClusterSecret upon deletion", "name", clustersecret.GetName())

	// TODO(user): fill in your validation logic upon object deletion.

	return nil, nil
}
