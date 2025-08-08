package controller

import (
	"regexp"
	"strconv"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/labels"
	"k8s.io/apimachinery/pkg/util/validation/field"

	clustersecretiov2 "github.com/zakkg3/ClusterSecret/api/v2"
)

func getNamespaceFields(ns *corev1.Namespace) labels.Set {
	return labels.Set{
		"metadata.name": ns.Name,
		"status.phase":  string(ns.Status.Phase),
	}
}

func getNamespaceLabels(ns *corev1.Namespace) labels.Set {
	return ns.Labels
}

func matchesNamespace(terms []clustersecretiov2.NamespaceSelectorTerm, namespace *corev1.Namespace) (bool, error) {
	path := field.NewPath("spec", "namespaceSelectorTerm")

	nsFields := getNamespaceFields(namespace)
	nsLabels := getNamespaceLabels(namespace)

	for termIdx, term := range terms {
		termPath := path.Index(termIdx)
		ok, err := matchesTerm(term, nsFields, nsLabels, termPath)
		if err != nil {
			return false, err
		}
		// Return true if any term matches,
		// resulting in an OR operation between terms
		if ok {
			return true, nil
		}
	}
	return false, nil
}

func matchesTerm(term clustersecretiov2.NamespaceSelectorTerm, nsFields, nsLabels labels.Labels, path *field.Path) (bool, error) {
	for reqIdx, req := range term.MatchFields {
		reqPath := path.Child("matchFields").Index(reqIdx)
		ok, err := matchesRequirement(req, nsFields, reqPath)
		if err != nil {
			return false, err
		}
		// Return false if any requirement fails,
		// resulting in an AND operation between requirements within a term
		if !ok {
			return false, nil
		}
	}

	for reqIdx, req := range term.MatchExpressions {
		reqPath := path.Child("matchExpressions").Index(reqIdx)
		ok, err := matchesRequirement(req, nsLabels, reqPath)
		if err != nil {
			return false, err
		}
		// Return false if any requirement fails,
		// resulting in an AND operation between requirements within a term
		if !ok {
			return false, nil
		}
	}

	return true, nil
}

func matchesRequirement(requirement clustersecretiov2.NamespaceSelectorRequirement, ls labels.Labels, path *field.Path) (bool, error) {
	switch requirement.Operator {
	case clustersecretiov2.NamespaceSelectorOpIn:
		if !ls.Has(requirement.Key) {
			return false, nil
		}
		return matchesAnyString(requirement.Values, ls.Get(requirement.Key)), nil
	case clustersecretiov2.NamespaceSelectorOpNotIn:
		if !ls.Has(requirement.Key) {
			return true, nil
		}
		return !matchesAnyString(requirement.Values, ls.Get(requirement.Key)), nil
	case clustersecretiov2.NamespaceSelectorOpInRegex:
		if !ls.Has(requirement.Key) {
			return false, nil
		}
		return matchesAnyRegex(requirement.Values, ls.Get(requirement.Key), path.Child("values"))
	case clustersecretiov2.NamespaceSelectorOpNotInRegex:
		if !ls.Has(requirement.Key) {
			return true, nil
		}
		ok, err := matchesAnyRegex(requirement.Values, ls.Get(requirement.Key), path.Child("values"))
		return !ok, err
	case clustersecretiov2.NamespaceSelectorOpExists:
		return ls.Has(requirement.Key), nil
	case clustersecretiov2.NamespaceSelectorOpDoesNotExist:
		return !ls.Has(requirement.Key), nil
	case clustersecretiov2.NamespaceSelectorOpGt:
		if !ls.Has(requirement.Key) {
			return false, nil
		}
		if len(requirement.Values) == 0 {
			return false, field.Required(path.Child("values"), "must have one element")
		}
		parsedValue, err := strconv.ParseInt(requirement.Values[0], 10, 0)
		if err != nil {
			return false, field.Invalid(path.Child("values").Index(0), requirement.Values[0], err.Error())
		}
		parsedLabel, err := strconv.ParseInt(ls.Get(requirement.Key), 10, 0)
		if err != nil {
			return false, nil // ignore error when Namespace field is not number
		}
		return parsedLabel > parsedValue, nil
	case clustersecretiov2.NamespaceSelectorOpLt:
		if !ls.Has(requirement.Key) {
			return false, nil
		}
		if len(requirement.Values) == 0 {
			return false, field.Required(path.Child("values"), "must have one element")
		}
		parsedValue, err := strconv.ParseInt(requirement.Values[0], 10, 0)
		if err != nil {
			return false, field.Invalid(path.Child("values").Index(0), requirement.Values[0], err.Error())
		}
		parsedLabel, err := strconv.ParseInt(ls.Get(requirement.Key), 10, 0)
		if err != nil {
			return false, nil // ignore error when Namespace field is not number
		}
		return parsedLabel < parsedValue, nil
	default:
		return false, field.Invalid(path.Child("operator"), string(requirement.Operator), "invalid or unsupported operator")
	}
}

func matchesAnyString(haystack []string, needle string) bool {
	for _, v := range haystack {
		if v == needle {
			return true
		}
	}
	return false
}

func matchesAnyRegex(patterns []string, s string, path *field.Path) (bool, error) {
	for i, pattern := range patterns {
		ok, err := regexp.MatchString(pattern, s)
		if err != nil {
			return false, field.Invalid(path.Index(i), pattern, err.Error())
		}
		if ok {
			return true, nil
		}
	}
	return false, nil
}
