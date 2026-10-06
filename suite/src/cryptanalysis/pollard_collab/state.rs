//! Replicated job state and the check-in message that advances it.
//!
//! # Why a CRDT
//!
//! With no central server every peer holds its own copy of the job
//! state and merges whatever check-ins reach it, in whatever order,
//! possibly twice.  So the state is built only from operations that
//! are **commutative, associative and idempotent**:
//!
//! - the DP table is a grow-only set keyed by the DP (first writer
//!   wins on the value, but any second writer with *different*
//!   coefficients is a collision — the thing we want);
//! - each peer's report on a unit is a max-register ordered by the
//!   peer's own sequence number;
//! - the solution is a write-once register (verified before accepted);
//! - the check-in log is a grow-only set keyed by `(peer, seq)`, and
//!   doubles as the gossip payload: a peer that knows `{peer ↦ max
//!   seq}` can be sent exactly the check-ins it lacks.
//!
//! Two peers that have seen the same set of check-ins therefore hold
//! identical state, whatever the delivery order — see
//! `merge_is_order_independent` in the tests.

use std::collections::{BTreeMap, HashMap};

use num_bigint::BigUint;
use num_traits::Zero;
use serde::{Deserialize, Serialize};

use super::job::{hex_of, parse_hex, JobContext, PROTOCOL_VERSION};
use super::walk::DpRecord;
use crate::ecc::point::Point;
use crate::utils::mod_inverse;

/// Progress a peer claims on one work unit.  Cumulative, so a later
/// report supersedes an earlier one from the same peer.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct UnitReport {
    pub unit: u64,
    /// Walkers of this unit finished so far (the resume cursor).
    pub walkers_done: u64,
    pub steps: u64,
    pub dps: u64,
    pub dead_trails: u64,
    pub completed: bool,
}

/// The one message of the protocol.  Peers emit them periodically and
/// forward everyone else's; state is the merge of all of them.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CheckIn {
    pub version: u32,
    pub job_id: String,
    /// Origin lane id (`node.lane`).  Sequence numbers are per origin.
    pub peer: String,
    pub seq: u64,
    /// Origin wall clock (seconds).  Informational; leases use the
    /// receiver's clock so skew cannot orphan a unit.
    pub time: u64,
    pub units: Vec<UnitReport>,
    pub dps: Vec<DpRecord>,
    /// Hex `x` with `x·P = Q`, once known.  Verified on receipt.
    pub solution: Option<String>,
}

/// Stored DP.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DpEntry {
    pub a: BigUint,
    pub b: BigUint,
    pub y: BigUint,
    pub walker: u64,
    pub peer: String,
}

#[derive(Clone, Debug)]
struct Claim {
    seq: u64,
    received_at: u64,
    report: UnitReport,
}

/// Merged view of one unit.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct UnitView {
    pub unit: u64,
    pub completed: bool,
    /// Highest resume cursor reported by anyone.
    pub walkers_done: u64,
    pub steps: u64,
    pub dps: u64,
    pub dead_trails: u64,
    /// Peer whose lease on the unit is still live, if any.
    pub owner: Option<String>,
}

/// Aggregate progress for status displays.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Progress {
    pub steps: u64,
    pub dps_stored: usize,
    pub dead_trails: u64,
    pub units_completed: u64,
    pub units_active: u64,
    pub peers: usize,
    pub checkins: usize,
    pub rejected_dps: u64,
    pub expected_steps: f64,
    pub expected_dps: f64,
    /// `steps / expected_steps` — passes 1.0 around the median solve.
    pub fraction: f64,
    pub solution: Option<String>,
}

/// Outcome of merging one check-in.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ApplyOutcome {
    /// `false` when the `(peer, seq)` was already in the log.
    pub new: bool,
    pub accepted_dps: usize,
    pub rejected_dps: usize,
    /// Set when this check-in produced (or carried) the solution.
    pub solved_now: bool,
}

/// Per-peer replicated state.
#[derive(Clone, Debug)]
pub struct SharedState {
    job_id: String,
    pub dp_table: HashMap<String, DpEntry>,
    claims: BTreeMap<u64, HashMap<String, Claim>>,
    log: BTreeMap<(String, u64), CheckIn>,
    next_seq: HashMap<String, u64>,
    pub solution: Option<BigUint>,
    pub rejected_dps: u64,
    pub rejected_checkins: u64,
    pub sterile_collisions: u64,
}

impl SharedState {
    pub fn new(ctx: &JobContext) -> Self {
        Self {
            job_id: ctx.job_id.clone(),
            dp_table: HashMap::new(),
            claims: BTreeMap::new(),
            log: BTreeMap::new(),
            next_seq: HashMap::new(),
            solution: None,
            rejected_dps: 0,
            rejected_checkins: 0,
            sterile_collisions: 0,
        }
    }

    pub fn job_id(&self) -> &str {
        &self.job_id
    }

    /// Next sequence number for a lane this node emits as.  Always
    /// above anything already in the log for that lane, so a node
    /// that restarts from a synced log never reuses a number.
    pub fn next_seq(&mut self, peer: &str) -> u64 {
        let logged = self
            .log
            .range((peer.to_string(), 0)..=(peer.to_string(), u64::MAX))
            .next_back()
            .map(|((_, s), _)| *s)
            .unwrap_or(0);
        let e = self.next_seq.entry(peer.to_string()).or_insert(0);
        *e = (*e).max(logged) + 1;
        *e
    }

    /// Merge one check-in.  `now` is the receiver's clock; `verify`
    /// re-derives every DP (recommended whenever the origin is not
    /// this process).
    pub fn apply(
        &mut self,
        ctx: &JobContext,
        ci: &CheckIn,
        now: u64,
        verify: bool,
    ) -> Result<ApplyOutcome, String> {
        if ci.version != PROTOCOL_VERSION {
            self.rejected_checkins += 1;
            return Err(format!("check-in version {} unsupported", ci.version));
        }
        if ci.job_id != self.job_id {
            self.rejected_checkins += 1;
            return Err("check-in belongs to a different job".into());
        }
        let key = (ci.peer.clone(), ci.seq);
        if self.log.contains_key(&key) {
            return Ok(ApplyOutcome::default());
        }
        let mut out = ApplyOutcome {
            new: true,
            ..Default::default()
        };

        for rec in &ci.dps {
            let pt = if verify {
                match rec.verify(ctx) {
                    Ok(p) => p,
                    Err(_) => {
                        out.rejected_dps += 1;
                        self.rejected_dps += 1;
                        continue;
                    }
                }
            } else {
                match rec.point(ctx) {
                    Ok(p) => p,
                    Err(_) => {
                        out.rejected_dps += 1;
                        self.rejected_dps += 1;
                        continue;
                    }
                }
            };
            let (a, b) = match rec.coefficients() {
                Ok(v) => v,
                Err(_) => {
                    out.rejected_dps += 1;
                    self.rejected_dps += 1;
                    continue;
                }
            };
            let y = match &pt {
                Point::Affine { y, .. } => y.value.clone(),
                Point::Infinity => BigUint::zero(),
            };
            let k = ctx.dp_key(&pt);
            out.accepted_dps += 1;
            match self.dp_table.get(&k) {
                None => {
                    self.dp_table.insert(
                        k,
                        DpEntry {
                            a,
                            b,
                            y,
                            walker: rec.walker,
                            peer: ci.peer.clone(),
                        },
                    );
                }
                Some(prev) => {
                    if prev.a == a && prev.b == b {
                        continue; // same trail re-reported
                    }
                    if self.solution.is_none() {
                        match solve_collision(ctx, (&prev.a, &prev.b, &prev.y), (&a, &b, &y)) {
                            Some(x) => {
                                self.solution = Some(x);
                                out.solved_now = true;
                            }
                            None => self.sterile_collisions += 1,
                        }
                    }
                    // Keep the table order-independent: the entry
                    // under a key is the coefficient-wise minimum of
                    // everything ever reported for it.
                    if (&a, &b) < (&prev.a, &prev.b) {
                        self.dp_table.insert(
                            k,
                            DpEntry {
                                a,
                                b,
                                y,
                                walker: rec.walker,
                                peer: ci.peer.clone(),
                            },
                        );
                    }
                }
            }
        }

        for rep in &ci.units {
            let slot = self.claims.entry(rep.unit).or_default();
            let replace = slot.get(&ci.peer).is_none_or(|c| c.seq < ci.seq);
            if replace {
                slot.insert(
                    ci.peer.clone(),
                    Claim {
                        seq: ci.seq,
                        received_at: now,
                        report: rep.clone(),
                    },
                );
            }
        }

        if let Some(hex) = &ci.solution {
            if self.solution.is_none() {
                if let Ok(x) = parse_hex(hex) {
                    if x < ctx.n && ctx.g.scalar_mul(&x, &ctx.a) == ctx.q {
                        self.solution = Some(x);
                        out.solved_now = true;
                    }
                }
            }
        }

        self.log.insert(key, ci.clone());
        Ok(out)
    }

    /// `{peer ↦ highest seq in log}` — what to send in a pull.
    pub fn version_vector(&self) -> BTreeMap<String, u64> {
        let mut vv = BTreeMap::new();
        for (peer, seq) in self.log.keys() {
            let e = vv.entry(peer.clone()).or_insert(0);
            *e = (*e).max(*seq);
        }
        vv
    }

    /// Check-ins the holder of `known` has not seen, oldest first.
    pub fn delta_for(&self, known: &BTreeMap<String, u64>) -> Vec<CheckIn> {
        self.log
            .iter()
            .filter(|((peer, seq), _)| *seq > known.get(peer).copied().unwrap_or(0))
            .map(|(_, ci)| ci.clone())
            .collect()
    }

    pub fn log_len(&self) -> usize {
        self.log.len()
    }

    pub fn checkin(&self, peer: &str, seq: u64) -> Option<&CheckIn> {
        self.log.get(&(peer.to_string(), seq))
    }

    fn claim_live(c: &Claim, now: u64, lease_secs: u64) -> bool {
        !c.report.completed && now < c.received_at.saturating_add(lease_secs)
    }

    /// Merged view of unit `u`.
    pub fn unit_view(&self, u: u64, now: u64, lease_secs: u64) -> UnitView {
        let mut v = UnitView {
            unit: u,
            completed: false,
            walkers_done: 0,
            steps: 0,
            dps: 0,
            dead_trails: 0,
            owner: None,
        };
        if let Some(slot) = self.claims.get(&u) {
            let mut best: Option<(&String, &Claim)> = None;
            for (peer, c) in slot {
                v.completed |= c.report.completed;
                if c.report.walkers_done > v.walkers_done
                    || (c.report.walkers_done == v.walkers_done && v.steps == 0)
                {
                    v.walkers_done = c.report.walkers_done;
                    v.steps = c.report.steps;
                    v.dps = c.report.dps;
                    v.dead_trails = c.report.dead_trails;
                }
                if Self::claim_live(c, now, lease_secs) {
                    // Deterministic tie-break: most recent, then lowest id.
                    let better = match best {
                        None => true,
                        Some((bp, bc)) => {
                            (c.received_at, std::cmp::Reverse(peer))
                                > (bc.received_at, std::cmp::Reverse(bp))
                        }
                    };
                    if better {
                        best = Some((peer, c));
                    }
                }
            }
            v.owner = if v.completed {
                None
            } else {
                best.map(|(p, _)| p.clone())
            };
        }
        v
    }

    /// All units anyone has reported on.
    pub fn units(&self, now: u64, lease_secs: u64) -> Vec<UnitView> {
        self.claims
            .keys()
            .map(|&u| self.unit_view(u, now, lease_secs))
            .collect()
    }

    /// Pick the unit lane `me` should work next and the walker offset
    /// to resume from.
    ///
    /// 1. A unit `me` already holds a live lease on is continued.
    /// 2. Otherwise the lowest-numbered units that are neither
    ///    completed nor live-leased by someone else are candidates;
    ///    the first `window` of them are spread across lanes by
    ///    hashing the lane id, so lanes whose views lag each other
    ///    rarely pick the same unit.  Duplicated work is only a
    ///    performance loss — trails are deterministic, so it can
    ///    never corrupt the table.
    /// 3. A unit abandoned by an expired lease resumes from the
    ///    highest cursor anyone reported for it.
    ///
    /// `max_units == 0` means unbounded.
    pub fn next_unit(
        &self,
        me: &str,
        now: u64,
        lease_secs: u64,
        window: usize,
        max_units: u64,
    ) -> Option<(u64, u64)> {
        for (u, slot) in &self.claims {
            if let Some(c) = slot.get(me) {
                if Self::claim_live(c, now, lease_secs) {
                    let v = self.unit_view(*u, now, lease_secs);
                    if !v.completed {
                        return Some((*u, v.walkers_done));
                    }
                }
            }
        }
        let window = window.max(1);
        let mut cands: Vec<(u64, u64)> = Vec::with_capacity(window);
        let mut u = 0u64;
        while cands.len() < window {
            if max_units > 0 && u >= max_units {
                break;
            }
            let v = self.unit_view(u, now, lease_secs);
            if !v.completed && v.owner.is_none() {
                cands.push((u, v.walkers_done));
            }
            u = u.checked_add(1)?;
        }
        if cands.is_empty() {
            return None;
        }
        let h = crate::hash::sha256(me.as_bytes());
        let pick = (u64::from_le_bytes(h[..8].try_into().unwrap()) as usize) % cands.len();
        Some(cands[pick])
    }

    pub fn progress(&self, ctx: &JobContext, now: u64, lease_secs: u64) -> Progress {
        let mut steps = 0u64;
        let mut dead = 0u64;
        let mut done = 0u64;
        let mut active = 0u64;
        for v in self.units(now, lease_secs) {
            steps += v.steps;
            dead += v.dead_trails;
            if v.completed {
                done += 1;
            } else if v.owner.is_some() {
                active += 1;
            }
        }
        let expected_steps = ctx.expected_steps();
        Progress {
            steps,
            dps_stored: self.dp_table.len(),
            dead_trails: dead,
            units_completed: done,
            units_active: active,
            peers: self.version_vector().len(),
            checkins: self.log.len(),
            rejected_dps: self.rejected_dps,
            expected_steps,
            expected_dps: ctx.expected_dps(),
            fraction: if expected_steps > 0.0 {
                steps as f64 / expected_steps
            } else {
                0.0
            },
            solution: self.solution.as_ref().map(hex_of),
        }
    }
}

fn sub_mod(a: &BigUint, b: &BigUint, n: &BigUint) -> BigUint {
    let a = a % n;
    let b = b % n;
    if a >= b {
        a - b
    } else {
        n - (b - a)
    }
}

/// Solve `x` from two DP entries sharing a key.  Same point:
/// `(a₁ − a₂)·P = (b₂ − b₁)·Q`.  Opposite points (negation map, same
/// `x`, different `y`): `(a₁ + a₂)·P = −(b₁ + b₂)·Q`.  The candidate is
/// verified against `Q` before it is returned.
pub fn solve_collision(
    ctx: &JobContext,
    e1: (&BigUint, &BigUint, &BigUint),
    e2: (&BigUint, &BigUint, &BigUint),
) -> Option<BigUint> {
    let n = &ctx.n;
    let (num, den) = if e1.2 == e2.2 {
        (sub_mod(e1.0, e2.0, n), sub_mod(e2.1, e1.1, n))
    } else {
        let s_a = (e1.0 + e2.0) % n;
        let s_b = (e1.1 + e2.1) % n;
        (sub_mod(&BigUint::zero(), &s_a, n), s_b)
    };
    if den.is_zero() {
        return None;
    }
    let inv = mod_inverse(&den, n)?;
    let x = (num * inv) % n;
    if ctx.g.scalar_mul(&x, &ctx.a) == ctx.q {
        Some(x)
    } else {
        None
    }
}

/// Seconds since the Unix epoch (receiver clock for leases).
pub fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::super::job::{demo_curve, JobSpec};
    use super::super::walk::{run_walker, WalkerOutcome};
    use super::*;

    fn ctx(negation: bool, secret: u32) -> JobContext {
        let curve = demo_curve("demo-mid").unwrap();
        let q = curve
            .generator()
            .scalar_mul(&BigUint::from(secret), &curve.a_fe());
        let mut spec = JobSpec::new(&curve, &q, "state", 3).unwrap();
        spec.dp_bits = 3;
        spec.unit_size = 16;
        spec.negation_map = negation;
        spec.build().unwrap()
    }

    fn checkin(ctx: &JobContext, peer: &str, seq: u64, walkers: std::ops::Range<u64>) -> CheckIn {
        let mut dps = Vec::new();
        let mut dead = 0;
        let mut steps = 0;
        for i in walkers.clone() {
            match run_walker(ctx, i) {
                WalkerOutcome::Dp(r) => {
                    steps += r.steps;
                    dps.push(r);
                }
                WalkerOutcome::DeadTrail { steps: s } => {
                    steps += s;
                    dead += 1;
                }
            }
        }
        let unit = walkers.start / ctx.spec.unit_size;
        CheckIn {
            version: PROTOCOL_VERSION,
            job_id: ctx.job_id.clone(),
            peer: peer.into(),
            seq,
            time: 0,
            units: vec![UnitReport {
                unit,
                walkers_done: walkers.end - unit * ctx.spec.unit_size,
                steps,
                dps: dps.len() as u64,
                dead_trails: dead,
                completed: walkers.end.is_multiple_of(ctx.spec.unit_size),
            }],
            dps,
            solution: None,
        }
    }

    #[test]
    fn merging_checkins_solves_the_instance() {
        for negation in [false, true] {
            let c = ctx(negation, 31_337);
            let mut st = SharedState::new(&c);
            let mut unit = 0u64;
            while st.solution.is_none() {
                let ci = checkin(&c, "a", unit + 1, unit * 16..(unit + 1) * 16);
                st.apply(&c, &ci, 100, true).unwrap();
                unit += 1;
                assert!(
                    unit < 200,
                    "negation={negation}: no collision after 3200 walkers"
                );
            }
            assert_eq!(st.solution.unwrap(), BigUint::from(31_337u32));
            assert_eq!(st.rejected_dps, 0);
        }
    }

    #[test]
    fn merge_is_order_independent_and_idempotent() {
        let c = ctx(false, 555);
        let cis: Vec<CheckIn> = (0..6u64)
            .map(|u| {
                checkin(
                    &c,
                    if u % 2 == 0 { "a" } else { "b" },
                    u / 2 + 1,
                    u * 16..(u + 1) * 16,
                )
            })
            .collect();
        let mut s1 = SharedState::new(&c);
        let mut s2 = SharedState::new(&c);
        for ci in &cis {
            s1.apply(&c, ci, 10, true).unwrap();
        }
        for ci in cis.iter().rev() {
            s2.apply(&c, ci, 10, true).unwrap();
            // Second delivery is a no-op.
            let dup = s2.apply(&c, ci, 10, true).unwrap();
            assert!(!dup.new);
        }
        assert_eq!(s1.dp_table.len(), s2.dp_table.len());
        for (k, e) in &s1.dp_table {
            let f = &s2.dp_table[k];
            assert_eq!((&e.a, &e.b), (&f.a, &f.b), "dp {k}");
        }
        assert_eq!(s1.units(10, 60), s2.units(10, 60));
        assert_eq!(s1.version_vector(), s2.version_vector());
        assert_eq!(s1.solution, s2.solution);
    }

    #[test]
    fn rejects_foreign_job_and_bad_dps() {
        let c = ctx(false, 5);
        let other = ctx(false, 6);
        let mut st = SharedState::new(&c);
        let foreign = checkin(&other, "z", 1, 0..16);
        assert!(st.apply(&c, &foreign, 0, true).is_err());
        assert_eq!(st.rejected_checkins, 1);
        let mut forged = checkin(&c, "z", 1, 0..16);
        assert!(!forged.dps.is_empty());
        forged.dps[0].b = "0".into();
        let out = st.apply(&c, &forged, 0, true).unwrap();
        assert_eq!(out.rejected_dps, 1);
        assert_eq!(out.accepted_dps, forged.dps.len() - 1);
        // A bogus solution claim is ignored; a real one is accepted.
        let mut st = SharedState::new(&c);
        let mut claim = checkin(&c, "z", 2, 16..32);
        claim.dps.clear();
        claim.solution = Some("7".into());
        assert!(!st.apply(&c, &claim, 0, true).unwrap().solved_now);
        assert!(st.solution.is_none());
        let mut claim = checkin(&c, "z", 3, 32..48);
        claim.dps.clear();
        claim.solution = Some("5".into());
        assert!(st.apply(&c, &claim, 0, true).unwrap().solved_now);
        assert_eq!(st.solution, Some(BigUint::from(5u32)));
    }

    #[test]
    fn leases_expire_and_units_resume_from_cursor() {
        let c = ctx(false, 9);
        let mut st = SharedState::new(&c);
        // Lane a claims unit 0 with 8/16 walkers done at t=100.
        let ci = checkin(&c, "a", 1, 0..8);
        st.apply(&c, &ci, 100, true).unwrap();
        // While the lease is live, lane b is steered elsewhere…
        assert_eq!(st.next_unit("b", 110, 60, 1, 0), Some((1, 0)));
        // …and lane a continues its own unit.
        assert_eq!(st.next_unit("a", 110, 60, 1, 0), Some((0, 8)));
        // After expiry, b takes over unit 0 from walker 8.
        assert_eq!(st.next_unit("b", 200, 60, 1, 0), Some((0, 8)));
        let v = st.unit_view(0, 200, 60);
        assert_eq!(v.owner, None);
        assert_eq!(v.walkers_done, 8);
        // Completing it removes it from circulation.
        let done = checkin(&c, "b", 1, 8..16);
        st.apply(&c, &done, 200, true).unwrap();
        assert!(st.unit_view(0, 200, 60).completed);
        assert_eq!(st.next_unit("b", 201, 60, 1, 0), Some((1, 0)));
        // Bounded jobs run out.
        assert_eq!(st.next_unit("b", 201, 60, 1, 1), None);
        let p = st.progress(&c, 201, 60);
        assert_eq!(p.units_completed, 1);
        assert!(p.steps > 0);
    }

    #[test]
    fn seq_never_reused_after_reload() {
        let c = ctx(false, 9);
        let mut st = SharedState::new(&c);
        st.apply(&c, &checkin(&c, "a", 4, 0..16), 0, true).unwrap();
        assert_eq!(st.next_seq("a"), 5);
        assert_eq!(st.next_seq("a"), 6);
        assert_eq!(st.next_seq("b"), 1);
        let known = BTreeMap::from([("a".to_string(), 3u64)]);
        assert_eq!(st.delta_for(&known).len(), 1);
        let known = BTreeMap::from([("a".to_string(), 4u64)]);
        assert!(st.delta_for(&known).is_empty());
    }
}
