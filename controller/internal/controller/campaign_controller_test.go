package controller

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"

	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	"k8s.io/client-go/tools/record"
	"k8s.io/utils/ptr"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	"github.com/aburan28/cryptanalysis/controller/api/v1alpha1"
)

type feedServer struct {
	server *httptest.Server
	state  atomic.Value
	hits   atomic.Int64
}

func newFeedServer(t *testing.T) *feedServer {
	t.Helper()
	fs := &feedServer{}
	fs.state.Store(PressureGreen)
	fs.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		fs.hits.Add(1)
		state := fs.state.Load().(string)
		if state == "down" {
			http.Error(w, "unavailable", http.StatusServiceUnavailable)
			return
		}
		collisions := 0
		if state == "collision" {
			state, collisions = PressureGreen, 1
		}
		fmt.Fprintf(w, `{"state":"COLLECTING","generated_at":%q,"collisions":%d,"dps":10,"walkers":2,"queue":{"state":%q,"messages":5}}`,
			time.Now().UTC().Format(time.RFC3339), collisions, state)
	}))
	t.Cleanup(fs.server.Close)
	return fs
}

type harness struct {
	t          *testing.T
	client     client.Client
	reconciler *CampaignReconciler
	recorder   *record.FakeRecorder
	clock      time.Time
	feed       *feedServer
}

func newHarness(t *testing.T, campaign *v1alpha1.Campaign, feed *feedServer) *harness {
	t.Helper()
	scheme := runtime.NewScheme()
	if err := clientgoscheme.AddToScheme(scheme); err != nil {
		t.Fatal(err)
	}
	if err := v1alpha1.AddToScheme(scheme); err != nil {
		t.Fatal(err)
	}
	if feed != nil {
		campaign.Spec.Coordinator.StatusURL = feed.server.URL + "/status.json"
	}
	c := fake.NewClientBuilder().WithScheme(scheme).WithObjects(campaign).
		WithStatusSubresource(&v1alpha1.Campaign{}).Build()
	h := &harness{t: t, client: c, recorder: record.NewFakeRecorder(64), clock: time.Now(), feed: feed}
	h.reconciler = &CampaignReconciler{
		Client: c, Scheme: scheme, Recorder: h.recorder,
		Feed: NewHTTPFeedSource(5 * time.Second),
		Now:  func() time.Time { return h.clock },
	}
	return h
}

func (h *harness) reconcile(name string) ctrl.Result {
	h.t.Helper()
	res, err := h.reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Namespace: "cryptanalysis", Name: name},
	})
	if err != nil {
		h.t.Fatalf("reconcile: %v", err)
	}
	return res
}

func (h *harness) jobs() []batchv1.Job {
	h.t.Helper()
	list := &batchv1.JobList{}
	if err := h.client.List(context.Background(), list, client.InNamespace("cryptanalysis")); err != nil {
		h.t.Fatal(err)
	}
	return list.Items
}

func (h *harness) campaign(name string) *v1alpha1.Campaign {
	h.t.Helper()
	c := &v1alpha1.Campaign{}
	if err := h.client.Get(context.Background(), types.NamespacedName{Namespace: "cryptanalysis", Name: name}, c); err != nil {
		h.t.Fatal(err)
	}
	return c
}

func (h *harness) update(c *v1alpha1.Campaign) {
	h.t.Helper()
	if err := h.client.Update(context.Background(), c); err != nil {
		h.t.Fatal(err)
	}
}

func condition(c *v1alpha1.Campaign, kind string) *metav1.Condition {
	return meta.FindStatusCondition(c.Status.Conditions, kind)
}

func TestReconcileCreatesSuspendedKueueJob(t *testing.T) {
	h := newHarness(t, sampleCampaign(), nil)
	res := h.reconcile("ecc2k-130")
	if res.RequeueAfter != defaultRequeue {
		t.Fatalf("expected periodic requeue, got %v", res.RequeueAfter)
	}
	jobs := h.jobs()
	if len(jobs) != 1 {
		t.Fatalf("expected one job, got %d", len(jobs))
	}
	job := jobs[0]
	if !ptr.Deref(job.Spec.Suspend, false) || ptr.Deref(job.Spec.Parallelism, 0) != 4 {
		t.Fatalf("job should be suspended at desired parallelism: %+v", job.Spec)
	}
	if !metav1.IsControlledBy(&job, h.campaign("ecc2k-130")) {
		t.Fatal("job must be owned by the campaign")
	}
	c := h.campaign("ecc2k-130")
	if c.Status.Phase != v1alpha1.PhaseQueued || c.Status.JobName != job.Name || c.Status.EffectiveParallelism != 4 {
		t.Fatalf("status %+v", c.Status)
	}
	if cond := condition(c, v1alpha1.ConditionAdmitted); cond == nil || cond.Status != metav1.ConditionFalse {
		t.Fatalf("Admitted should be false before Kueue unsuspends: %+v", cond)
	}
	if cond := condition(c, v1alpha1.ConditionStatusFresh); cond == nil || cond.Reason != ReasonNoFeedConfigured {
		t.Fatalf("StatusFresh reason: %+v", cond)
	}
	select {
	case ev := <-h.recorder.Events:
		if ev == "" {
			t.Fatal("expected an event")
		}
	default:
		t.Fatal("expected a JobCreated or EnvOverrideIgnored event")
	}
}

func TestReconcileReportsAdmissionAndReadiness(t *testing.T) {
	h := newHarness(t, sampleCampaign(), nil)
	h.reconcile("ecc2k-130")
	job := h.jobs()[0]
	// Simulate Kueue admission and the Job controller reporting readiness.
	job.Spec.Suspend = ptr.To(false)
	if err := h.client.Update(context.Background(), &job); err != nil {
		t.Fatal(err)
	}
	job.Status.Active, job.Status.Ready = 4, ptr.To[int32](4)
	if err := h.client.Status().Update(context.Background(), &job); err != nil {
		t.Fatal(err)
	}
	h.reconcile("ecc2k-130")
	c := h.campaign("ecc2k-130")
	if c.Status.Phase != v1alpha1.PhaseRunning || c.Status.ReadyWorkers != 4 {
		t.Fatalf("status %+v", c.Status)
	}
	if cond := condition(c, v1alpha1.ConditionWorkersReady); cond == nil || cond.Status != metav1.ConditionTrue {
		t.Fatalf("WorkersReady: %+v", cond)
	}
}

func TestReconcileBackpressureScalesAndReleases(t *testing.T) {
	feed := newFeedServer(t)
	campaign := sampleCampaign()
	campaign.Spec.Backpressure = &v1alpha1.BackpressureSpec{
		PollIntervalSeconds: 30, RedParallelism: 0, YellowParallelism: ptr.To[int32](2),
		RecoverySeconds: 300, StaleAfterSeconds: 900,
	}
	h := newHarness(t, campaign, feed)

	res := h.reconcile("ecc2k-130")
	if res.RequeueAfter != 30*time.Second {
		t.Fatalf("poll interval should drive requeue, got %v", res.RequeueAfter)
	}
	if got := ptr.Deref(h.jobs()[0].Spec.Parallelism, 0); got != 4 {
		t.Fatalf("green should run desired, got %d", got)
	}

	// Cached within the poll interval: the feed is not re-fetched.
	feed.state.Store(PressureYellow)
	h.reconcile("ecc2k-130")
	if feed.hits.Load() != 1 {
		t.Fatalf("feed should be cached, hits=%d", feed.hits.Load())
	}

	h.clock = h.clock.Add(31 * time.Second)
	h.reconcile("ecc2k-130")
	jobs := h.jobs()
	if len(jobs) != 1 || ptr.Deref(jobs[0].Spec.Parallelism, 0) != 2 {
		t.Fatalf("yellow should scale to 2 in place, got %+v", jobs)
	}
	c := h.campaign("ecc2k-130")
	if c.Status.Phase != v1alpha1.PhaseBackpressured || c.Status.QueueState != PressureYellow {
		t.Fatalf("status %+v", c.Status)
	}

	feed.state.Store(PressureRed)
	h.clock = h.clock.Add(31 * time.Second)
	h.reconcile("ecc2k-130")
	if len(h.jobs()) != 0 {
		t.Fatal("red with redParallelism=0 must release the job")
	}
	c = h.campaign("ecc2k-130")
	if c.Status.LastRedObserved == nil || c.Status.EffectiveParallelism != 0 {
		t.Fatalf("red status %+v", c.Status)
	}

	// Green again, but inside the recovery window: nothing is recreated.
	feed.state.Store(PressureGreen)
	h.clock = h.clock.Add(31 * time.Second)
	h.reconcile("ecc2k-130")
	if len(h.jobs()) != 0 {
		t.Fatal("recovery window must hold the release")
	}
	if cond := condition(h.campaign("ecc2k-130"), v1alpha1.ConditionBackpressured); cond == nil || cond.Reason != ReasonRecovering {
		t.Fatalf("Backpressured reason: %+v", cond)
	}

	h.clock = h.clock.Add(6 * time.Minute)
	h.reconcile("ecc2k-130")
	jobs = h.jobs()
	if len(jobs) != 1 || ptr.Deref(jobs[0].Spec.Parallelism, 0) != 4 {
		t.Fatalf("after recovery the job returns at desired parallelism, got %+v", jobs)
	}
}

func TestReconcileHoldsWhenFeedUnavailable(t *testing.T) {
	feed := newFeedServer(t)
	campaign := sampleCampaign()
	campaign.Spec.Backpressure = &v1alpha1.BackpressureSpec{
		PollIntervalSeconds: 30, YellowParallelism: ptr.To[int32](2), RecoverySeconds: 300, StaleAfterSeconds: 900,
	}
	h := newHarness(t, campaign, feed)
	feed.state.Store(PressureYellow)
	h.reconcile("ecc2k-130")
	if got := ptr.Deref(h.jobs()[0].Spec.Parallelism, 0); got != 2 {
		t.Fatalf("yellow should run 2, got %d", got)
	}

	feed.state.Store("down")
	h.clock = h.clock.Add(31 * time.Second)
	h.reconcile("ecc2k-130")
	if got := ptr.Deref(h.jobs()[0].Spec.Parallelism, 0); got != 2 {
		t.Fatalf("unavailable feed must hold parallelism, got %d", got)
	}
	c := h.campaign("ecc2k-130")
	if cond := condition(c, v1alpha1.ConditionStatusFresh); cond == nil || cond.Status != metav1.ConditionFalse {
		t.Fatalf("StatusFresh should be false: %+v", cond)
	}
}

func TestReconcileSuspendDeletesJob(t *testing.T) {
	h := newHarness(t, sampleCampaign(), nil)
	h.reconcile("ecc2k-130")
	c := h.campaign("ecc2k-130")
	c.Spec.Suspend = true
	h.update(c)
	h.reconcile("ecc2k-130")
	if len(h.jobs()) != 0 {
		t.Fatal("suspend must delete the job")
	}
	c = h.campaign("ecc2k-130")
	if c.Status.Phase != v1alpha1.PhaseSuspended || c.Status.JobName != "" {
		t.Fatalf("status %+v", c.Status)
	}
	c.Spec.Suspend = false
	h.update(c)
	h.reconcile("ecc2k-130")
	if len(h.jobs()) != 1 {
		t.Fatal("resume must recreate the job")
	}
}

func TestReconcileCollisionPolicySuspends(t *testing.T) {
	feed := newFeedServer(t)
	campaign := sampleCampaign()
	campaign.Spec.OnCollision = v1alpha1.CollisionSuspend
	h := newHarness(t, campaign, feed)
	h.reconcile("ecc2k-130")
	if len(h.jobs()) != 1 {
		t.Fatal("expected job")
	}
	feed.state.Store("collision")
	h.clock = h.clock.Add(2 * time.Minute)
	h.reconcile("ecc2k-130")
	if len(h.jobs()) != 0 {
		t.Fatal("collision with Suspend policy must release the job")
	}
	c := h.campaign("ecc2k-130")
	if c.Status.Collisions != 1 || c.Status.Phase != v1alpha1.PhaseSuspended {
		t.Fatalf("status %+v", c.Status)
	}
	if cond := condition(c, v1alpha1.ConditionCollisionRecorded); cond == nil || cond.Status != metav1.ConditionTrue {
		t.Fatalf("CollisionRecorded: %+v", cond)
	}
}

func TestReconcileHandsOverOnImmutableChange(t *testing.T) {
	h := newHarness(t, sampleCampaign(), nil)
	h.reconcile("ecc2k-130")
	oldName := h.jobs()[0].Name

	c := h.campaign("ecc2k-130")
	c.Spec.Workers.Image = "ghcr.io/example/ecc2k130-walker:2.0"
	h.update(c)
	res := h.reconcile("ecc2k-130")
	// The fake client deletes synchronously, so the handover completes on the
	// next pass; the reconciler must not have created the successor yet.
	if len(h.jobs()) != 0 {
		t.Fatalf("superseded job must be deleted before a successor exists: %+v", h.jobs())
	}
	if res.RequeueAfter != handoverRequeue {
		t.Fatalf("expected handover requeue, got %v", res.RequeueAfter)
	}
	h.reconcile("ecc2k-130")
	jobs := h.jobs()
	if len(jobs) != 1 || jobs[0].Name == oldName {
		t.Fatalf("expected a new job after handover, got %+v", jobs)
	}
	if jobs[0].Spec.Template.Spec.Containers[0].Image != "ghcr.io/example/ecc2k130-walker:2.0" {
		t.Fatal("new job must carry the new image")
	}
}

func TestReconcileNonElasticResizeRecreates(t *testing.T) {
	campaign := sampleCampaign()
	campaign.Spec.Scheduling.Elastic = ptr.To(false)
	h := newHarness(t, campaign, nil)
	h.reconcile("ecc2k-130")
	first := h.jobs()[0]
	if _, elasticAnnotated := first.Annotations[v1alpha1.KueueElasticJobAnnotation]; elasticAnnotated {
		t.Fatal("non-elastic jobs must not carry the elastic annotation")
	}
	c := h.campaign("ecc2k-130")
	c.Spec.Workers.Parallelism = 2
	h.update(c)
	h.reconcile("ecc2k-130")
	if len(h.jobs()) != 0 {
		t.Fatal("non-elastic resize must delete the job first")
	}
	h.reconcile("ecc2k-130")
	jobs := h.jobs()
	if len(jobs) != 1 || ptr.Deref(jobs[0].Spec.Parallelism, 0) != 2 {
		t.Fatalf("recreated job should run 2, got %+v", jobs)
	}
	if jobs[0].Name != first.Name {
		t.Fatal("parallelism is not part of the spec hash; the name must be stable")
	}
}

func TestReconcileIgnoresForeignJobs(t *testing.T) {
	campaign := sampleCampaign()
	h := newHarness(t, campaign, nil)
	foreign := &batchv1.Job{ObjectMeta: metav1.ObjectMeta{
		Name: "someone-elses", Namespace: "cryptanalysis",
		Labels: map[string]string{v1alpha1.LabelCampaign: "ecc2k-130"},
	}, Spec: batchv1.JobSpec{Template: corev1.PodTemplateSpec{Spec: corev1.PodSpec{
		RestartPolicy: corev1.RestartPolicyNever,
		Containers:    []corev1.Container{{Name: "x", Image: "x"}},
	}}}}
	if err := h.client.Create(context.Background(), foreign); err != nil {
		t.Fatal(err)
	}
	h.reconcile("ecc2k-130")
	if len(h.jobs()) != 2 {
		t.Fatalf("a job not owned by the campaign must be left alone, got %d jobs", len(h.jobs()))
	}
}
