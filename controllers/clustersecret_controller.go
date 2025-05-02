/*
Copyright 2022.

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

package controllers

import (
	"context"

	"k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	ctrllog "sigs.k8s.io/controller-runtime/pkg/log"

	v1 "k8s.io/api/core/v1"

	cachev1alpha1 "github.com/zakkg3/ClusterSecret/api/v1alpha1"
)

// ClusterSecretReconciler reconciles a ClusterSecret object
type ClusterSecretReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

//+kubebuilder:rbac:groups=cache.clustersecret.io,resources=clustersecrets,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=cache.clustersecret.io,resources=clustersecrets/status,verbs=get;update;patch
//+kubebuilder:rbac:groups=cache.clustersecret.io,resources=clustersecrets/finalizers,verbs=update

//  Manage secrets
//+kubebuilder:rbac:groups=core,resources=secrets,verbs=list;watch;get;patch;create;delete

// Warching new namespaces
//+kubebuilder:rbac:groups=apps,resources=namespace,verbs=list;watch;get;update

func (r *ClusterSecretReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	log := ctrllog.FromContext(ctx)
	log.V(1).Info("Clustersecret Reconcilier Starting DEBUG")
	log.Info("Clustersecret Reconcilier Starting INFO ")
	// get csec Instance
	csec := &cachev1alpha1.ClusterSecret{}
	err := r.Get(ctx, req.NamespacedName, csec)
	if err != nil {
		if errors.IsNotFound(err) {
			// Request object not found, could have been deleted after reconcile request.
			// Owned objects are automatically garbage collected. For additional cleanup logic use finalizers.
			// Return and don't requeue
			log.Info("ClusterSecret resource not found. Ignoring since object must be deleted")
			return ctrl.Result{}, nil
		}
		// Error reading the object - requeue the request.
		log.Error(err, "Failed to get ClusterSecret")
		return ctrl.Result{}, err
	}
	// End Get csec Instance

	log.V(1).Info("Reconcilier Ended Ok")
	return ctrl.Result{}, nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *ClusterSecretReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&cachev1alpha1.ClusterSecret{}).
		Owns(&v1.Secret{}). //, builder.OnlyMetadata).
		Complete(r)
}
