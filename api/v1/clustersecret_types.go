// SPDX-FileCopyrightText: 2020 The Kubernetes Authors
// SPDX-FileCopyrightText: 2024 Kalle Fagerberg
// SPDX-FileCopyrightText: 2024 Nicolas Kowenski
// SPDX-License-Identifier: MIT

package v1

import (
	"encoding/json"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:scope=Cluster,shortName=csec
// +kubebuilder:deprecatedversion:warning="The clustersecret.io/v1 apiVersion is no longer supported. Please migrate over to clustersecret.io/v2: https://clustersecret.io/update/v1-to-v2/"
// +kubebuilder:printcolumn:name=Type,description=Secret Type,JSONPath=.type,type=string
// +kubebuilder:printcolumn:name=Age,description=Timestamp of when the ClusterSecret resource was created,type=date,JSONPath=.metadata.creationTimestamp

// ClusterSecret is the Schema for the clustersecrets API
type ClusterSecret struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	// MatchNamespaces is a list of RegEx patterns on namespaces to replicate
	// the Kubernetes Secret to.
	// +kubebuilder:example:={{prod-.*}}
	// +listType=atomic
	MatchNamespace []NamespaceRegex `json:"matchNamespace,omitempty"`

	// AvoidNamespaces is a list of RegEx patterns on namespaces to skip
	// replication of the Kubernetes Secret to.
	// These patterns has higher precedence than the MatchNamespaces patterns.
	// +kubebuilder:example:={{kube-.*, default}}
	// +listType=atomic
	AvoidNamespaces []NamespaceRegex `json:"avoidNamespaces,omitempty"`

	// Data contains the secret data. Each key must consist of alphanumeric
	// characters, '-', '_' or '.'. The serialized form of the secret data is a
	// base64 encoded string, representing the arbitrary (possibly non-string)
	// data value here. Described in https://tools.ietf.org/html/rfc4648#section-4
	// +kubebuilder:validation:Schemaless
	// +kubebuilder:pruning:PreserveUnknownFields
	// +optional
	// +nullable
	Data json.RawMessage `json:"data,omitempty"`

	// StringData allows specifying non-binary secret data in string form.
	// It is provided as a write-only input field for convenience.
	// All keys and values are merged into the data field on write, overwriting any existing values.
	// The stringData field is never output when reading from the API.
	// +optional
	// +nullable
	StringData map[string]string `json:"stringData,omitempty"`

	// Type of the Kubernetes Secret.
	// Used to facilitate programmatic handling of secret data.
	// More info: https://kubernetes.io/docs/concepts/configuration/secret/#secret-types
	// +kubebuilder:default:=Opaque
	// +kubebuilder:example:={Opaque, kubernetes.io/dockerconfigjson, kubernetes.io/dockercfg, kubernetes.io/basic-auth, kubernetes.io/ssh-auth, kubernetes.io/tls, kubernetes.io/service-account-token, bootstrap.kubernetes.io/token}
	Type corev1.SecretType `json:"type,omitempty"`

	Status ClusterSecretStatus `json:"status,omitempty"`
}

// NamespaceRegex defines a regular expression pattern used to filter namespaces.
// +kubebuilder:validation:Format:=regex
type NamespaceRegex string

// ClusterSecretStatus defines the observed state of ClusterSecret
type ClusterSecretStatus struct {
	// +optional
	CreateFn CreateFnStatus `json:"create_fn"`
	// +optional
	Kopf KopfStatus `json:"kopf"`
}

type CreateFnStatus struct {
	// +optional
	SyncedNs []string `json:"syncedns"`
}

type KopfStatus struct {
	// +optional
	KopfProgressStatus `json:"progress"`
}

type KopfProgressStatus struct{}

// +kubebuilder:object:root=true

// ClusterSecretList contains a list of ClusterSecret
type ClusterSecretList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []ClusterSecret `json:"items"`
}

func init() {
	SchemeBuilder.Register(&ClusterSecret{}, &ClusterSecretList{})
}
