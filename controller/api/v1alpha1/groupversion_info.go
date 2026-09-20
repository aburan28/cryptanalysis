// Package v1alpha1 contains the cryptanalysis.io/v1alpha1 API.
//
// +kubebuilder:object:generate=true
// +groupName=cryptanalysis.io
package v1alpha1

import (
	"k8s.io/apimachinery/pkg/runtime/schema"
	"sigs.k8s.io/controller-runtime/pkg/scheme"
)

var (
	// GroupVersion identifies the API served by this package.
	GroupVersion = schema.GroupVersion{Group: "cryptanalysis.io", Version: "v1alpha1"}

	// SchemeBuilder registers the package types with a runtime.Scheme.
	SchemeBuilder = &scheme.Builder{GroupVersion: GroupVersion}

	// AddToScheme adds the package types to a runtime.Scheme.
	AddToScheme = SchemeBuilder.AddToScheme
)
