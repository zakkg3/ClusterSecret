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
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// ClusterSecretSpec defines the desired state of ClusterSecret
type ClusterSecretSpec struct {
	// NamespaceSelectorTerms defines the list of namespace selection
	// criteria for where to place the Secrets.
	//
	//   - If the affinity requirements specified by this field are not met,
	//     the secret will not be added to the namespace.
	//   - If the affinity requirements specified by this field cease to be met
	//     at some point during execution (e.g. due to an update),
	//     the operator will try to eventually evict the secret
	//     from its namespace.
	//
	// The terms in this list are ORed together.
	// +optional
	NamespaceSelectorTerms []NamespaceSelectorTerm `json:"namespaceSelectorTerm"`

	// Template of the Kubernetes Secret to replicate across the namespaces.
	Template SecretTemplate `json:"template"`

	// DataFrom sets a list of sources where the data can be created from.
	// This data is loaded first, and is overridden by .spec.template.data.* and .spec.template.dataValueFrom.* fields.
	// +optional
	// +nullable
	DataFrom []DataFrom `json:"dataFrom,omitempty"`

	// DataValueFrom sets a map of data keys and where to load their data from.
	// This data is loaded after .spec.template.dataFrom, but is overridden by the .spec.template.data.* fields.
	// +optional
	// +nullable
	DataValueFrom map[string]DataValueFrom `json:"dataValueFrom,omitempty"`
}

// A null or empty namespace selector term matches no objects.
// The requirements in matchExpressions and matchFields are ANDed together.
// +structType=atomic
type NamespaceSelectorTerm struct {
	// A list of namespace selector requirements by namespace's labels.
	// The requirements in this list are ANDed together.
	// +optional
	MatchExpressions []NamespaceSelectorRequirement `json:"matchExpressions,omitempty"`
	// A list of namespace selector requirements by namespace's fields.
	// The requirements in this list are ANDed together.
	// +optional
	MatchFields []NamespaceSelectorRequirement `json:"matchFields,omitempty"`
}

// A namespace selector requirement is a selector that contains values, a key,
// and an operator that relates the key and values.
type NamespaceSelectorRequirement struct {
	// The label key that the selector applies to.
	Key string `json:"key"`

	// Represents a key's relationship to a set of values.
	// Valid operators are In, NotIn, InRegex, NotInRegex, Exists, DoesNotExist, Gt, and Lt.
	Operator NamespaceSelectorOperator `json:"operator"`

	// An array of string values.
	//
	//   - If the operator is In or NotIn,
	//     the values array must be non-empty.
	//   - If the operator is InRegex or NotInRegex,
	//     the values array must be non-empty,
	//     which will be interpreted as Go Regex patterns.
	//     (https://pkg.go.dev/regexp/syntax)
	//   - If the operator is Exists or DoesNotExist,
	//     the values array must be empty.
	//   - If the operator is Gt or Lt,
	//     the values array must have a single element,
	//     which will be interpreted as an integer.
	//
	// This array is replaced during a strategic merge patch.
	// +optional
	Values []string `json:"values,omitempty"`
}

// A namespace selector operator is the set of operators that can be used in
// a namespace selector requirement.
// +kubebuilder:validation:Enum={In,NotIn,InRegex,NotInRegex,Exists,DoesNotExist,Gt,Lt}
type NamespaceSelectorOperator string

const (
	NamespaceSelectorOpIn           NamespaceSelectorOperator = "In"
	NamespaceSelectorOpNotIn        NamespaceSelectorOperator = "NotIn"
	NamespaceSelectorOpInRegex      NamespaceSelectorOperator = "InRegex"
	NamespaceSelectorOpNotInRegex   NamespaceSelectorOperator = "NotInRegex"
	NamespaceSelectorOpExists       NamespaceSelectorOperator = "Exists"
	NamespaceSelectorOpDoesNotExist NamespaceSelectorOperator = "DoesNotExist"
	NamespaceSelectorOpGt           NamespaceSelectorOperator = "Gt"
	NamespaceSelectorOpLt           NamespaceSelectorOperator = "Lt"
)

// SecretTemplate defines the expected state of the Secret.
type SecretTemplate struct {
	// Metadata of the Kubernetes Secret. Only supports a subset of all metadata fields.
	// +optional
	Metadata *SecretTemplateMetadata `json:"metadata,omitempty"`

	// Data contains the secret data. Each key must consist of alphanumeric
	// characters, '-', '_' or '.'. The serialized form of the secret data is a
	// base64 encoded string, representing the arbitrary (possibly non-string)
	// data value here. Described in https://tools.ietf.org/html/rfc4648#section-4
	// +optional
	// +nullable
	Data map[string][]byte `json:"data,omitempty"`

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
}

// DataFrom defines a source to read additional secret data from,
// similar to a container's .envFrom field.
type DataFrom struct {
	// SecretRef from where to load additional data from.
	// +optional
	SecretRef *SecretReference `json:"secretRef,omitempty"`
}

// SecretReference represents a Secret Reference. It has enough information to retrieve secret
// in any namespace
// +structType=atomic
type SecretReference struct {
	// Name is unique within a namespace to reference a secret resource.
	Name string `json:"name,omitempty"`
	// Namespace defines the space within which the secret name must be unique.
	Namespace string `json:"namespace,omitempty"`
}

// DataValueFrom defines a source to read a specific secret data field/key from,
// similar to a container's .env[*].valueFrom field.
type DataValueFrom struct {
	// SecretKeyRef from where to load additional data field from.
	// +optional
	SecretKeyRef *SecretKeyReference `json:"secretKeyRef,omitempty"`
}

// SecretKeyReference represents a Secret Reference. It has enough information to retrieve secret
// in any namespace and target a specific field in that secret.
// +structType=atomic
type SecretKeyReference struct {
	// Name is unique within a namespace to reference a secret resource.
	Name string `json:"name,omitempty"`
	// Namespace defines the space within which the secret name must be unique.
	Namespace string `json:"namespace,omitempty"`
	// Key is which Secret key in its data to reference.
	Key string `json:"key,omitempty"`
}

// SecretTemplateMetadata defines template data for the Kubernetes Secret
// that the operator will create.
type SecretTemplateMetadata struct {
	// Name of the Kubernetes Secret to create.
	// By default uses the name of the ClusterSecret resource.
	Name string `json:"name,omitempty"`

	// Labels of the Kubernetes Secret to create.
	Labels map[string]string `json:"labels,omitempty"`

	// Annotations of the Kubernetes Secret to create.
	Annotations map[string]string `json:"annotations,omitempty"`
}

// ClusterSecretStatus defines the observed state of ClusterSecret
type ClusterSecretStatus struct {
	Conditions []metav1.Condition `json:"conditions,omitempty" patchStrategy:"merge" patchMergeKey:"type"`

	// DataCount is the number of fields in the data.
	// +optional
	DataCount int32 `json:"dataCount"`

	// MatchingNamespaces is a list of namespaces the secret will try replicate to,
	// based on the current namespaces in the cluster and the ClusterSecret's
	// filtering.
	// +optional
	MatchingNamespaces []string `json:"matchingNamespaces"`

	// MatchingNamespacesCount is the target number of namespaces the secret will try replicate to,
	// based on the current namespaces in the cluster and the ClusterSecret's
	// filtering.
	// +optional
	MatchingNamespacesCount int32 `json:"matchingNamespacesCount"`

	// ReadySecretsCount is the number of secrets that currently exist.
	// +optional
	ReadySecretsCount int32 `json:"readySecretsCount"`

	// ReadySecretsRatio is a string like "3/3" or "0/3" that shows how many
	// secrets are ready (the first number) out of how many secrets this ClusterSecret
	// aims to have (the second number).
	// +optional
	ReadySecretsRatio string `json:"readySecretsRatio"`
}

// ClusterSecretStatusNamespace defines the observed state of a specific namespace.
type ClusterSecretStatusNamespace struct {
	// Namespace that the operator has attempted to replicate into.
	Namespace string `json:"namespace"`

	// Secret that the operator has replicated
	// +nullable
	Secret *corev1.ObjectReference `json:"secret,omitempty"`

	// LastUpdateTime of this Kubernetes Secret in the given namespace.
	LastUpdateTime metav1.Time `json:"lastUpdateTime"`

	// Status of the Secret creation/replication.
	Status SecretStatus `json:"status"`

	// Error message from when failing to replicate the Secret.
	Error string `json:"error,omitempty"`
}

// SecretStatus defines the different statuses a secret can have.
type SecretStatus string

const (
	SecretStatusReady        SecretStatus = "Ready"
	SecretStatusSkipped      SecretStatus = "Skipped"
	SecretStatusFailedSync   SecretStatus = "FailedSync"
	SecretStatusFailedDelete SecretStatus = "FailedDelete"
)

//+kubebuilder:object:root=true
//+kubebuilder:subresource:status
//+kubebuilder:resource:scope=Cluster,shortName=csec
//+kubebuilder:storageversion
//+kubebuilder:printcolumn:name=Ready,description=Number of ready secrets vs how many secrets it attempts to create,JSONPath=.status.readySecretsRatio,type=string
//+kubebuilder:printcolumn:name=Type,description=Secret Type,JSONPath=.spec.template.type,type=string
//+kubebuilder:printcolumn:name=Data,description=Number of data fields in the secret,JSONPath=.status.dataCount,type=integer,format=int32
//+kubebuilder:printcolumn:name=Age,description=Timestamp of when the ClusterSecret resource was created,type=date,JSONPath=.metadata.creationTimestamp

// ClusterSecret is the Schema for the clustersecrets API
type ClusterSecret struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   ClusterSecretSpec   `json:"spec,omitempty"`
	Status ClusterSecretStatus `json:"status,omitempty"`
}

// Hub marks this type as a conversion hub.
func (*ClusterSecret) Hub() {}

//+kubebuilder:object:root=true

// ClusterSecretList contains a list of ClusterSecret
type ClusterSecretList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []ClusterSecret `json:"items"`
}

func init() {
	SchemeBuilder.Register(&ClusterSecret{}, &ClusterSecretList{})
}
