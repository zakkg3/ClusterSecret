// SPDX-FileCopyrightText: 2020 The Kubernetes Authors
// SPDX-FileCopyrightText: 2024 Kalle Fagerberg
// SPDX-FileCopyrightText: 2024 Nicolas Kowenski
// SPDX-License-Identifier: MIT

package controller

import (
	"context"
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	"k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

	clustersecretiov2 "github.com/zakkg3/ClusterSecret/api/v2"
)

var _ = Describe("ClusterSecret Controller", func() {
	// The controller is running in the background,
	// so we test by querying the k8s client instead of running
	// [ClusterSecretReconciler.Reconcile] manually.
	// See: https://github.com/kubernetes-sigs/kubebuilder/blob/v4.7.1/docs/book/src/cronjob-tutorial/testdata/project/internal/controller/cronjob_controller_test.go
	const (
		ClusterSecretName = "test-resource"

		timeout  = time.Second * 10
		duration = time.Second * 10
		interval = time.Millisecond * 250
	)

	Context("When reconciling a resource", func() {
		// TODO: convert to test code that looks more like this: https://github.com/kubernetes-sigs/kubebuilder/blob/v4.7.1/docs/book/src/cronjob-tutorial/testdata/project/internal/controller/cronjob_controller_test.go
		ctx := context.Background()

		typeNamespacedName := types.NamespacedName{Name: ClusterSecretName}
		clustersecret := &clustersecretiov2.ClusterSecret{}

		BeforeEach(func() {
			By("creating the custom resource for the Kind ClusterSecret")
			err := k8sClient.Get(ctx, typeNamespacedName, clustersecret)
			if err != nil && errors.IsNotFound(err) {
				resource := &clustersecretiov2.ClusterSecret{
					ObjectMeta: metav1.ObjectMeta{
						Name:      ClusterSecretName,
						Namespace: "default",
					},
					// TODO(user): Specify other spec details if needed.
				}
				Expect(k8sClient.Create(ctx, resource)).To(Succeed())
			}
		})

		AfterEach(func() {
			// TODO(user): Cleanup logic after each test, like removing the resource instance.
			resource := &clustersecretiov2.ClusterSecret{}
			err := k8sClient.Get(ctx, typeNamespacedName, resource)
			Expect(err).NotTo(HaveOccurred())

			By("Cleanup the specific resource instance ClusterSecret")
			Expect(k8sClient.Delete(ctx, resource)).To(Succeed())
		})
		It("should successfully reconcile the resource", func() {
			By("Reconciling the created resource")
			controllerReconciler := &ClusterSecretReconciler{
				Client: k8sManager.GetClient(),
				Scheme: k8sManager.GetScheme(),
			}

			_, err := controllerReconciler.Reconcile(ctx, reconcile.Request{
				NamespacedName: typeNamespacedName,
			})
			Expect(err).NotTo(HaveOccurred())
			// TODO(user): Add more specific assertions depending on your controller's reconciliation logic.
			// Example: If you expect a certain status condition after reconciliation, verify it here.
		})
	})
})
