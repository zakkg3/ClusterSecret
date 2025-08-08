package v1

import (
	"bytes"
	"encoding/json"
	"testing"

	clustersecretiov2 "github.com/zakkg3/CsGo/api/v2"
)

func TestConvertTo_matchNamespace(t *testing.T) {
	src := &ClusterSecret{
		MatchNamespace:  []NamespaceRegex{`foo.*`},
		AvoidNamespaces: []NamespaceRegex{`kube-.*`},
	}

	dst := &clustersecretiov2.ClusterSecret{}

	if err := src.ConvertTo(dst); err != nil {
		t.Fatalf("ConvertTo error: %s", err)
	}

	terms := dst.Spec.NamespaceSelectorTerms
	if len(terms) == 0 {
		t.Fatalf("missing terms")
	}

	if len(terms) > 1 {
		t.Errorf("too many terms, want 1, got: %#v", terms)
	}

	term := terms[0]

	if term.MatchExpressions != nil {
		t.Errorf("want nil matchExpressions, got: %#v", term.MatchExpressions)
	}

	if len(term.MatchFields) != 2 {
		t.Fatalf("want 2 matchFields, got: %#v", term.MatchFields)
	}

	match0 := term.MatchFields[0]
	match1 := term.MatchFields[1]

	equalAsJSON(t, "metadata.name", match0.Key, "matchFields[0].key")
	equalAsJSON(t, "metadata.name", match1.Key, "matchFields[1].key")

	equalAsJSON(t, clustersecretiov2.NamespaceSelectorOpInRegex, match0.Operator, "matchFields[0].operator")
	equalAsJSON(t, clustersecretiov2.NamespaceSelectorOpNotInRegex, match1.Operator, "matchFields[1].operator")

	equalAsJSON(t, []string{"foo.*"}, match0.Values, "matchFields[0].values")
	equalAsJSON(t, []string{"kube-.*"}, match1.Values, "matchFields[0].values")
}

func equalAsJSON(t testing.TB, want, got any, message string) bool {
	wantBytes, err := json.Marshal(want)
	if err != nil {
		t.Fatalf("%s: marshal 'want': %s", message, err)
	}
	gotBytes, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("%s: marshal 'got': %s", message, err)
	}
	if !bytes.Equal(wantBytes, gotBytes) {
		t.Errorf("%s: want %s, got %s", message, wantBytes, gotBytes)
		return false
	}
	return true
}
