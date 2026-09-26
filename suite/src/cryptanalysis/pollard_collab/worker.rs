//! A worker *lane*: claims units, walks them, and emits check-ins.
//!
//! One lane is one thread's worth of sequential walking.  A node runs
//! as many lanes as it has cores; every lane has its own id
//! (`node.lane`) and sequence counter so their reports never collide.
//! Lanes share the node's [`SharedState`] behind a mutex and touch it
//! only at check-in time, so the walk itself runs lock-free.

use std::sync::Mutex;

use num_bigint::BigUint;

use super::job::{hex_of, JobContext, PROTOCOL_VERSION};
use super::state::{now_secs, CheckIn, SharedState, UnitReport};
use super::walk::{run_walker, WalkerOutcome};

/// Lane tuning.
#[derive(Clone, Debug)]
pub struct LaneOptions {
    /// Origin id for this lane's check-ins (`node.lane`).
    pub lane_id: String,
    /// Emit a check-in every this many walkers (and always at unit end).
    pub checkin_every: u64,
    /// Seconds a claim stays live without a fresh check-in.
    pub lease_secs: u64,
    /// Candidate spread for unit selection (see
    /// [`SharedState::next_unit`]).
    pub claim_window: usize,
    /// Cap on units for the whole job; `0` = unbounded.
    pub max_units: u64,
    /// Stop after this many walkers in this lane; `0` = until solved.
    pub max_walkers: u64,
}

impl LaneOptions {
    pub fn new(lane_id: &str) -> Self {
        Self {
            lane_id: lane_id.to_string(),
            checkin_every: 64,
            lease_secs: 120,
            claim_window: 4,
            max_units: 0,
            max_walkers: 0,
        }
    }
}

/// What a lane did before returning.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct LaneSummary {
    pub walkers: u64,
    pub steps: u64,
    pub dps: u64,
    pub dead_trails: u64,
    pub units_completed: u64,
    pub checkins: u64,
    pub solution: Option<BigUint>,
}

/// Run one lane until the job is solved, the walker budget is spent,
/// no unit is left, or `should_stop` says so.  `on_checkin` is called
/// with every check-in *after* it has been merged locally — the
/// transport hook (write a mailbox file, mark for gossip, …).
pub fn run_lane(
    ctx: &JobContext,
    state: &Mutex<SharedState>,
    opts: &LaneOptions,
    on_checkin: &mut dyn FnMut(&CheckIn),
    should_stop: &dyn Fn() -> bool,
) -> LaneSummary {
    let mut sum = LaneSummary::default();
    let every = opts.checkin_every.max(1);
    // `steps`/`dps`/`dead_trails` in `LaneSummary` are lane totals,
    // accumulated per walker below; the per-unit counters passed to
    // `emit` are what goes on the wire.

    'units: loop {
        if should_stop() {
            break;
        }
        // Choose a unit and announce the claim in one critical
        // section, so two lanes of this node can never pick the same
        // unit between the choice and the announcement.
        let (unit, resume_from, claim) = {
            let mut st = state.lock().unwrap();
            if let Some(x) = &st.solution {
                sum.solution = Some(x.clone());
                break;
            }
            let (unit, resume_from) = match st.next_unit(
                &opts.lane_id,
                now_secs(),
                opts.lease_secs,
                opts.claim_window,
                opts.max_units,
            ) {
                Some(u) => u,
                None => break,
            };
            let report = UnitReport {
                unit,
                walkers_done: resume_from,
                steps: 0,
                dps: 0,
                dead_trails: 0,
                completed: false,
            };
            let (cis, _) = merge_locked(ctx, &mut st, opts, &mut sum, report, Vec::new());
            (unit, resume_from, cis)
        };
        publish(&claim, on_checkin, &mut sum);
        let (first, last) = ctx.unit_range(unit);
        let mut cursor = first + resume_from;
        // Cumulative counters for this unit (this lane's own share).
        let mut u_steps = 0u64;
        let mut u_dps = 0u64;
        let mut u_dead = 0u64;
        let mut pending = Vec::new();
        let mut since_checkin = 0u64;

        while cursor < last {
            if should_stop() {
                break 'units;
            }
            match run_walker(ctx, cursor) {
                WalkerOutcome::Dp(rec) => {
                    u_steps += rec.steps;
                    u_dps += 1;
                    sum.steps += rec.steps;
                    sum.dps += 1;
                    pending.push(rec);
                }
                WalkerOutcome::DeadTrail { steps } => {
                    u_steps += steps;
                    u_dead += 1;
                    sum.steps += steps;
                    sum.dead_trails += 1;
                }
            }
            cursor += 1;
            sum.walkers += 1;
            since_checkin += 1;
            let done = cursor == last;
            let budget_out = opts.max_walkers > 0 && sum.walkers >= opts.max_walkers;
            if since_checkin >= every || done || budget_out {
                let report = UnitReport {
                    unit,
                    walkers_done: cursor - first,
                    steps: u_steps,
                    dps: u_dps,
                    dead_trails: u_dead,
                    completed: done,
                };
                let (cis, solved) = {
                    let mut st = state.lock().unwrap();
                    merge_locked(
                        ctx,
                        &mut st,
                        opts,
                        &mut sum,
                        report,
                        std::mem::take(&mut pending),
                    )
                };
                publish(&cis, on_checkin, &mut sum);
                since_checkin = 0;
                if done {
                    sum.units_completed += 1;
                }
                if solved || budget_out {
                    break 'units;
                }
            }
        }
    }
    if let Ok(st) = state.lock() {
        if sum.solution.is_none() {
            sum.solution = st.solution.clone();
        }
    }
    sum
}

/// Build one check-in from a unit report plus DP records and merge it
/// into the (already locked) state.  Returns the check-ins to publish
/// — the report, plus a solution announcement if this merge solved
/// the job — and whether the state now holds a solution.
fn merge_locked(
    ctx: &JobContext,
    st: &mut SharedState,
    opts: &LaneOptions,
    sum: &mut LaneSummary,
    report: UnitReport,
    records: Vec<super::walk::DpRecord>,
) -> (Vec<CheckIn>, bool) {
    let seq = st.next_seq(&opts.lane_id);
    let ci = CheckIn {
        version: PROTOCOL_VERSION,
        job_id: ctx.job_id.clone(),
        peer: opts.lane_id.clone(),
        seq,
        time: now_secs(),
        units: vec![report],
        dps: records,
        solution: None,
    };
    // Our own records need no re-verification.
    let out = st
        .apply(ctx, &ci, now_secs(), false)
        .expect("own check-in is valid");
    let mut cis = vec![ci];
    if out.solved_now {
        // Announce the solution in a second, tiny check-in so peers
        // that receive it can stop without re-deriving.
        let seq2 = st.next_seq(&opts.lane_id);
        let ann = CheckIn {
            version: PROTOCOL_VERSION,
            job_id: ctx.job_id.clone(),
            peer: opts.lane_id.clone(),
            seq: seq2,
            time: now_secs(),
            units: Vec::new(),
            dps: Vec::new(),
            solution: st.solution.as_ref().map(hex_of),
        };
        st.apply(ctx, &ann, now_secs(), false)
            .expect("announcement is valid");
        sum.solution = st.solution.clone();
        cis.push(ann);
    }
    (cis, st.solution.is_some())
}

/// Hand merged check-ins to the transport hook (outside the lock).
fn publish(cis: &[CheckIn], on_checkin: &mut dyn FnMut(&CheckIn), sum: &mut LaneSummary) {
    for ci in cis {
        on_checkin(ci);
        sum.checkins += 1;
    }
}

#[cfg(test)]
mod tests {
    use super::super::job::{demo_curve, JobSpec};
    use super::*;
    use std::sync::Arc;

    fn ctx(secret: u32, negation: bool) -> JobContext {
        let curve = demo_curve("demo-mid").unwrap();
        let q = curve
            .generator()
            .scalar_mul(&BigUint::from(secret), &curve.a_fe());
        let mut spec = JobSpec::new(&curve, &q, "lane", 11).unwrap();
        spec.dp_bits = 3;
        spec.unit_size = 32;
        spec.negation_map = negation;
        spec.build().unwrap()
    }

    #[test]
    fn single_lane_solves() {
        for negation in [false, true] {
            let c = ctx(60_001, negation);
            let state = Mutex::new(SharedState::new(&c));
            let mut seen = 0u64;
            let sum = run_lane(
                &c,
                &state,
                &LaneOptions {
                    checkin_every: 8,
                    ..LaneOptions::new("solo.0")
                },
                &mut |_ci| seen += 1,
                &|| false,
            );
            assert_eq!(
                sum.solution,
                Some(BigUint::from(60_001u32)),
                "negation={negation}"
            );
            assert_eq!(seen, sum.checkins);
            let st = state.lock().unwrap();
            assert_eq!(st.solution, sum.solution);
            // The announcement is the last check-in in the log.
            let vv = st.version_vector();
            let last = st.checkin("solo.0", vv["solo.0"]).unwrap();
            assert!(last.solution.is_some());
        }
    }

    #[test]
    fn lanes_on_one_node_split_units_and_stop_together() {
        let c = Arc::new(ctx(12_345, false));
        let state = Arc::new(Mutex::new(SharedState::new(&c)));
        let handles: Vec<_> = (0..3)
            .map(|lane| {
                let c = Arc::clone(&c);
                let state = Arc::clone(&state);
                std::thread::spawn(move || {
                    run_lane(
                        &c,
                        &state,
                        &LaneOptions {
                            checkin_every: 4,
                            claim_window: 1,
                            ..LaneOptions::new(&format!("node.{lane}"))
                        },
                        &mut |_| {},
                        &|| false,
                    )
                })
            })
            .collect();
        let sums: Vec<LaneSummary> = handles.into_iter().map(|h| h.join().unwrap()).collect();
        let st = state.lock().unwrap();
        assert_eq!(st.solution, Some(BigUint::from(12_345u32)));
        for s in &sums {
            assert_eq!(s.solution, st.solution);
        }
        // No two lanes ever reported the same unit.
        let mut owners: std::collections::HashMap<u64, String> = Default::default();
        for ci in st.delta_for(&Default::default()) {
            for u in &ci.units {
                let prev = owners.insert(u.unit, ci.peer.clone());
                assert!(
                    prev.is_none() || prev.as_deref() == Some(ci.peer.as_str()),
                    "unit {} worked by two lanes",
                    u.unit
                );
            }
        }
    }

    #[test]
    fn walker_budget_and_stop_flag_are_honoured() {
        let c = ctx(777, false);
        let state = Mutex::new(SharedState::new(&c));
        let sum = run_lane(
            &c,
            &state,
            &LaneOptions {
                max_walkers: 5,
                claim_window: 1,
                ..LaneOptions::new("b.0")
            },
            &mut |_| {},
            &|| false,
        );
        assert_eq!(sum.walkers, 5);
        let sum = run_lane(&c, &state, &LaneOptions::new("b.1"), &mut |_| {}, &|| true);
        assert_eq!(sum.walkers, 0);
        // A bounded job with all units taken yields nothing.
        let sum = run_lane(
            &c,
            &state,
            &LaneOptions {
                max_units: 1,
                claim_window: 1,
                ..LaneOptions::new("b.0")
            },
            &mut |_| {},
            &|| false,
        );
        assert_eq!(
            sum.walkers, 27,
            "resumes own unit at walker 5, then no unit is left"
        );
    }
}
