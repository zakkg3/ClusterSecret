package controller

import (
	"bytes"
	"fmt"

	corev1 "k8s.io/api/core/v1"
)

func getSecretDiff(sec, expected *corev1.Secret) string {
	switch {
	case sec.Name != expected.Name:
		return "name"
	case sec.Type != expected.Type:
		return "type"
	default:
		if diff := diffStringMaps(expected.Labels, sec.Labels); diff != "" {
			return "labels: " + diff
		}
		// Delete it, because we don't want to diff it
		delete(sec.Annotations, annotationLastSync)
		if diff := diffStringMaps(expected.Annotations, sec.Annotations); diff != "" {
			return "annotations: " + diff
		}
		if diff := diffMaps(expected.Data, sec.Data, bytes.Equal); diff != "" {
			return "data: " + diff
		}
		return ""
	}
}

func diffStringMaps(want, got map[string]string) string {
	return diffMaps(want, got, func(a, b string) bool { return a == b })
}

func diffMaps[V any](a, b map[string]V, equal func(V, V) bool) string {
	for k, v := range a {
		other, ok := b[k]
		if !ok {
			return fmt.Sprintf("missing key: %q", k)
		}
		if !equal(v, other) {
			return fmt.Sprintf("value does not match on key: %q", k)
		}
	}
	for k := range b {
		_, ok := a[k]
		if !ok {
			return fmt.Sprintf("excess key: %q", k)
		}
	}
	return ""
}
