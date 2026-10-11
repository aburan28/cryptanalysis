package controller

import (
	"time"

	"github.com/aburan28/cryptanalysis/controller/api/v1alpha1"
)

// Pressure states reported by the coordinator.
const (
	PressureGreen   = "green"
	PressureYellow  = "yellow"
	PressureRed     = "red"
	PressureUnknown = "unknown"
)

// Decision is the outcome of applying the Campaign policy to the feed.
type Decision struct {
	// Effective is the parallelism the Job should run; zero releases it.
	Effective int32
	// Reason is a condition reason describing the decision.
	Reason string
	// QueueState is the normalised pressure state used for the decision.
	QueueState string
	// Fresh is false when the feed was missing, unparsable or stale.
	Fresh bool
	// Suspended is true when the Job must not exist at all.
	Suspended bool
	// Collision is true once the coordinator reported a collision.
	Collision bool
	// LastRed carries forward the hysteresis timestamp.
	LastRed *time.Time
}

// Decision reasons.
const (
	ReasonSuspended         = "SpecSuspended"
	ReasonCollisionSuspend  = "CollisionPolicySuspend"
	ReasonNoPolicy          = "NoBackpressurePolicy"
	ReasonFeedStale         = "FeedStaleHoldingParallelism"
	ReasonFeedUnavailable   = "FeedUnavailableHoldingParallelism"
	ReasonPressureRed       = "PressureRed"
	ReasonPressureYellow    = "PressureYellow"
	ReasonRecovering        = "RecoveringFromRed"
	ReasonPressureGreen     = "PressureGreen"
	ReasonPressureUnknown   = "PressureUnknownHoldingParallelism"
	ReasonNoFeedConfigured  = "NoStatusFeed"
	ReasonCollisionRecorded = "CollisionRecorded"
)

// Decide maps the Campaign spec, the latest feed and the previous effective
// parallelism to a scheduling decision. feed may be nil when the fetch failed.
func Decide(c *v1alpha1.Campaign, feed *Feed, feedErr error, current int32, lastRed *time.Time, now time.Time) Decision {
	desired := c.Spec.Workers.Parallelism
	d := Decision{Effective: desired, QueueState: PressureUnknown, LastRed: lastRed}

	if feed != nil {
		d.Collision = feed.Collisions > 0
	}
	if c.Spec.Suspend {
		d.Effective, d.Suspended, d.Reason = 0, true, ReasonSuspended
	} else if d.Collision && c.Spec.OnCollision == v1alpha1.CollisionSuspend {
		d.Effective, d.Suspended, d.Reason = 0, true, ReasonCollisionSuspend
	}

	bp := c.Spec.Backpressure
	if bp == nil || c.Spec.Coordinator.StatusURL == "" {
		if d.Reason == "" {
			d.Reason = ReasonNoPolicy
		}
		d.Fresh = feed != nil && feedErr == nil
		if feed != nil {
			d.QueueState = normalisePressure(feed.QueueState)
		}
		return d
	}

	stale := time.Duration(bp.StaleAfterSeconds) * time.Second
	switch {
	case feedErr != nil || feed == nil:
		d.Fresh = false
		if !d.Suspended {
			d.Effective, d.Reason = current, ReasonFeedUnavailable
		}
		return d
	case now.Sub(feed.GeneratedAt) > stale:
		d.Fresh = false
		d.QueueState = normalisePressure(feed.QueueState)
		if !d.Suspended {
			d.Effective, d.Reason = current, ReasonFeedStale
		}
		return d
	}

	d.Fresh = true
	d.QueueState = normalisePressure(feed.QueueState)
	if d.Suspended {
		return d
	}

	var candidate int32
	var reason string
	switch d.QueueState {
	case PressureRed:
		t := now
		d.LastRed = &t
		candidate, reason = bp.RedParallelism, ReasonPressureRed
	case PressureYellow:
		candidate, reason = desired, ReasonPressureYellow
		if bp.YellowParallelism != nil {
			candidate = *bp.YellowParallelism
		}
	case PressureGreen:
		candidate, reason = desired, ReasonPressureGreen
	default:
		d.Effective, d.Reason = current, ReasonPressureUnknown
		return d
	}

	recovery := time.Duration(bp.RecoverySeconds) * time.Second
	if candidate > current && d.LastRed != nil && now.Sub(*d.LastRed) < recovery && d.QueueState != PressureRed {
		d.Effective, d.Reason = current, ReasonRecovering
		return d
	}
	d.Effective, d.Reason = candidate, reason
	return d
}

func normalisePressure(state string) string {
	switch state {
	case PressureGreen, PressureYellow, PressureRed:
		return state
	default:
		return PressureUnknown
	}
}
