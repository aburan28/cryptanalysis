package controller

import (
	"errors"
	"testing"
	"time"

	"k8s.io/utils/ptr"

	"github.com/aburan28/cryptanalysis/controller/api/v1alpha1"
)

func policyCampaign(desired int32, bp *v1alpha1.BackpressureSpec) *v1alpha1.Campaign {
	c := &v1alpha1.Campaign{}
	c.Spec.Workers.Parallelism = desired
	c.Spec.Coordinator.StatusURL = "https://status.example/status.json"
	c.Spec.Backpressure = bp
	return c
}

func feedAt(state string, generated time.Time) *Feed {
	return &Feed{QueueState: state, GeneratedAt: generated, State: "COLLECTING"}
}

func TestDecideWithoutPolicyRunsDesired(t *testing.T) {
	now := time.Now()
	c := policyCampaign(8, nil)
	d := Decide(c, feedAt(PressureRed, now), nil, 0, nil, now)
	if d.Effective != 8 || d.Reason != ReasonNoPolicy {
		t.Fatalf("expected desired parallelism without policy, got %+v", d)
	}
}

func TestDecideSuspendWins(t *testing.T) {
	now := time.Now()
	c := policyCampaign(8, &v1alpha1.BackpressureSpec{StaleAfterSeconds: 900, RecoverySeconds: 300})
	c.Spec.Suspend = true
	d := Decide(c, feedAt(PressureGreen, now), nil, 8, nil, now)
	if !d.Suspended || d.Effective != 0 || d.Reason != ReasonSuspended {
		t.Fatalf("suspend must release the job, got %+v", d)
	}
}

func TestDecideCollisionPolicy(t *testing.T) {
	now := time.Now()
	c := policyCampaign(8, nil)
	feed := feedAt(PressureGreen, now)
	feed.Collisions = 1

	d := Decide(c, feed, nil, 8, nil, now)
	if d.Suspended || !d.Collision || d.Effective != 8 {
		t.Fatalf("Continue policy must keep walking, got %+v", d)
	}
	c.Spec.OnCollision = v1alpha1.CollisionSuspend
	d = Decide(c, feed, nil, 8, nil, now)
	if !d.Suspended || d.Reason != ReasonCollisionSuspend {
		t.Fatalf("Suspend policy must release the job, got %+v", d)
	}
}

func TestDecidePressureLadder(t *testing.T) {
	now := time.Now()
	bp := &v1alpha1.BackpressureSpec{
		RedParallelism: 0, YellowParallelism: ptr.To[int32](4),
		RecoverySeconds: 300, StaleAfterSeconds: 900,
	}
	c := policyCampaign(8, bp)

	green := Decide(c, feedAt(PressureGreen, now), nil, 8, nil, now)
	if green.Effective != 8 || green.Reason != ReasonPressureGreen || !green.Fresh {
		t.Fatalf("green: %+v", green)
	}
	yellow := Decide(c, feedAt(PressureYellow, now), nil, 8, nil, now)
	if yellow.Effective != 4 || yellow.Reason != ReasonPressureYellow {
		t.Fatalf("yellow: %+v", yellow)
	}
	red := Decide(c, feedAt(PressureRed, now), nil, 4, nil, now)
	if red.Effective != 0 || red.Reason != ReasonPressureRed || red.LastRed == nil {
		t.Fatalf("red: %+v", red)
	}

	// Leaving red: hold until the recovery window passes.
	soon := now.Add(2 * time.Minute)
	hold := Decide(c, feedAt(PressureGreen, soon), nil, 0, red.LastRed, soon)
	if hold.Effective != 0 || hold.Reason != ReasonRecovering {
		t.Fatalf("recovery hold: %+v", hold)
	}
	later := now.Add(6 * time.Minute)
	restored := Decide(c, feedAt(PressureGreen, later), nil, 0, red.LastRed, later)
	if restored.Effective != 8 || restored.Reason != ReasonPressureGreen {
		t.Fatalf("recovery restore: %+v", restored)
	}

	// Decreases are never delayed by the recovery window.
	down := Decide(c, feedAt(PressureYellow, soon), nil, 8, red.LastRed, soon)
	if down.Effective != 4 {
		t.Fatalf("scale down during recovery: %+v", down)
	}
}

func TestDecideStaleOrMissingFeedHolds(t *testing.T) {
	now := time.Now()
	bp := &v1alpha1.BackpressureSpec{RecoverySeconds: 300, StaleAfterSeconds: 900}
	c := policyCampaign(8, bp)

	stale := Decide(c, feedAt(PressureGreen, now.Add(-time.Hour)), nil, 3, nil, now)
	if stale.Effective != 3 || stale.Fresh || stale.Reason != ReasonFeedStale {
		t.Fatalf("stale feed must hold, got %+v", stale)
	}
	missing := Decide(c, nil, errors.New("boom"), 3, nil, now)
	if missing.Effective != 3 || missing.Fresh || missing.Reason != ReasonFeedUnavailable {
		t.Fatalf("missing feed must hold, got %+v", missing)
	}
	unknown := Decide(c, feedAt("purple", now), nil, 3, nil, now)
	if unknown.Effective != 3 || unknown.Reason != ReasonPressureUnknown || unknown.QueueState != PressureUnknown {
		t.Fatalf("unknown pressure must hold, got %+v", unknown)
	}
}

func TestParseFeed(t *testing.T) {
	body := []byte(`{"state":"INGEST_BEHIND","generated_at":"2026-09-20T12:00:00Z","collisions":0,"dps":42,"walkers":3,"queue":{"state":"Yellow","messages":120}}`)
	feed, err := ParseFeed(body)
	if err != nil {
		t.Fatal(err)
	}
	if feed.QueueState != PressureYellow || feed.QueueMessages != 120 || feed.DPs != 42 || feed.State != "INGEST_BEHIND" {
		t.Fatalf("unexpected feed %+v", feed)
	}
	if _, err := ParseFeed([]byte(`{"state":"EMPTY"}`)); err == nil {
		t.Fatal("feed without generated_at must be rejected")
	}
	if _, err := ParseFeed([]byte(`not json`)); err == nil {
		t.Fatal("invalid JSON must be rejected")
	}
}
