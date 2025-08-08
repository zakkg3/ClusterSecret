// SPDX-FileCopyrightText: 2020 The Kubernetes Authors
// SPDX-FileCopyrightText: 2024 Kalle Fagerberg
// SPDX-FileCopyrightText: 2024 Nicolas Kowenski
// SPDX-License-Identifier: MIT

// Package v1 contains API Schema definitions for the  v1 API group
// +kubebuilder:object:generate=true
// +groupName=clustersecret.io
package v1

import (
	"k8s.io/apimachinery/pkg/runtime/schema"
	"sigs.k8s.io/controller-runtime/pkg/scheme"
)

var (
	// GroupVersion is group version used to register these objects
	GroupVersion = schema.GroupVersion{Group: "clustersecret.io", Version: "v1"}

	// SchemeBuilder is used to add go types to the GroupVersionKind scheme
	SchemeBuilder = &scheme.Builder{GroupVersion: GroupVersion}

	// AddToScheme adds the types in this group-version to the given scheme.
	AddToScheme = SchemeBuilder.AddToScheme
)
