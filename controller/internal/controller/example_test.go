package controller

import (
	"os"
	"path/filepath"
	"testing"

	"k8s.io/utils/ptr"
	"sigs.k8s.io/yaml"

	"github.com/aburan28/cryptanalysis/controller/api/v1alpha1"
)

// The shipped example must decode strictly and build a valid Job, so the
// documentation cannot drift from the API.
func TestExampleCampaignBuilds(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "..", "deploy", "examples", "campaign-ecc2k130.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	var c v1alpha1.Campaign
	if err := yaml.UnmarshalStrict(raw, &c); err != nil {
		t.Fatalf("example does not match the API: %v", err)
	}
	if c.Spec.Backpressure == nil || c.Spec.Coordinator.StatusURL == "" {
		t.Fatal("example should demonstrate backpressure with a status feed")
	}
	job, dropped := BuildJob(&c, c.Spec.Workers.Parallelism)
	if len(dropped) != 0 {
		t.Fatalf("example env must not collide with the contract: %v", dropped)
	}
	if ptr.Deref(job.Spec.Completions, 0) != 256 || ptr.Deref(job.Spec.Parallelism, 0) != 32 {
		t.Fatalf("example slot range: %d/%d", *job.Spec.Parallelism, *job.Spec.Completions)
	}
	if got := job.Spec.Template.Spec.Containers[0].Resources.Limits["nvidia.com/gpu"]; got.String() != "1" {
		t.Fatalf("example should request one GPU per walker, got %s", got.String())
	}
	if int64(c.Spec.Workers.SlotBase)+int64(*c.Spec.Workers.SlotCount) > v1alpha1.MaxSlot+1 {
		t.Fatal("example slot range exceeds the coordinator schema")
	}
}
