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

package v1

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"

	"sigs.k8s.io/controller-runtime/pkg/conversion"

	clustersecretiov2 "github.com/zakkg3/CsGo/api/v2"
	"github.com/zakkg3/CsGo/internal/util"
)

var (
	skipAnnotationPrefixes = []string{
		"kopf.zalando.org",
		"kubectl.kubernetes.io",
	}
)

// ConvertTo converts this ClusterSecret to the Hub version (v2).
func (src *ClusterSecret) ConvertTo(dstRaw conversion.Hub) error {
	dst := dstRaw.(*clustersecretiov2.ClusterSecret)

	// ObjectMeta
	dst.ObjectMeta = src.ObjectMeta

	// Spec
	var matchFieldRequirements []clustersecretiov2.NamespaceSelectorRequirement

	if len(src.MatchNamespace) > 0 {
		matchNsRequirement := clustersecretiov2.NamespaceSelectorRequirement{
			Key:      "metadata.name",
			Operator: clustersecretiov2.NamespaceSelectorOpInRegex,
		}
		for _, matchNs := range src.MatchNamespace {
			matchNsRequirement.Values = append(matchNsRequirement.Values, string(matchNs))
		}
		matchFieldRequirements = append(matchFieldRequirements, matchNsRequirement)
	}

	if len(src.AvoidNamespaces) > 0 {
		avoidNsRequirement := clustersecretiov2.NamespaceSelectorRequirement{
			Key:      "metadata.name",
			Operator: clustersecretiov2.NamespaceSelectorOpNotInRegex,
		}
		for _, avoidNs := range src.AvoidNamespaces {
			avoidNsRequirement.Values = append(avoidNsRequirement.Values, string(avoidNs))
		}
		matchFieldRequirements = append(matchFieldRequirements, avoidNsRequirement)
	}

	if len(matchFieldRequirements) == 0 {
		dst.Spec.NamespaceSelectorTerms = nil
	} else {
		dst.Spec.NamespaceSelectorTerms = []clustersecretiov2.NamespaceSelectorTerm{{
			MatchFields: matchFieldRequirements,
		}}
	}

	spec, err := convertToData(src.Data)
	if err != nil {
		return err
	}
	if spec != nil {
		dst.Spec.DataFrom = spec.DataFrom
		dst.Spec.DataValueFrom = spec.DataValueFrom
		dst.Spec.Template.Data = spec.Template.Data
		dst.Spec.Template.Type = src.Type
		dst.Spec.Template.StringData = src.StringData
	}

	annotations := filterAnnotations(src.Annotations)
	if len(annotations) > 0 || len(src.Labels) > 0 {
		dst.Spec.Template.Metadata = &clustersecretiov2.SecretTemplateMetadata{
			Labels:      src.Labels,
			Annotations: annotations,
		}
	}

	return nil
}

func convertToData(srcData json.RawMessage) (*clustersecretiov2.ClusterSecretSpec, error) {
	if len(srcData) == 0 {
		return nil, nil
	}
	var data map[string]any
	if err := json.Unmarshal(srcData, &data); err != nil {
		return nil, fmt.Errorf("unmarshal secret data: %w", err)
	}
	spec := &clustersecretiov2.ClusterSecretSpec{
		Template: clustersecretiov2.SecretTemplate{
			Data: make(map[string][]byte, len(data)),
		},
	}
	for k, v := range data {
		switch v := v.(type) {
		case string:
			b, err := base64.StdEncoding.DecodeString(v)
			if err != nil {
				return nil, fmt.Errorf("decode data.%s: %w", k, err)
			}
			spec.Template.Data[k] = b
			continue
		case []byte:
			spec.Template.Data[k] = v
			continue
		case map[string]any:
			if k == "valueFrom" {
				valueFromSpec, err := convertToDataValueFrom(srcData)
				if err != nil {
					return nil, fmt.Errorf("decode data.valueFrom: %w", err)
				}
				return valueFromSpec, nil
			}
		}
		return nil, fmt.Errorf("data.%s: invalid data value type: %T", k, v)
	}
	return spec, nil
}

func convertToDataValueFrom(srcData json.RawMessage) (*clustersecretiov2.ClusterSecretSpec, error) {
	var dataValueFrom struct {
		ValueFrom struct {
			SecretKeyRef struct {
				Name      string   `json:"name"`
				Namespace string   `json:"namespace"`
				Keys      []string `json:"keys"`
			} `json:"secretKeyRef"`
		} `json:"valueFrom"`
	}
	if err := json.Unmarshal(srcData, &dataValueFrom); err != nil {
		return nil, fmt.Errorf("unmarshal secret data as valueFrom: %w", err)
	}
	if dataValueFrom.ValueFrom.SecretKeyRef.Name == "" {
		return nil, fmt.Errorf("missing required value: data.valueFrom.secretKeyRef.name")
	}

	spec := &clustersecretiov2.ClusterSecretSpec{}

	// reference an entire secret
	if dataValueFrom.ValueFrom.SecretKeyRef.Keys == nil {
		spec.DataFrom = []clustersecretiov2.DataFrom{{
			SecretRef: &clustersecretiov2.SecretReference{
				Name:      dataValueFrom.ValueFrom.SecretKeyRef.Name,
				Namespace: dataValueFrom.ValueFrom.SecretKeyRef.Namespace,
			},
		}}
		return spec, nil
	}

	// reference only specific fields in a secret
	spec.DataValueFrom = make(map[string]clustersecretiov2.DataValueFrom, len(dataValueFrom.ValueFrom.SecretKeyRef.Keys))
	for _, key := range dataValueFrom.ValueFrom.SecretKeyRef.Keys {
		spec.DataValueFrom[key] = clustersecretiov2.DataValueFrom{
			SecretKeyRef: &clustersecretiov2.SecretKeyReference{
				Name:      dataValueFrom.ValueFrom.SecretKeyRef.Name,
				Namespace: dataValueFrom.ValueFrom.SecretKeyRef.Namespace,
				Key:       key,
			},
		}
	}

	return spec, nil
}

func (dst *ClusterSecret) ConvertFrom(srcRaw conversion.Hub) error {
	src := srcRaw.(*clustersecretiov2.ClusterSecret)

	// ObjectMeta
	dst.ObjectMeta = src.ObjectMeta

	if src.Spec.Template.Metadata != nil {
		dst.Annotations = util.AppendMap(dst.Annotations, src.Spec.Template.Metadata.Annotations)
		dst.Labels = util.AppendMap(dst.Labels, src.Spec.Template.Metadata.Labels)
	}

	// Spec
	dst.AvoidNamespaces = nil
	dst.MatchNamespace = nil

	for _, term := range src.Spec.NamespaceSelectorTerms {
		for _, field := range term.MatchFields {
			if field.Key != "metadata.name" {
				continue
			}
			switch field.Operator {
			case clustersecretiov2.NamespaceSelectorOpIn:
				for _, v := range field.Values {
					dst.MatchNamespace = append(dst.MatchNamespace, NamespaceRegex(regexp.QuoteMeta(v)))
				}
			case clustersecretiov2.NamespaceSelectorOpNotIn:
				for _, v := range field.Values {
					dst.AvoidNamespaces = append(dst.AvoidNamespaces, NamespaceRegex(regexp.QuoteMeta(v)))
				}
			case clustersecretiov2.NamespaceSelectorOpInRegex:
				for _, v := range field.Values {
					dst.MatchNamespace = append(dst.MatchNamespace, NamespaceRegex(v))
				}
			case clustersecretiov2.NamespaceSelectorOpNotInRegex:
				for _, v := range field.Values {
					dst.AvoidNamespaces = append(dst.AvoidNamespaces, NamespaceRegex(v))
				}
			}
		}
	}

	dst.Type = src.Spec.Template.Type
	dst.StringData = src.Spec.Template.StringData

	b, err := convertFromData(&src.Spec)
	if err != nil {
		return err
	}
	dst.Data = b

	// Status
	dst.Status.CreateFn.SyncedNs = src.Status.MatchingNamespaces

	return nil
}

func convertFromData(srcSpec *clustersecretiov2.ClusterSecretSpec) (json.RawMessage, error) {
	if len(srcSpec.DataValueFrom) > 0 {
		keys := make([]string, 0, len(srcSpec.DataValueFrom))
		var ref *clustersecretiov2.SecretKeyReference
		for k, v := range srcSpec.DataValueFrom {
			// NOTE: Ignores the new key name, as v1 doesn't support renaming fields
			_ = k

			if v.SecretKeyRef == nil {
				continue
			}
			keys = append(keys, v.SecretKeyRef.Key)

			// NOTE: Only considers the first secretKeyRef, as v1 doesn't support
			// referencing multiple secrets
			if ref == nil {
				ref = v.SecretKeyRef
			}
		}
		data := map[string]any{
			"valueFrom": map[string]any{
				"secretKeyRef": map[string]any{
					"name":      ref.Name,
					"namespace": ref.Namespace,
					"keys":      keys,
				},
			},
		}
		return json.Marshal(data)
	}
	if len(srcSpec.DataFrom) > 0 {
		// NOTE: Only considers the first dataFrom, as v1 doesn't support
		// referencing multiple secrets
		data := map[string]any{
			"valueFrom": map[string]any{
				"secretKeyRef": map[string]any{
					"name":      srcSpec.DataFrom[0].SecretRef.Name,
					"namespace": srcSpec.DataFrom[0].SecretRef.Namespace,
				},
			},
		}
		return json.Marshal(data)
	}
	return json.Marshal(srcSpec.Template.Data)
}

func filterAnnotations(annotations map[string]string) map[string]string {
	if annotations == nil {
		return nil
	}
	result := make(map[string]string, len(annotations))
	for k, v := range annotations {
		if containsPrefix(k, skipAnnotationPrefixes) {
			continue
		}
		result[k] = v
	}
	return result
}

func containsPrefix(value string, prefixes []string) bool {
	for _, p := range prefixes {
		if strings.HasPrefix(value, p) {
			return true
		}
	}
	return false
}
