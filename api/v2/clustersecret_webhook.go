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

package v2

import (
	"cmp"
	"regexp"
	"strconv"

	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/util/validation/field"
	ctrl "sigs.k8s.io/controller-runtime"
	logf "sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/webhook"
	"sigs.k8s.io/controller-runtime/pkg/webhook/admission"
)

// log is for logging in this package.
var clustersecretlog = logf.Log.WithName("clustersecret-resource")

// SetupWebhookWithManager will setup the manager to manage the webhooks
func (r *ClusterSecret) SetupWebhookWithManager(mgr ctrl.Manager) error {
	return ctrl.NewWebhookManagedBy(mgr).
		For(r).
		Complete()
}

// TODO(user): EDIT THIS FILE!  THIS IS SCAFFOLDING FOR YOU TO OWN!

//+kubebuilder:webhook:path=/mutate-clustersecret-io-v2-clustersecret,mutating=true,failurePolicy=fail,sideEffects=None,groups=clustersecret.io,resources=clustersecrets,verbs=create;update,versions=v2,name=mclustersecret.kb.io,admissionReviewVersions=v1

var _ webhook.Defaulter = &ClusterSecret{}

// Default implements webhook.Defaulter so a webhook will be registered for the type
func (r *ClusterSecret) Default() {
	clustersecretlog.Info("default", "name", r.Name)

	r.Spec.Template.Type = cmp.Or(r.Spec.Template.Type, "Opaque")

	if r.Spec.Template.StringData != nil {
		if r.Spec.Template.Data == nil {
			r.Spec.Template.Data = make(map[string][]byte, len(r.Spec.Template.StringData))
		}
		for k, v := range r.Spec.Template.StringData {
			r.Spec.Template.Data[k] = []byte(v)
		}
		r.Spec.Template.StringData = nil
	}

	if r.Status.ReadySecretsRatio == "" {
		r.Status.ReadySecretsRatio = "0/0"
	}
}

// TODO(user): change verbs to "verbs=create;update;delete" if you want to enable deletion validation.
//+kubebuilder:webhook:path=/validate-clustersecret-io-v2-clustersecret,mutating=false,failurePolicy=fail,sideEffects=None,groups=clustersecret.io,resources=clustersecrets,verbs=create;update,versions=v2,name=vclustersecret.kb.io,admissionReviewVersions=v1

var _ webhook.Validator = &ClusterSecret{}

// ValidateCreate implements webhook.Validator so a webhook will be registered for the type
func (r *ClusterSecret) ValidateCreate() (admission.Warnings, error) {
	clustersecretlog.Info("validate create", "name", r.Name)

	return r.validate()
}

// ValidateUpdate implements webhook.Validator so a webhook will be registered for the type
func (r *ClusterSecret) ValidateUpdate(old runtime.Object) (admission.Warnings, error) {
	clustersecretlog.Info("validate update", "name", r.Name)

	return r.validate()
}

func (r *ClusterSecret) validate() (admission.Warnings, error) {
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

var (
	validMatchFieldOperators = []string{
		string(NamespaceSelectorOpIn),
		string(NamespaceSelectorOpNotIn),
		string(NamespaceSelectorOpInRegex),
		string(NamespaceSelectorOpNotInRegex),
		string(NamespaceSelectorOpExists),
		string(NamespaceSelectorOpDoesNotExist),
		string(NamespaceSelectorOpGt),
		string(NamespaceSelectorOpLt),
	}
)

func validateMatchField(expr NamespaceSelectorRequirement, path *field.Path) error {
	switch expr.Operator {
	case NamespaceSelectorOpIn, NamespaceSelectorOpNotIn:
		if len(expr.Values) == 0 {
			return field.Invalid(path.Child("values"), expr.Values, "must have one element")
		}

	case NamespaceSelectorOpInRegex, NamespaceSelectorOpNotInRegex:
		if len(expr.Values) == 0 {
			return field.Invalid(path.Child("values"), expr.Values, "must have one element")
		}

		for i, v := range expr.Values {
			if _, err := regexp.Compile(v); err != nil {
				return field.Invalid(path.Child("values").Index(i), expr.Values, err.Error())
			}
		}

	case NamespaceSelectorOpLt, NamespaceSelectorOpGt:
		if len(expr.Values) == 0 {
			return field.Invalid(path.Child("values"), expr.Values, "must have one element")
		}
		if len(expr.Values) > 1 {
			return field.TooMany(path.Child("values"), len(expr.Values), 1)
		}

		if _, err := strconv.ParseInt(expr.Values[0], 10, 0); err != nil {
			return field.Invalid(path.Child("values").Index(0), expr.Values[0], err.Error())
		}

	case NamespaceSelectorOpExists, NamespaceSelectorOpDoesNotExist:
		if len(expr.Values) > 0 {
			return field.TooMany(path.Child("values"), len(expr.Values), 0)
		}

	default:
		return field.NotSupported(path.Child("operator"), expr.Operator, validMatchFieldOperators)
	}
	return nil
}

// ValidateDelete implements webhook.Validator so a webhook will be registered for the type
func (r *ClusterSecret) ValidateDelete() (admission.Warnings, error) {
	clustersecretlog.Info("validate delete", "name", r.Name)

	// TODO(user): fill in your validation logic upon object deletion.
	return nil, nil
}
