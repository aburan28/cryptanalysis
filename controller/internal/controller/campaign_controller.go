package controller

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/client-go/tools/record"
	"k8s.io/utils/ptr"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"

	"github.com/aburan28/cryptanalysis/controller/api/v1alpha1"
)

const (
	// defaultRequeue bounds how long a Campaign goes unobserved without events.
	defaultRequeue = 5 * time.Minute
	// handoverRequeue is the wait while a superseded Job finishes deleting.
	handoverRequeue = 5 * time.Second
)

// CampaignReconciler turns Campaigns into Kueue-scheduled walker Jobs.
type CampaignReconciler struct {
	client.Client
	Scheme   *runtime.Scheme
	Recorder record.EventRecorder
	Feed     FeedSource
	// Now is injectable for tests.
	Now func() time.Time

	mu    sync.Mutex
	feeds map[string]cachedFeed
}

type cachedFeed struct {
	fetchedAt time.Time
	feed      *Feed
	err       error
}

// +kubebuilder:rbac:groups=cryptanalysis.io,resources=campaigns,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=cryptanalysis.io,resources=campaigns/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=cryptanalysis.io,resources=campaigns/finalizers,verbs=update
// +kubebuilder:rbac:groups=batch,resources=jobs,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups="",resources=events,verbs=create;patch

// SetupWithManager registers the reconciler.
func (r *CampaignReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		Named("campaign").
		For(&v1alpha1.Campaign{}).
		Owns(&batchv1.Job{}).
		Complete(r)
}

func (r *CampaignReconciler) now() time.Time {
	if r.Now != nil {
		return r.Now()
	}
	return time.Now()
}

// Reconcile drives one Campaign towards its desired Job.
func (r *CampaignReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)
	campaign := &v1alpha1.Campaign{}
	if err := r.Get(ctx, req.NamespacedName, campaign); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	if !campaign.DeletionTimestamp.IsZero() {
		return ctrl.Result{}, nil
	}

	now := r.now()
	feed, feedErr := r.currentFeed(ctx, campaign, now)
	var lastRed *time.Time
	if campaign.Status.LastRedObserved != nil {
		t := campaign.Status.LastRedObserved.Time
		lastRed = &t
	}
	decision := Decide(campaign, feed, feedErr, campaign.Status.EffectiveParallelism, lastRed, now)

	jobs := &batchv1.JobList{}
	if err := r.List(ctx, jobs, client.InNamespace(campaign.Namespace),
		client.MatchingLabels{v1alpha1.LabelCampaign: campaign.Name}); err != nil {
		return ctrl.Result{}, err
	}
	hash := SpecHash(campaign)
	var current *batchv1.Job
	var superseded []batchv1.Job
	for i := range jobs.Items {
		job := &jobs.Items[i]
		if !metav1.IsControlledBy(job, campaign) {
			continue
		}
		if job.Labels[v1alpha1.LabelSpecHash] == hash && job.DeletionTimestamp.IsZero() {
			current = job
		} else {
			superseded = append(superseded, *job)
		}
	}

	requeue := defaultRequeue
	if campaign.Spec.Backpressure != nil && campaign.Spec.Coordinator.StatusURL != "" {
		requeue = time.Duration(campaign.Spec.Backpressure.PollIntervalSeconds) * time.Second
	}

	var actionErr error
	switch {
	case decision.Effective == 0:
		// Suspended or fully backpressured: release every Job and its quota.
		for i := range jobs.Items {
			if err := r.deleteJob(ctx, &jobs.Items[i]); err != nil {
				actionErr = err
			}
		}
		if actionErr == nil && (current != nil || len(superseded) > 0) {
			r.Recorder.Eventf(campaign, corev1.EventTypeNormal, "WalkersReleased",
				"released walker Job(s): %s", decision.Reason)
		}
		current = nil
	default:
		pendingDeletes := false
		for i := range superseded {
			if superseded[i].DeletionTimestamp.IsZero() {
				if err := r.deleteJob(ctx, &superseded[i]); err != nil {
					actionErr = err
					continue
				}
				r.Recorder.Eventf(campaign, corev1.EventTypeNormal, "JobHandover",
					"deleting superseded Job %s", superseded[i].Name)
			}
			pendingDeletes = true
		}
		if pendingDeletes {
			// Never run two generations at once: wait for quota to return.
			requeue = handoverRequeue
		} else if current == nil {
			job, dropped := BuildJob(campaign, decision.Effective)
			if len(dropped) > 0 {
				r.Recorder.Eventf(campaign, corev1.EventTypeWarning, "EnvOverrideIgnored",
					"workers.env may not override the walker contract: %s", strings.Join(dropped, ", "))
			}
			if err := controllerutil.SetControllerReference(campaign, job, r.Scheme); err != nil {
				return ctrl.Result{}, err
			}
			if err := r.Create(ctx, job); err != nil && !apierrors.IsAlreadyExists(err) {
				actionErr = err
			} else {
				r.Recorder.Eventf(campaign, corev1.EventTypeNormal, "JobCreated",
					"created walker Job %s with parallelism %d on queue %s",
					job.Name, decision.Effective, campaign.Spec.Scheduling.QueueName)
				current = job
			}
		} else if ptr.Deref(current.Spec.Parallelism, 0) != decision.Effective {
			if elastic(campaign) {
				patch := client.MergeFrom(current.DeepCopy())
				current.Spec.Parallelism = ptr.To(decision.Effective)
				if err := r.Patch(ctx, current, patch); err != nil {
					actionErr = err
				} else {
					r.Recorder.Eventf(campaign, corev1.EventTypeNormal, "WalkersScaled",
						"parallelism %d: %s", decision.Effective, decision.Reason)
				}
			} else {
				// Kueue rejects resizing an admitted non-elastic Job; hand over.
				if err := r.deleteJob(ctx, current); err != nil {
					actionErr = err
				} else {
					r.Recorder.Eventf(campaign, corev1.EventTypeNormal, "JobHandover",
						"recreating Job %s to change parallelism to %d", current.Name, decision.Effective)
				}
				current = nil
				requeue = handoverRequeue
			}
		}
	}

	if err := r.updateStatus(ctx, campaign, current, decision, feed, now); err != nil {
		return ctrl.Result{}, err
	}
	if actionErr != nil {
		logger.Error(actionErr, "campaign action failed")
		return ctrl.Result{}, actionErr
	}
	return ctrl.Result{RequeueAfter: requeue}, nil
}

func (r *CampaignReconciler) deleteJob(ctx context.Context, job *batchv1.Job) error {
	if !job.DeletionTimestamp.IsZero() {
		return nil
	}
	err := r.Delete(ctx, job, client.PropagationPolicy(metav1.DeletePropagationForeground))
	return client.IgnoreNotFound(err)
}

// currentFeed returns the cached feed for the Campaign, refreshing it once per
// poll interval so event storms do not hammer the coordinator.
func (r *CampaignReconciler) currentFeed(ctx context.Context, c *v1alpha1.Campaign, now time.Time) (*Feed, error) {
	url := c.Spec.Coordinator.StatusURL
	if url == "" || r.Feed == nil {
		return nil, nil
	}
	interval := time.Duration(60) * time.Second
	if c.Spec.Backpressure != nil && c.Spec.Backpressure.PollIntervalSeconds > 0 {
		interval = time.Duration(c.Spec.Backpressure.PollIntervalSeconds) * time.Second
	}
	key := c.Namespace + "/" + c.Name
	r.mu.Lock()
	if r.feeds == nil {
		r.feeds = map[string]cachedFeed{}
	}
	cached, ok := r.feeds[key]
	r.mu.Unlock()
	if ok && now.Sub(cached.fetchedAt) < interval {
		return cached.feed, cached.err
	}
	feed, err := r.Feed.Fetch(ctx, url)
	r.mu.Lock()
	r.feeds[key] = cachedFeed{fetchedAt: now, feed: feed, err: err}
	r.mu.Unlock()
	return feed, err
}

func (r *CampaignReconciler) updateStatus(ctx context.Context, c *v1alpha1.Campaign, job *batchv1.Job, d Decision, feed *Feed, now time.Time) error {
	patch := client.MergeFrom(c.DeepCopy())
	s := &c.Status
	s.ObservedGeneration = c.Generation
	s.DesiredParallelism = c.Spec.Workers.Parallelism
	s.EffectiveParallelism = d.Effective
	s.QueueState = d.QueueState
	if d.LastRed != nil {
		s.LastRedObserved = &metav1.Time{Time: *d.LastRed}
	}
	if feed != nil {
		s.QueueMessages = feed.QueueMessages
		s.CoordinatorState = feed.State
		s.Collisions = feed.Collisions
		s.DistinguishedPoints = feed.DPs
	}
	if c.Spec.Coordinator.StatusURL != "" {
		s.LastStatusPoll = &metav1.Time{Time: now}
	}

	admitted, ready, failed := false, int32(0), false
	if job != nil {
		s.JobName = job.Name
		s.ActiveWorkers = job.Status.Active
		ready = ptr.Deref(job.Status.Ready, 0)
		s.ReadyWorkers = ready
		admitted = !ptr.Deref(job.Spec.Suspend, false)
		for _, cond := range job.Status.Conditions {
			if cond.Type == batchv1.JobFailed && cond.Status == corev1.ConditionTrue {
				failed = true
			}
		}
	} else {
		s.JobName, s.ActiveWorkers, s.ReadyWorkers = "", 0, 0
	}

	setCondition(s, v1alpha1.ConditionAdmitted, admitted, map[bool]string{true: "JobUnsuspended", false: "AwaitingKueueAdmission"}[admitted],
		fmt.Sprintf("job=%q", s.JobName))
	workersReady := job != nil && admitted && d.Effective > 0 && ready >= d.Effective
	setCondition(s, v1alpha1.ConditionWorkersReady, workersReady, map[bool]string{true: "AllWalkersReady", false: "WalkersStarting"}[workersReady],
		fmt.Sprintf("%d/%d ready", ready, d.Effective))
	backpressured := !d.Suspended && d.Effective < c.Spec.Workers.Parallelism
	setCondition(s, v1alpha1.ConditionBackpressured, backpressured, d.Reason,
		fmt.Sprintf("queue %s; effective %d of %d", d.QueueState, d.Effective, c.Spec.Workers.Parallelism))
	freshReason := "FeedCurrent"
	switch {
	case c.Spec.Coordinator.StatusURL == "":
		freshReason = ReasonNoFeedConfigured
	case !d.Fresh:
		freshReason = "FeedStaleOrUnavailable"
	}
	setCondition(s, v1alpha1.ConditionStatusFresh, d.Fresh, freshReason, feedMessage(feed, now))
	setCondition(s, v1alpha1.ConditionCollisionRecorded, d.Collision, map[bool]string{true: ReasonCollisionRecorded, false: "NoCollision"}[d.Collision],
		fmt.Sprintf("%d collision(s) reported by the coordinator", s.Collisions))

	switch {
	case failed:
		s.Phase = v1alpha1.PhaseFailed
	case d.Suspended:
		s.Phase = v1alpha1.PhaseSuspended
	case backpressured:
		s.Phase = v1alpha1.PhaseBackpressured
	case job == nil:
		s.Phase = v1alpha1.PhasePending
	case admitted:
		s.Phase = v1alpha1.PhaseRunning
	default:
		s.Phase = v1alpha1.PhaseQueued
	}
	return r.Status().Patch(ctx, c, patch)
}

func setCondition(s *v1alpha1.CampaignStatus, kind string, ok bool, reason, message string) {
	status := metav1.ConditionFalse
	if ok {
		status = metav1.ConditionTrue
	}
	meta.SetStatusCondition(&s.Conditions, metav1.Condition{
		Type: kind, Status: status, Reason: reason, Message: message,
		ObservedGeneration: s.ObservedGeneration,
	})
}

func feedMessage(feed *Feed, now time.Time) string {
	if feed == nil {
		return "no status document"
	}
	return fmt.Sprintf("generated %s ago; state %s", now.Sub(feed.GeneratedAt).Truncate(time.Second), feed.State)
}
