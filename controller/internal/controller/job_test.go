package controller

import (
	"strings"
	"testing"

	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/utils/ptr"

	"github.com/aburan28/cryptanalysis/controller/api/v1alpha1"
)

func sampleCampaign() *v1alpha1.Campaign {
	return &v1alpha1.Campaign{
		ObjectMeta: metav1.ObjectMeta{Name: "ecc2k-130", Namespace: "cryptanalysis", UID: "uid-1"},
		Spec: v1alpha1.CampaignSpec{
			Target: v1alpha1.TargetSpec{Curve: "certicom-ecc2k-130", CampaignID: "ecc2k-130", ContractID: strings.Repeat("ab", 32)},
			Coordinator: v1alpha1.CoordinatorSpec{
				PublishURL: "http://ecc2k130-coordinator-publisher.cryptanalysis.svc",
				TokenSecretRef: corev1.SecretKeySelector{
					LocalObjectReference: corev1.LocalObjectReference{Name: "walker-publish"},
					Key:                  "publish-token",
				},
				Bucket:    "ecc2k130-590183823895",
				AWSRegion: "us-west-2",
			},
			Workers: v1alpha1.WorkerSpec{
				Image:       "ghcr.io/example/ecc2k130-walker:1.0",
				Parallelism: 4,
				SlotCount:   ptr.To[int32](16),
				SlotBase:    100,
				Resources: corev1.ResourceRequirements{Limits: corev1.ResourceList{
					"nvidia.com/gpu": resource.MustParse("1"),
				}},
				Env: []corev1.EnvVar{
					{Name: "WALKER_THREADS", Value: "8"},
					{Name: v1alpha1.EnvBucket, Value: "attacker-bucket"},
				},
				ServiceAccountName: "walker",
				Spool:              v1alpha1.SpoolSpec{SizeLimit: ptr.To(resource.MustParse("20Gi"))},
			},
			Scheduling: v1alpha1.SchedulingSpec{QueueName: "gpu-queue", WorkloadPriorityClass: "campaign-high"},
		},
	}
}

func envValue(env []corev1.EnvVar, name string) (corev1.EnvVar, bool) {
	for _, e := range env {
		if e.Name == name {
			return e, true
		}
	}
	return corev1.EnvVar{}, false
}

func TestBuildJobKueueContract(t *testing.T) {
	c := sampleCampaign()
	job, dropped := BuildJob(c, 3)

	if job.Labels[v1alpha1.KueueQueueNameLabel] != "gpu-queue" {
		t.Fatalf("queue label missing: %v", job.Labels)
	}
	if job.Labels[v1alpha1.KueuePriorityClassLabel] != "campaign-high" {
		t.Fatalf("priority label missing: %v", job.Labels)
	}
	if job.Annotations[v1alpha1.KueueElasticJobAnnotation] != "true" {
		t.Fatalf("elastic annotation expected by default: %v", job.Annotations)
	}
	if !ptr.Deref(job.Spec.Suspend, false) {
		t.Fatal("Kueue-managed Jobs must be created suspended")
	}
	if ptr.Deref(job.Spec.Parallelism, 0) != 3 || ptr.Deref(job.Spec.Completions, 0) != 16 {
		t.Fatalf("parallelism/completions wrong: %d/%d", *job.Spec.Parallelism, *job.Spec.Completions)
	}
	if ptr.Deref(job.Spec.CompletionMode, "") != batchv1.IndexedCompletion {
		t.Fatal("slots require Indexed completion mode")
	}
	if job.Spec.PodFailurePolicy == nil || job.Spec.PodFailurePolicy.Rules[0].Action != batchv1.PodFailurePolicyActionIgnore {
		t.Fatal("disruptions must be ignored by the pod failure policy")
	}
	if len(dropped) != 1 || dropped[0] != v1alpha1.EnvBucket {
		t.Fatalf("contract override should be dropped, got %v", dropped)
	}

	pod := job.Spec.Template
	if pod.Labels[v1alpha1.LabelPublisherClient] != "true" {
		t.Fatal("walker pods must carry the publisher NetworkPolicy label")
	}
	if pod.Spec.RestartPolicy != corev1.RestartPolicyOnFailure {
		t.Fatal("walkers restart in place on failure")
	}
	env := pod.Spec.Containers[0].Env
	bucket, _ := envValue(env, v1alpha1.EnvBucket)
	if bucket.Value != "ecc2k130-590183823895" {
		t.Fatalf("ECC_BUCKET overridden: %q", bucket.Value)
	}
	if base, _ := envValue(env, v1alpha1.EnvSlotBase); base.Value != "100" {
		t.Fatalf("slot base env: %q", base.Value)
	}
	if count, _ := envValue(env, v1alpha1.EnvSlotCount); count.Value != "16" {
		t.Fatalf("slot count env: %q", count.Value)
	}
	if token, _ := envValue(env, v1alpha1.EnvPublishToken); token.ValueFrom == nil || token.ValueFrom.SecretKeyRef.Name != "walker-publish" {
		t.Fatal("publish token must come from the referenced Secret")
	}
	if _, ok := envValue(env, "WALKER_THREADS"); !ok {
		t.Fatal("user env must be preserved")
	}
	if pod.Spec.Volumes[0].EmptyDir == nil || pod.Spec.Volumes[0].EmptyDir.SizeLimit.String() != "20Gi" {
		t.Fatal("spool emptyDir must carry the size limit")
	}
	if len(job.Name) > 63 || !strings.HasPrefix(job.Name, "ecc2k-130-walkers-") {
		t.Fatalf("job name %q", job.Name)
	}
}

func TestBuildJobWebIdentity(t *testing.T) {
	c := sampleCampaign()
	c.Spec.Workers.WebIdentity = &v1alpha1.WebIdentitySpec{RoleArn: "arn:aws:iam::123456789012:role/walker"}
	job, _ := BuildJob(c, 1)
	env := job.Spec.Template.Spec.Containers[0].Env
	if role, _ := envValue(env, v1alpha1.EnvAWSRoleArn); role.Value != "arn:aws:iam::123456789012:role/walker" {
		t.Fatal("AWS_ROLE_ARN missing")
	}
	if file, _ := envValue(env, v1alpha1.EnvAWSTokenFile); file.Value != webIdentityMount+"/token" {
		t.Fatalf("token file env: %q", file.Value)
	}
	var projected *corev1.ProjectedVolumeSource
	for _, v := range job.Spec.Template.Spec.Volumes {
		if v.Name == webIdentityVolume {
			projected = v.Projected
		}
	}
	if projected == nil || projected.Sources[0].ServiceAccountToken.Audience != "sts.amazonaws.com" {
		t.Fatal("projected token with the STS audience expected")
	}
	if ptr.Deref(projected.Sources[0].ServiceAccountToken.ExpirationSeconds, 0) != 3600 {
		t.Fatal("default token expiry expected")
	}
}

func TestSpecHashIgnoresMutableFields(t *testing.T) {
	a := sampleCampaign()
	b := sampleCampaign()
	b.Spec.Workers.Parallelism = 9
	b.Spec.Suspend = true
	b.Spec.Backpressure = &v1alpha1.BackpressureSpec{RedParallelism: 1}
	if SpecHash(a) != SpecHash(b) {
		t.Fatal("parallelism, suspend and backpressure must not change the hash")
	}
	b.Spec.Workers.Image = "ghcr.io/example/ecc2k130-walker:2.0"
	if SpecHash(a) == SpecHash(b) {
		t.Fatal("image change must change the hash")
	}
	c := sampleCampaign()
	c.Spec.Workers.SlotCount = ptr.To[int32](32)
	if SpecHash(a) == SpecHash(c) {
		t.Fatal("slot range change must change the hash")
	}
	d := sampleCampaign()
	d.Spec.Scheduling.QueueName = "other-queue"
	if SpecHash(a) == SpecHash(d) {
		t.Fatal("queue change must change the hash")
	}
}

func TestJobNameTruncates(t *testing.T) {
	c := sampleCampaign()
	c.Name = strings.Repeat("n", 70)
	name := JobName(c, "0123456789")
	if len(name) != 63 || !strings.HasSuffix(name, "-walkers-0123456789") {
		t.Fatalf("name %q (%d)", name, len(name))
	}
}
