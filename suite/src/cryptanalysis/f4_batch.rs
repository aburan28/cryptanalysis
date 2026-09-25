//! # Lockstep splitting search: many Boolean systems, batched Macaulay decisions.
//!
//! [`super::koblitz_groebner::solve_boolean_system_filtered`] reduces one
//! Macaulay matrix at a time, and each one is small — a few hundred rows —
//! so a device that wants thousands of independent matrices per launch
//! gets nothing from it.  Relation collection has that parallelism, one
//! level up: every trial target is its own search.  This module runs a
//! batch of searches **in lockstep**.  Each search is the recursive solver
//! turned into an explicit state machine; every round advances all of them
//! to their next reduction and hands the pending matrices to a
//! [`BatchDecider`] in a single call.
//!
//! Each search takes exactly the steps the recursive solver takes — the
//! same reductions, degrees, propagations, splits, budget checks and
//! early stop — so, given a decider that answers like
//! [`f4_gf2::decide`], its solutions and [`SolveStats`] are the
//! sequential solver's.  `lockstep_matches_the_recursive_solver` holds it
//! to that.
//!
//! Backends: [`CpuDecider`] is the host kernel, requests in parallel; the
//! GPU and its host emulator are in [`super::f4_gpu`].

use rayon::prelude::*;

use super::f4_gf2::{self, Decision, KernelCounters, MacaulayCaps};
use super::koblitz_groebner::{
    choose_split, f4_caps, f4_kernel, f4_profile_add_kernel, is_constant_one,
    solve_boolean_system_filtered, substitute, system_degree, F4Kernel, SolveOptions, SolveStats,
    SolverEngine,
};
use super::pq_groebner_f2::F2BoolPoly;

/// One Macaulay decision: the system, its variable count and the degree.
#[derive(Clone, Copy, Debug)]
pub struct DecisionRequest<'a> {
    /// The equations.
    pub polys: &'a [F2BoolPoly],
    /// Variables of the ring.
    pub n_vars: usize,
    /// Macaulay degree.
    pub degree: u32,
}

/// Answers batches of [`DecisionRequest`]s as [`f4_gf2::decide`] would.
pub trait BatchDecider: Send {
    /// A short label for reports.
    fn name(&self) -> String;
    /// Decide every request; one `(decision, counters)` per request, in
    /// order, with `None` for a matrix over `caps`.
    fn decide(
        &mut self,
        requests: &[DecisionRequest<'_>],
        caps: MacaulayCaps,
    ) -> Vec<(Option<Decision>, KernelCounters)>;
}

/// The host kernel, [`f4_gf2::decide`], over the requests in parallel.
#[derive(Clone, Copy, Debug, Default)]
pub struct CpuDecider;

impl BatchDecider for CpuDecider {
    fn name(&self) -> String {
        "cpu".into()
    }

    fn decide(
        &mut self,
        requests: &[DecisionRequest<'_>],
        caps: MacaulayCaps,
    ) -> Vec<(Option<Decision>, KernelCounters)> {
        requests
            .par_iter()
            .map(|r| f4_gf2::decide(r.polys, r.n_vars, r.degree, caps))
            .collect()
    }
}

/// The result of one search.
#[derive(Clone, Debug, Default)]
pub struct LockstepOutcome {
    /// Verified roots, in the order found.
    pub solutions: Vec<u64>,
    /// The solver's counters.
    pub stats: SolveStats,
    /// The root `accept` returned `true` for, which stopped the search.
    pub accepted: Option<u64>,
}

/// Measurements of one lockstep run.
#[derive(Clone, Debug, Default)]
pub struct LockstepReport {
    /// Rounds, i.e. calls to the decider.
    pub rounds: usize,
    /// Decision requests over all rounds.
    pub requests: usize,
    /// Largest round.
    pub max_round: usize,
    /// Nanoseconds inside the decider.
    pub decide_ns: u128,
    /// Nanoseconds advancing the searches between rounds.
    pub advance_ns: u128,
}

/// One activation of the recursive solver, as data.
enum Frame {
    /// Entry: stop, solution-count and budget checks.
    Entry {
        system: Vec<F2BoolPoly>,
        assignment: Vec<Option<bool>>,
    },
    /// Top of the reduce-and-propagate loop.
    Loop {
        system: Vec<F2BoolPoly>,
        assignment: Vec<Option<bool>>,
    },
    /// Waiting for the decision at `degree`.
    Reducing {
        system: Vec<F2BoolPoly>,
        assignment: Vec<Option<bool>>,
        degree: u32,
        top: u32,
        best: Option<Decision>,
    },
    /// The algebra stalled: split, or verify a full assignment.
    Split {
        system: Vec<F2BoolPoly>,
        assignment: Vec<Option<bool>>,
    },
    /// Branching on `free`; `next` children have been started.
    Branch {
        system: Vec<F2BoolPoly>,
        assignment: Vec<Option<bool>>,
        free: usize,
        next: u8,
    },
}

/// One search.
struct Search<'o> {
    original: &'o [F2BoolPoly],
    n_vars: usize,
    stack: Vec<Frame>,
    out: LockstepOutcome,
    stop: bool,
}

impl<'o> Search<'o> {
    fn new(equations: &'o [F2BoolPoly], n_vars: usize) -> Self {
        Search {
            original: equations,
            n_vars,
            stack: vec![Frame::Entry {
                system: equations.to_vec(),
                assignment: vec![None; n_vars],
            }],
            out: LockstepOutcome::default(),
            stop: false,
        }
    }

    /// The pending request, if the search is waiting on one.
    fn request(&self) -> Option<DecisionRequest<'_>> {
        match self.stack.last() {
            Some(Frame::Reducing { system, degree, .. }) => Some(DecisionRequest {
                polys: system,
                n_vars: self.n_vars,
                degree: *degree,
            }),
            _ => None,
        }
    }

    /// Run until the search waits on a decision or finishes.  Returns
    /// whether a request is pending.
    fn advance(
        &mut self,
        opts: &SolveOptions,
        max_degree: u32,
        accept: &dyn Fn(u64) -> bool,
    ) -> bool {
        loop {
            if matches!(self.stack.last(), Some(Frame::Reducing { .. })) {
                return true;
            }
            let Some(frame) = self.stack.pop() else {
                return false;
            };
            match frame {
                Frame::Entry { system, assignment } => {
                    if self.stop || self.out.solutions.len() >= opts.max_solutions {
                        continue;
                    }
                    if self.out.stats.reductions >= opts.node_budget {
                        self.out.stats.exhausted = true;
                        continue;
                    }
                    self.stack.push(Frame::Loop { system, assignment });
                }
                Frame::Loop {
                    mut system,
                    assignment,
                } => {
                    system.retain(|p| !p.is_zero());
                    if system.iter().any(is_constant_one) {
                        self.out.stats.infeasible_branches += 1;
                        continue;
                    }
                    self.out.stats.reductions += 1;
                    let base = system_degree(&system).max(2);
                    self.stack.push(Frame::Reducing {
                        system,
                        assignment,
                        degree: base,
                        top: max_degree.max(base),
                        best: None,
                    });
                }
                Frame::Reducing { .. } => unreachable!("handled above"),
                Frame::Split { system, assignment } => {
                    match choose_split(&system, &assignment, opts.split_rule) {
                        None => {
                            let mut pt = 0u64;
                            for (i, a) in assignment.iter().enumerate() {
                                if *a == Some(true) {
                                    pt |= 1 << i;
                                }
                            }
                            if self.original.iter().all(|e| e.eval(pt) == 0) {
                                self.out.solutions.push(pt);
                                if accept(pt) {
                                    self.out.accepted = Some(pt);
                                    self.stop = true;
                                }
                            }
                        }
                        Some(free) => {
                            self.out.stats.splits += 1;
                            self.stack.push(Frame::Branch {
                                system,
                                assignment,
                                free,
                                next: 0,
                            });
                        }
                    }
                }
                Frame::Branch {
                    system,
                    assignment,
                    free,
                    next,
                } => {
                    if next > 0 && (self.stop || self.out.solutions.len() >= opts.max_solutions) {
                        continue;
                    }
                    if next == 2 {
                        continue;
                    }
                    let value = next == 1;
                    let mut branch = assignment.clone();
                    branch[free] = Some(value);
                    let specialised: Vec<F2BoolPoly> = system
                        .iter()
                        .map(|p| substitute(p, free as u32, value))
                        .collect();
                    self.stack.push(Frame::Branch {
                        system,
                        assignment,
                        free,
                        next: next + 1,
                    });
                    self.stack.push(Frame::Entry {
                        system: specialised,
                        assignment: branch,
                    });
                }
            }
        }
    }

    /// Consume the decision for the pending request.
    fn deliver(
        &mut self,
        opts: &SolveOptions,
        decision: Option<Decision>,
        counters: &KernelCounters,
    ) {
        f4_profile_add_kernel(counters);
        let Some(Frame::Reducing {
            mut system,
            mut assignment,
            degree,
            top,
            mut best,
        }) = self.stack.pop()
        else {
            unreachable!("a decision arrived with no request pending");
        };
        let stats = &mut self.out.stats;
        match decision {
            Some(d) => {
                stats.max_degree_built = stats.max_degree_built.max(degree);
                let decisive = d.is_decisive();
                best = Some(d);
                if !decisive && degree < top {
                    self.stack.push(Frame::Reducing {
                        system,
                        assignment,
                        degree: degree + 1,
                        top,
                        best,
                    });
                    return;
                }
            }
            None => stats.oversize += 1,
        }
        let Some(d) = best else {
            self.stack.push(Frame::Split { system, assignment });
            return;
        };
        if d.refuted {
            stats.infeasible_branches += 1;
            return;
        }
        if d.forced.is_empty() {
            self.stack.push(Frame::Split { system, assignment });
            return;
        }
        for (v, val) in d.forced {
            match assignment[v as usize] {
                Some(existing) if existing != val => {
                    stats.infeasible_branches += 1;
                    return;
                }
                Some(_) => {}
                None => {
                    stats.propagations += 1;
                    assignment[v as usize] = Some(val);
                    system = system.iter().map(|p| substitute(p, v, val)).collect();
                }
            }
        }
        if stats.reductions >= opts.node_budget {
            stats.exhausted = true;
            return;
        }
        self.stack.push(Frame::Loop { system, assignment });
    }
}

/// Whether [`solve_lockstep`] can run `opts` in lockstep: the matrix-F4
/// engine on the fast kernel, with the reduction cache off.  Anything else
/// is solved system by system with the recursive solver.
pub fn lockstep_supported(opts: &SolveOptions) -> bool {
    use super::algebra_cache::{self, Layer};
    matches!(opts.engine, SolverEngine::MatrixF4 { .. })
        && f4_kernel() == F4Kernel::Fast
        && !algebra_cache::enabled(Layer::ExactReduction)
}

/// **Solve many systems in lockstep.**  `systems[i]` is `(equations,
/// n_vars)`; `accept(i, root)` is called on each verified root of system
/// `i` and stops that search when it returns `true`, exactly as the
/// callback of [`solve_boolean_system_filtered`] does.
///
/// Per system, the result equals [`solve_boolean_system_filtered`]'s when
/// `decider` answers as [`f4_gf2::decide`] does.  When
/// [`lockstep_supported`] is false the systems are solved one by one (in
/// parallel) with the recursive solver instead, and `decider` is unused.
pub fn solve_lockstep(
    systems: &[(Vec<F2BoolPoly>, usize)],
    opts: &SolveOptions,
    decider: &mut dyn BatchDecider,
    accept: &(dyn Fn(usize, u64) -> bool + Sync),
) -> (Vec<LockstepOutcome>, LockstepReport) {
    let mut report = LockstepReport::default();
    if !lockstep_supported(opts) {
        let outcomes = systems
            .par_iter()
            .enumerate()
            .map(|(i, (eqs, n_vars))| {
                let mut accepted = None;
                let (solutions, stats) =
                    solve_boolean_system_filtered(eqs, *n_vars, opts, |root| {
                        let ok = accept(i, root);
                        if ok {
                            accepted = Some(root);
                        }
                        ok
                    });
                LockstepOutcome {
                    solutions,
                    stats,
                    accepted,
                }
            })
            .collect();
        return (outcomes, report);
    }
    let SolverEngine::MatrixF4 { max_degree } = opts.engine else {
        unreachable!("checked by lockstep_supported");
    };
    let caps = f4_caps();
    let mut searches: Vec<Search<'_>> = systems
        .iter()
        .map(|(eqs, n_vars)| Search::new(eqs, *n_vars))
        .collect();
    loop {
        let t0 = std::time::Instant::now();
        let pending: Vec<bool> = searches
            .par_iter_mut()
            .enumerate()
            .map(|(i, s)| s.advance(opts, max_degree, &|root| accept(i, root)))
            .collect();
        report.advance_ns += t0.elapsed().as_nanos();
        let waiting: Vec<usize> = (0..searches.len()).filter(|&i| pending[i]).collect();
        if waiting.is_empty() {
            break;
        }
        let requests: Vec<DecisionRequest<'_>> = waiting
            .iter()
            .map(|&i| searches[i].request().expect("pending"))
            .collect();
        let t1 = std::time::Instant::now();
        let answers = decider.decide(&requests, caps);
        report.decide_ns += t1.elapsed().as_nanos();
        assert_eq!(answers.len(), requests.len(), "decider dropped a request");
        drop(requests);
        report.rounds += 1;
        report.requests += waiting.len();
        report.max_round = report.max_round.max(waiting.len());
        let t2 = std::time::Instant::now();
        let mut slots: Vec<Option<(Option<Decision>, KernelCounters)>> =
            answers.into_iter().map(Some).collect();
        let mut by_search: Vec<Option<(Option<Decision>, KernelCounters)>> =
            (0..searches.len()).map(|_| None).collect();
        for (slot, &i) in slots.iter_mut().zip(&waiting) {
            by_search[i] = slot.take();
        }
        searches
            .par_iter_mut()
            .zip(by_search.into_par_iter())
            .for_each(|(s, answer)| {
                if let Some((decision, counters)) = answer {
                    s.deliver(opts, decision, &counters);
                }
            });
        report.advance_ns += t2.elapsed().as_nanos();
    }
    (searches.into_iter().map(|s| s.out).collect(), report)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_groebner::{build_decomposition_system, FieldStructure};
    use crate::cryptanalysis::koblitz_index_calculus::{build_frobenius_factor_base, KoblitzCurve};
    use rand::{rngs::StdRng, Rng, SeedableRng};

    fn assert_same(a: &SolveStats, b: &SolveStats, what: &str) {
        assert_eq!(a.reductions, b.reductions, "{what}: reductions");
        assert_eq!(
            a.infeasible_branches, b.infeasible_branches,
            "{what}: infeasible branches"
        );
        assert_eq!(a.propagations, b.propagations, "{what}: propagations");
        assert_eq!(a.splits, b.splits, "{what}: splits");
        assert_eq!(a.exhausted, b.exhausted, "{what}: exhausted");
        assert_eq!(a.max_degree_built, b.max_degree_built, "{what}: degree");
        assert_eq!(a.oversize, b.oversize, "{what}: oversize");
    }

    /// Decomposition systems of random targets, with a budget small enough
    /// that some searches exhaust it and an `accept` that stops some early.
    fn fixtures() -> Vec<(Vec<F2BoolPoly>, usize)> {
        let mut out = Vec::new();
        for (a, n, m) in [(0u8, 9u32, 2usize), (0, 9, 3), (1, 11, 2), (0, 13, 2)] {
            let Some(kc) = KoblitzCurve::new(a, n) else {
                continue;
            };
            let Some(fb) = build_frobenius_factor_base(&kc, 0) else {
                continue;
            };
            let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
            let mut rng = StdRng::seed_from_u64(u64::from(n) * 7 + m as u64);
            for _ in 0..6 {
                let raw = 1 + rng.gen::<u64>() % ((1u64 << n) - 1);
                let x_r =
                    crate::binary_ecc::F2mElement::from_biguint(&num_bigint::BigUint::from(raw), n);
                if let Some(sys) =
                    build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, m, &st)
                {
                    out.push((sys.equations, sys.n_vars));
                }
            }
        }
        out
    }

    #[test]
    fn lockstep_matches_the_recursive_solver() {
        let systems = fixtures();
        assert!(systems.len() >= 12, "{} fixtures", systems.len());
        for (budget, max_solutions) in [(4096usize, usize::MAX), (7, usize::MAX), (4096, 2)] {
            let opts = SolveOptions {
                engine: SolverEngine::MatrixF4 { max_degree: 3 },
                max_solutions,
                node_budget: budget,
                ..SolveOptions::default()
            };
            // Stop system i at its first root whose low bits are i mod 3.
            let accept = |i: usize, root: u64| root % 3 == (i % 3) as u64;
            let (got, report) = solve_lockstep(&systems, &opts, &mut CpuDecider, &accept);
            assert_eq!(got.len(), systems.len());
            assert!(report.rounds > 0);
            for (i, ((eqs, n_vars), outcome)) in systems.iter().zip(&got).enumerate() {
                let mut accepted = None;
                let (sols, stats) = solve_boolean_system_filtered(eqs, *n_vars, &opts, |root| {
                    let ok = accept(i, root);
                    if ok {
                        accepted = Some(root);
                    }
                    ok
                });
                let what = format!("system {i}, budget {budget}, max {max_solutions}");
                assert_eq!(outcome.solutions, sols, "{what}: solutions");
                assert_eq!(outcome.accepted, accepted, "{what}: accepted root");
                assert_same(&outcome.stats, &stats, &what);
            }
        }
    }

    #[test]
    fn unsupported_engines_fall_back_to_the_recursive_solver() {
        let systems: Vec<_> = fixtures().into_iter().take(2).collect();
        let opts = SolveOptions {
            engine: SolverEngine::Buchberger,
            max_solutions: usize::MAX,
            node_budget: 16,
            ..SolveOptions::default()
        };
        assert!(!lockstep_supported(&opts));
        let (got, report) = solve_lockstep(&systems, &opts, &mut CpuDecider, &|_, _| false);
        assert_eq!(report.rounds, 0);
        for ((eqs, n_vars), outcome) in systems.iter().zip(&got) {
            let (sols, stats) = solve_boolean_system_filtered(eqs, *n_vars, &opts, |_| false);
            assert_eq!(outcome.solutions, sols);
            assert_same(&outcome.stats, &stats, "buchberger");
        }
    }
}
