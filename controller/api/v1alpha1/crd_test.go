package v1alpha1_test

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"k8s.io/apiextensions-apiserver/pkg/apis/apiextensions"
	apiextensionsv1 "k8s.io/apiextensions-apiserver/pkg/apis/apiextensions/v1"
	"k8s.io/apiextensions-apiserver/pkg/apis/apiextensions/validation"
	structuralschema "k8s.io/apiextensions-apiserver/pkg/apiserver/schema"
	"k8s.io/apiextensions-apiserver/pkg/apiserver/schema/cel"
	apiservervalidation "k8s.io/apiextensions-apiserver/pkg/apiserver/validation"
	utiljson "k8s.io/apimachinery/pkg/util/json"
	"k8s.io/apimachinery/pkg/util/validation/field"
	celconfig "k8s.io/apiserver/pkg/apis/cel"
	"sigs.k8s.io/yaml"
)

const (
	crdPath     = "../../deploy/helm/cryptanalysis-operator/crds/cryptanalysis.io_campaigns.yaml"
	examplePath = "../../deploy/examples/campaign-ecc2k130.yaml"
)

func loadCRD(t *testing.T) *apiextensions.CustomResourceDefinition {
	t.Helper()
	raw, err := os.ReadFile(filepath.Clean(crdPath))
	if err != nil {
		t.Fatal(err)
	}
	var v1 apiextensionsv1.CustomResourceDefinition
	if err := yaml.UnmarshalStrict(raw, &v1); err != nil {
		t.Fatalf("decode generated CRD: %v", err)
	}
	internal := &apiextensions.CustomResourceDefinition{}
	if err := apiextensionsv1.Convert_v1_CustomResourceDefinition_To_apiextensions_CustomResourceDefinition(&v1, internal, nil); err != nil {
		t.Fatal(err)
	}
	// The API server records the stored version on create; mirror that so
	// the full create-time validation applies.
	for _, version := range internal.Spec.Versions {
		if version.Storage {
			internal.Status.StoredVersions = append(internal.Status.StoredVersions, version.Name)
		}
	}
	return internal
}

// schemaOf returns the served schema; the internal type hoists a schema shared
// by every version to spec.validation.
func schemaOf(crd *apiextensions.CustomResourceDefinition) *apiextensions.JSONSchemaProps {
	if crd.Spec.Validation != nil && crd.Spec.Validation.OpenAPIV3Schema != nil {
		return crd.Spec.Validation.OpenAPIV3Schema
	}
	return crd.Spec.Versions[0].Schema.OpenAPIV3Schema
}

// The generated CRD must satisfy the same validation the API server applies
// on create, which includes compiling every CEL rule within its cost budget.
func TestGeneratedCRDPassesAPIServerValidation(t *testing.T) {
	crd := loadCRD(t)
	if errs := validation.ValidateCustomResourceDefinition(context.Background(), crd); len(errs) > 0 {
		t.Fatalf("CRD rejected by apiserver validation:\n%v", errs.ToAggregate())
	}
}

func exampleObject(t *testing.T) map[string]interface{} {
	t.Helper()
	raw, err := os.ReadFile(filepath.Clean(examplePath))
	if err != nil {
		t.Fatal(err)
	}
	jsonRaw, err := yaml.YAMLToJSON(raw)
	if err != nil {
		t.Fatal(err)
	}
	// The API server decodes integers as int64 before CEL evaluation; plain
	// encoding/json would produce float64 and every arithmetic rule would fail.
	var obj map[string]interface{}
	if err := utiljson.Unmarshal(jsonRaw, &obj); err != nil {
		t.Fatal(err)
	}
	return obj
}

func validateAgainstCRD(t *testing.T, crd *apiextensions.CustomResourceDefinition, obj map[string]interface{}) field.ErrorList {
	t.Helper()
	schema := schemaOf(crd)
	validator, _, err := apiservervalidation.NewSchemaValidator(schema)
	if err != nil {
		t.Fatal(err)
	}
	var errs field.ErrorList
	if result := validator.Validate(obj); len(result.Errors) > 0 {
		for _, e := range result.Errors {
			errs = append(errs, field.Invalid(field.NewPath(""), nil, e.Error()))
		}
		return errs
	}
	structural, err := structuralschema.NewStructural(schema)
	if err != nil {
		t.Fatal(err)
	}
	celValidator := cel.NewValidator(structural, true, celconfig.PerCallLimit)
	if celValidator == nil {
		t.Fatal("CRD declares no CEL rules; expected x-kubernetes-validations")
	}
	errs, _ = celValidator.Validate(context.Background(), nil, structural, obj, nil, celconfig.RuntimeCELCostBudget)
	return errs
}

func TestExampleSatisfiesSchemaAndCEL(t *testing.T) {
	crd := loadCRD(t)
	obj := exampleObject(t)
	if errs := validateAgainstCRD(t, crd, obj); len(errs) > 0 {
		t.Fatalf("example rejected:\n%v", errs.ToAggregate())
	}
	spec := obj["spec"].(map[string]interface{})
	workers := spec["workers"].(map[string]interface{})

	// slotBase + slotCount past the coordinator's slot range must fail CEL.
	workers["slotBase"] = int64(65535)
	if errs := validateAgainstCRD(t, crd, obj); len(errs) == 0 {
		t.Fatal("slot range overflow should be rejected by CEL")
	}
	workers["slotBase"] = int64(1024)

	// backpressure without a status feed must fail CEL.
	coordinator := spec["coordinator"].(map[string]interface{})
	delete(coordinator, "statusURL")
	if errs := validateAgainstCRD(t, crd, obj); len(errs) == 0 {
		t.Fatal("backpressure without statusURL should be rejected by CEL")
	}
}
