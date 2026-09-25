//! # Pricing the decomposition oracles: what one target costs each solver.
//!
//! The boundary ledger (`ic_boundary`) runs whole discrete logarithms
//! with the oracles that can finish one — enumeration, meet in the
//! middle, `S₄` pairs-and-solve.  The algebraic oracles cannot, at any
//! size worth the name: matrix-F4 and CDCL SAT on the Weil-descended
//! Semaev system decide a target in seconds to minutes where the others
//! take microseconds.  They are still the only route that does not
//! enumerate the factor base, so their cost per target is the number
//! the whole field's literature argues about, and it belongs on the
//! same ledger in the same unit.
//!
//! This module prices every oracle on the same targets of the same
//! Koblitz instances, natively and converted:
//!
//! | oracle | native unit | what is counted |
//! |:--|:--|:--|
//! | `enumerate` | group additions | `R − P_i`, then `R − P_i − P_j` (`m = 3`), early exit |
//! | `mitm` | probes and additions | one probe (`m = 2`); `|F|` subtractions and probes (`m = 3`) |
//! | `semaev_s4` | pairs | the pairs-and-solve loop over the invariant subspace |
//! | `matrix_f4` | 64-bit word XORs | every Macaulay elimination of the splitting solve, exact, from [`f4_word_ops_total`] |
//! | `sat` | conflicts | CDCL with native parity rows and the degree-2 Macaulay consequences |
//!
//! and records, per system, the Boolean unknown and equation counts,
//! the system degree, the Macaulay rank profile and the **first fall
//! degree** over the target draws — the quantities the boundary ledger's
//! `decomposition` stage asks for.
//!
//! Every conclusive verdict is cross-checked: an oracle that finds a
//! decomposition another refutes is a bug, and a run with a
//! disagreement is not a measurement.  Inconclusive verdicts (budget
//! spent) are reported as such and never counted as refutations.
//!
//! The last column is an extrapolation and says so: with the measured
//! hit rate and the `K + 1` relations the instance needs, the relation
//! phase would cost `(K+1)/rate` targets at the oracle's mean price —
//! which, in the unit, is what the oracle would have to beat rho by.

use std::collections::BTreeMap;
use std::time::Instant;

use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde::Serialize;

use crate::cryptanalysis::ic_boundary::lift_abscissae;

use crate::cryptanalysis::ic_boundary::{
    calibrate_binary_instance, calibrate_s4, census_hits, choose_koblitz_base, decompose_mitm,
    generic_floor_ops, generic_floor_s, koblitz_factor_base, koblitz_instance_best, BinaryGroup,
    BinaryInstance, Calibration, ColumnFold, CountedGroup, FactorBase, GroupOps, Oracle,
    OracleCounters, PairTable,
};
use crate::cryptanalysis::koblitz_fast::FastPoint;
use crate::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, f4_profile, f4_word_ops_total, first_fall_degree, FieldStructure,
    SolverEngine,
};
use crate::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, groebner_decompose, sat_decompose_with, FrobeniusFactorBase,
    SatDecompositionOptions,
};
use crate::cryptanalysis::semaev_decomp::SubspaceOracle;

/// How one oracle fared on one target.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum Verdict {
    Found,
    Refuted,
    Inconclusive,
}

/// One oracle on one target.
#[derive(Clone, Debug, Serialize)]
pub struct TargetPrice {
    pub verdict: Verdict,
    pub native: u64,
    pub group_adds: u64,
    pub wall_ns: u64,
    pub gae: f64,
    /// Engine detail: F4 reductions/splits, SAT solver calls/models.
    pub extra: BTreeMap<String, u64>,
}

fn median(mut xs: Vec<f64>) -> f64 {
    if xs.is_empty() {
        return f64::NAN;
    }
    xs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mid = xs.len() / 2;
    if xs.len().is_multiple_of(2) {
        (xs[mid - 1] + xs[mid]) / 2.0
    } else {
        xs[mid]
    }
}

/// One oracle over every target of a cell.
#[derive(Clone, Debug, Serialize)]
pub struct OraclePrice {
    pub oracle: String,
    pub native_unit: String,
    pub found: usize,
    pub refuted: usize,
    pub inconclusive: usize,
    pub native_total: u64,
    pub native_median_found: f64,
    pub native_median_refuted: f64,
    pub ms_median_found: f64,
    pub ms_median_refuted: f64,
    pub ms_total: f64,
    /// Mean group-addition equivalents per target, over every target.
    pub gae_per_target_mean: f64,
    /// Mean over the refuted targets only — the cost that dominates a
    /// relation phase, where most targets do not decompose.
    pub gae_per_refutation_mean: f64,
    pub extra_totals: BTreeMap<String, u64>,
    pub per_target: Vec<TargetPrice>,
}

impl OraclePrice {
    fn from_targets(oracle: &str, unit: &str, per_target: Vec<TargetPrice>) -> Self {
        let class = |v: Verdict| per_target.iter().filter(move |t| t.verdict == v);
        let mut extra_totals: BTreeMap<String, u64> = BTreeMap::new();
        for t in &per_target {
            for (k, v) in &t.extra {
                *extra_totals.entry(k.clone()).or_insert(0) += v;
            }
        }
        let refuted: Vec<&TargetPrice> = class(Verdict::Refuted).collect();
        Self {
            oracle: oracle.into(),
            native_unit: unit.into(),
            found: class(Verdict::Found).count(),
            refuted: refuted.len(),
            inconclusive: class(Verdict::Inconclusive).count(),
            native_total: per_target.iter().map(|t| t.native).sum(),
            native_median_found: median(class(Verdict::Found).map(|t| t.native as f64).collect()),
            native_median_refuted: median(refuted.iter().map(|t| t.native as f64).collect()),
            ms_median_found: median(
                class(Verdict::Found)
                    .map(|t| t.wall_ns as f64 / 1e6)
                    .collect(),
            ),
            ms_median_refuted: median(refuted.iter().map(|t| t.wall_ns as f64 / 1e6).collect()),
            ms_total: per_target.iter().map(|t| t.wall_ns as f64 / 1e6).sum(),
            gae_per_target_mean: per_target.iter().map(|t| t.gae).sum::<f64>()
                / per_target.len().max(1) as f64,
            gae_per_refutation_mean: refuted.iter().map(|t| t.gae).sum::<f64>()
                / refuted.len().max(1) as f64,
            extra_totals,
            per_target,
        }
    }
}

/// The relation phase an oracle would give, extrapolated from its
/// measured price and the measured hit rate.
#[derive(Clone, Debug, Serialize)]
pub struct ProjectedRelationPhase {
    pub oracle: String,
    pub targets_needed: f64,
    pub relation_phase_gae: f64,
    pub s_projected: f64,
    pub s_over_rho_floor: f64,
    pub extrapolation: bool,
}

/// One instance of the Semaev system, priced by every oracle.
#[derive(Clone, Debug, Serialize)]
pub struct OracleCell {
    pub curve: serde_json::Value,
    pub n: u32,
    pub a: u64,
    pub r: u64,
    pub log2_r: f64,
    pub group_order: u64,
    pub factor_base: String,
    pub dimension: u32,
    pub signed_points: usize,
    pub signed_orbits: usize,
    pub m: u32,
    pub unknowns: usize,
    pub equations: usize,
    pub system_degree: u32,
    pub eq_var_ratio: f64,
    pub ffd_min: Option<u32>,
    pub ffd_max: Option<u32>,
    pub ffd_no_fall: usize,
    pub macaulay: Vec<serde_json::Value>,
    pub targets: usize,
    pub hit_rate: f64,
    pub disagreements: usize,
    pub calibration: Calibration,
    pub oracles: Vec<OraclePrice>,
    pub projected: Vec<ProjectedRelationPhase>,
    pub wall_ns: u64,
}

/// Which cells to price.
#[derive(Clone, Debug, Serialize)]
pub struct OraclePricingConfig {
    pub seed: u64,
    pub targets: usize,
    /// `(n, m)` cells; the base dimension is chosen as in the ledger.
    pub cells: Vec<(u32, u32)>,
    pub f4_node_budget: usize,
    pub sat_conflict_budget: u64,
    pub sat_max_models: usize,
    /// Skip an algebraic engine when the system has more unknowns than
    /// this (it would not finish within the budgets anyway).
    pub max_unknowns: usize,
}

impl Default for OraclePricingConfig {
    fn default() -> Self {
        Self {
            seed: 0x0FA_C1E5,
            targets: 8,
            cells: vec![
                (9, 2),
                (9, 3),
                (11, 2),
                (11, 3),
                (13, 2),
                (13, 3),
                (15, 2),
                (15, 3),
                (17, 2),
                (17, 3),
                (19, 2),
                (19, 3),
                (23, 2),
            ],
            f4_node_budget: 20_000,
            sat_conflict_budget: 200_000,
            sat_max_models: 64,
            max_unknowns: 48,
        }
    }
}

impl OraclePricingConfig {
    pub fn quick() -> Self {
        Self {
            targets: 4,
            cells: vec![(9, 2), (9, 3), (13, 2)],
            ..Self::default()
        }
    }
}

/// Counted exhaustive search: `R − P_i ∈ F` (`m = 2`) or
/// `R − P_i − P_j ∈ F` (`m = 3`), early exit on the first hit.
fn enumerate_counted(
    g: &BinaryGroup,
    fb: &FactorBase<FastPoint>,
    m: u32,
    target: FastPoint,
    ops: &mut GroupOps,
) -> Option<Vec<usize>> {
    let n = fb.points.len();
    for i in 0..n {
        let s = g.add(ops, target, g.neg(fb.points[i]));
        if m == 2 {
            if let Some(&j) = fb.point_index.get(&s.pack()) {
                return Some(vec![i, j]);
            }
            continue;
        }
        if s.infinity {
            continue;
        }
        for j in i..n {
            let t = g.add(ops, s, g.neg(fb.points[j]));
            if let Some(&k) = fb.point_index.get(&t.pack()) {
                return Some(vec![i, j, k]);
            }
        }
    }
    None
}

/// Price one `(n, m)` cell.
/// Whether an `S₄` answer agrees with the exhaustive search.  A witness
/// agrees only if it lifts over the signed base *and* the search found a
/// decomposition; a refutation agrees only if the search found none.  A
/// witness that does not lift is a spurious answer whatever the search
/// said, and is counted against the oracle.
pub fn s4_agrees(found: bool, lifted: bool, truth: bool) -> bool {
    if found {
        lifted && truth
    } else {
        !truth
    }
}

/// The instance and factor base a cell is priced on.  The ledger's base
/// first, then the single top-degree factor the scaling target uses; a
/// candidate must be a linear subspace (the algebraic oracles need one)
/// on which some target decomposes.
type CellBase = (
    BinaryInstance,
    FrobeniusFactorBase,
    String,
    FactorBase<FastPoint>,
    PairTable,
);

fn cell_base(n: u32, m: u32, cfg: &OraclePricingConfig) -> Option<CellBase> {
    let inst = koblitz_instance_best(n)?;
    let kc = inst.koblitz.as_ref()?;
    let g = BinaryGroup(&inst.fast);
    let mut candidates: Vec<(FrobeniusFactorBase, String)> = Vec::new();
    if let Some(c) = choose_koblitz_base(&inst, cfg.seed, 4096) {
        candidates.push(c);
    }
    if let Some(fb) = build_frobenius_factor_base(kc, 0) {
        candidates.push((fb, "invariant subspace of the top-degree factor".into()));
    }
    let mut chosen = None;
    for (frob, description) in candidates {
        if frob.uses_ambient_basis() || frob.points.len() > 4096 {
            continue;
        }
        if !frob.m_can_decompose(kc, m as usize) {
            continue;
        }
        let fb = koblitz_factor_base(
            &inst,
            &frob,
            ColumnFold::SignedFrobeniusOrbit,
            description.clone(),
        )?;
        let table = PairTable::build(&g, &fb);
        if census_hits(&inst, &fb, &Oracle::Mitm { table: &table, m }, 64, cfg.seed) == 0 {
            continue;
        }
        chosen = Some((frob, description, fb, table));
        break;
    }
    let (frob, description, fb, table) = chosen?;
    Some((inst, frob, description, fb, table))
}

pub fn price_cell(n: u32, m: u32, cfg: &OraclePricingConfig) -> Option<OracleCell> {
    let started = Instant::now();
    let (inst, frob, description, fb, table) = cell_base(n, m, cfg)?;
    let kc = inst.koblitz.as_ref()?;
    let g = BinaryGroup(&inst.fast);
    let mut calib = calibrate_binary_instance(&inst);
    calib.ns_per_lookup = table.calibrate_lookup(200_000);
    let basis = fb.subspace_basis.clone()?;
    let s4 = (m == 3).then(|| SubspaceOracle::new(&basis, 1, &inst.gf));
    if let Some(o) = &s4 {
        calibrate_s4(&inst, o, &mut calib);
    }
    let st = FieldStructure::new(n, &kc.curve.irreducible);
    let index_of = frob.index_map();
    let r = inst.r;

    // Targets: random points of the subgroup.
    let mut rng = StdRng::seed_from_u64(cfg.seed ^ ((n as u64) << 8) ^ m as u64);
    let mut ops = GroupOps::default();
    let targets: Vec<FastPoint> = (0..cfg.targets)
        .map(|_| g.mul(&mut ops, inst.generator, rng.gen_range(1..r)))
        .collect();

    // The system, its shape, its fall degree over the draws.
    let mut unknowns = 0usize;
    let mut equations = 0usize;
    let mut degree = 0u32;
    let mut falls: Vec<Option<u32>> = Vec::new();
    let mut macaulay: Vec<serde_json::Value> = Vec::new();
    for (t, target) in targets.iter().enumerate() {
        let x_r = inst.gf.to_element(target.x);
        let sys =
            build_decomposition_system(&frob.subspace_basis, &x_r, &kc.curve.b, m as usize, &st)?;
        unknowns = sys.n_vars;
        equations = sys.equations.len();
        degree = sys
            .equations
            .iter()
            .flat_map(|e| e.terms.iter())
            .map(|term| term.mask.count_ones())
            .max()
            .unwrap_or(0);
        if unknowns <= cfg.max_unknowns {
            let (fall, profiles) = first_fall_degree(&sys.equations, sys.n_vars, 3);
            falls.push(fall);
            if t == 0 {
                macaulay = profiles
                    .iter()
                    .map(|p| {
                        serde_json::json!({"degree": p.degree, "rows": p.rows, "cols": p.cols, "rank": p.rank, "syzygies": p.syzygies()})
                    })
                    .collect();
            }
        }
    }
    let algebra = unknowns <= cfg.max_unknowns;

    let ns_add = calib.ns_per_add;
    let price =
        |native: u64, ns: f64, adds: u64| -> f64 { native as f64 * ns / ns_add + adds as f64 };
    let mut disagreements = 0usize;
    let mut enumerate_rows = Vec::new();
    let mut mitm_rows = Vec::new();
    let mut s4_rows = Vec::new();
    let mut f4_rows = Vec::new();
    let mut sat_rows = Vec::new();
    let mut hits = 0usize;

    for target in &targets {
        // enumerate
        let mut o = GroupOps::default();
        let t0 = Instant::now();
        let by_enum = enumerate_counted(&g, &fb, m, *target, &mut o);
        let wall = t0.elapsed().as_nanos() as u64;
        let truth = by_enum.is_some();
        if truth {
            hits += 1;
        }
        enumerate_rows.push(TargetPrice {
            verdict: if truth {
                Verdict::Found
            } else {
                Verdict::Refuted
            },
            native: o.adds,
            group_adds: o.adds,
            wall_ns: wall,
            gae: o.gae(),
            extra: BTreeMap::new(),
        });

        // meet in the middle
        let mut o = GroupOps::default();
        let mut ctr = OracleCounters::default();
        let t0 = Instant::now();
        let by_mitm = decompose_mitm(&g, &fb, &table, m, &mut o, &mut ctr, *target);
        let wall = t0.elapsed().as_nanos() as u64;
        if by_mitm.is_some() != truth {
            disagreements += 1;
        }
        mitm_rows.push(TargetPrice {
            verdict: if by_mitm.is_some() {
                Verdict::Found
            } else {
                Verdict::Refuted
            },
            native: ctr.lookups,
            group_adds: o.adds,
            wall_ns: wall,
            gae: price(ctr.lookups, calib.ns_per_lookup, o.adds),
            extra: BTreeMap::new(),
        });

        // S₄ pairs-and-solve
        if let Some(oracle) = &s4 {
            let mut o = GroupOps::default();
            let t0 = Instant::now();
            let (witness, pairs) = oracle.decompose(target.x, &inst.gf);
            // The witness is a triple of abscissae.  Lift it over the
            // signed base exactly as the pipeline does before it accepts
            // a relation: some choice of the base points above those
            // abscissae must sum to the target.  The lift is charged to
            // the row, and the agreement test runs in both directions: a
            // witness that does not lift, a witness on a target the
            // exhaustive search refuted, and a refutation on a target it
            // found are all disagreements.
            let lifted = witness
                .as_ref()
                .map(|xs| lift_abscissae(&g, &fb, &mut o, xs, *target).is_some())
                .unwrap_or(false);
            let wall = t0.elapsed().as_nanos() as u64;
            let verdict = match witness {
                Some(_) => Verdict::Found,
                None => Verdict::Refuted,
            };
            if !s4_agrees(verdict == Verdict::Found, lifted, truth) {
                disagreements += 1;
            }
            let mut extra = BTreeMap::new();
            extra.insert(
                "lift_failures".into(),
                u64::from(witness.is_some() && !lifted),
            );
            s4_rows.push(TargetPrice {
                verdict,
                native: pairs,
                group_adds: o.adds,
                wall_ns: wall,
                gae: price(pairs, calib.ns_per_s4_pair.unwrap_or(ns_add), o.adds),
                extra,
            });
        }

        if !algebra {
            continue;
        }
        let target_big = inst.fast.lower(*target);

        // matrix-F4 with splitting
        let before = f4_word_ops_total();
        let profile_before = f4_profile();
        let t0 = Instant::now();
        let (by_f4, stats) = groebner_decompose(
            kc,
            &frob,
            &index_of,
            &st,
            &target_big,
            m as usize,
            SolverEngine::default(),
            cfg.f4_node_budget,
        );
        let wall = t0.elapsed().as_nanos() as u64;
        let words = f4_word_ops_total() - before;
        let profile = f4_profile();
        let verdict = match (&by_f4, stats.exhausted) {
            (Some(_), _) => Verdict::Found,
            (None, false) => Verdict::Refuted,
            (None, true) => Verdict::Inconclusive,
        };
        if verdict != Verdict::Inconclusive && (verdict == Verdict::Found) != truth {
            disagreements += 1;
        }
        let mut extra = BTreeMap::new();
        extra.insert("reductions".into(), stats.reductions as u64);
        extra.insert("splits".into(), stats.splits as u64);
        extra.insert(
            "infeasible_branches".into(),
            stats.infeasible_branches as u64,
        );
        extra.insert("max_degree_built".into(), stats.max_degree_built as u64);
        // Where the engine's word operations went, for the stage profile:
        // the inherited engine's specialisation share is zero under the
        // from-scratch engine.
        extra.insert(
            "f4_specialise_word_ops".into(),
            profile.specialise_word_ops - profile_before.specialise_word_ops,
        );
        extra.insert("f4_calls".into(), profile.calls - profile_before.calls);
        extra.insert("f4_rows".into(), profile.rows - profile_before.rows);
        f4_rows.push(TargetPrice {
            verdict,
            native: words,
            group_adds: 0,
            wall_ns: wall,
            gae: price(words, calib.ns_per_word_xor.unwrap_or(1.0), 0),
            extra,
        });

        // CDCL SAT with native parity rows and degree-2 Macaulay rows
        let options = SatDecompositionOptions {
            conflict_budget: cfg.sat_conflict_budget,
            ..Default::default()
        };
        let t0 = Instant::now();
        let (by_sat, sstats) = sat_decompose_with(
            kc,
            &frob,
            &index_of,
            &st,
            &target_big,
            m as usize,
            cfg.sat_max_models,
            Some(2),
            options,
        );
        let wall = t0.elapsed().as_nanos() as u64;
        let verdict = match (&by_sat, sstats.refuted) {
            (Some(_), _) => Verdict::Found,
            (None, true) => Verdict::Refuted,
            (None, false) => Verdict::Inconclusive,
        };
        if verdict != Verdict::Inconclusive && (verdict == Verdict::Found) != truth {
            disagreements += 1;
        }
        let mut extra = BTreeMap::new();
        extra.insert("solver_calls".into(), sstats.solver_calls as u64);
        extra.insert("models".into(), sstats.models as u64);
        extra.insert("implied_rows".into(), sstats.implied_rows as u64);
        extra.insert("spurious".into(), sstats.spurious as u64);
        // A conflict is priced by its measured wall share: conflicts
        // are the machine-independent count, the conversion is the
        // per-target wall over the per-target conflicts on this host.
        let ns_per_conflict = if sstats.conflicts > 0 {
            wall as f64 / sstats.conflicts as f64
        } else {
            wall as f64
        };
        sat_rows.push(TargetPrice {
            verdict,
            native: sstats.conflicts,
            group_adds: 0,
            wall_ns: wall,
            gae: price(sstats.conflicts.max(1), ns_per_conflict, 0),
            extra,
        });
    }

    let mut oracles = vec![
        OraclePrice::from_targets(
            &format!("enumerate_m{m}"),
            "group_additions",
            enumerate_rows,
        ),
        OraclePrice::from_targets(
            &format!("meet_in_the_middle_m{m}"),
            "pair_table_probes",
            mitm_rows,
        ),
    ];
    if !s4_rows.is_empty() {
        oracles.push(OraclePrice::from_targets(
            "semaev_s4_pairs_and_solve",
            "pairs",
            s4_rows,
        ));
    }
    if !f4_rows.is_empty() {
        oracles.push(OraclePrice::from_targets(
            "matrix_f4_splitting",
            "word_xors",
            f4_rows,
        ));
    }
    if !sat_rows.is_empty() {
        oracles.push(OraclePrice::from_targets(
            "cdcl_sat_native_xor",
            "conflicts",
            sat_rows,
        ));
    }

    // Extrapolated relation phase: (K + 1) relations at the measured
    // hit rate, each target at the oracle's mean price.
    let hit_rate = hits as f64 / targets.len().max(1) as f64;
    let needed = (fb.columns as f64 + 1.0) / hit_rate.max(1.0 / (4.0 * targets.len() as f64));
    let sqrt_r = (r as f64).sqrt();
    let floor = generic_floor_s(2.0 * n as f64);
    let projected: Vec<ProjectedRelationPhase> = oracles
        .iter()
        .map(|o| {
            let gae = needed * o.gae_per_target_mean;
            ProjectedRelationPhase {
                oracle: o.oracle.clone(),
                targets_needed: needed,
                relation_phase_gae: gae,
                s_projected: gae / sqrt_r,
                s_over_rho_floor: gae / sqrt_r / floor,
                extrapolation: true,
            }
        })
        .collect();

    let seen: Vec<u32> = falls.iter().flatten().copied().collect();
    Some(OracleCell {
        curve: inst.describe(),
        n,
        a: inst.a,
        r,
        log2_r: (r as f64).log2(),
        group_order: inst.group_order,
        factor_base: description,
        dimension: frob.ell,
        signed_points: fb.points.len(),
        signed_orbits: fb.columns,
        m,
        unknowns,
        equations,
        system_degree: degree,
        eq_var_ratio: equations as f64 / unknowns.max(1) as f64,
        ffd_min: seen.iter().copied().min(),
        ffd_max: seen.iter().copied().max(),
        ffd_no_fall: falls.iter().filter(|f| f.is_none()).count(),
        macaulay,
        targets: targets.len(),
        hit_rate,
        disagreements,
        calibration: calib,
        oracles,
        projected,
        wall_ns: started.elapsed().as_nanos() as u64,
    })
}

/// Price every cell of the configuration.
pub fn price_oracles(cfg: &OraclePricingConfig, mut progress: impl FnMut(&str)) -> Vec<OracleCell> {
    let mut out = Vec::new();
    for &(n, m) in &cfg.cells {
        progress(&format!("oracles: n = {n}, m = {m}"));
        match price_cell(n, m, cfg) {
            Some(cell) => {
                progress(&format!(
                    "oracles: n = {n}, m = {m}: {} unknowns, FFD {:?}..{:?}, {} disagreements",
                    cell.unknowns, cell.ffd_min, cell.ffd_max, cell.disagreements
                ));
                out.push(cell);
            }
            None => progress(&format!("oracles: n = {n}, m = {m}: no instance")),
        }
    }
    out
}

/// One oracle call, natively counted, with its verdict.
#[derive(Clone, Debug, Serialize)]
pub struct SwapCall {
    pub verdict: Verdict,
    pub native: u64,
    pub wall_ns: u64,
}

/// One oracle on one swap pair: the built target `R`, then `R − P + Q`
/// for a summand `P` of `R` and a class-matched base point `Q`.
#[derive(Clone, Debug, Serialize)]
pub struct SwapPair {
    pub on_target: SwapCall,
    pub on_swap: SwapCall,
    /// `native(R − P + Q) / native(R)`: the number section 3.2 of the
    /// decomposition note needs to be a constant.
    pub ratio: f64,
}

/// One oracle over every swap pair of a cell.
#[derive(Clone, Debug, Serialize)]
pub struct SwapPrice {
    pub oracle: String,
    pub native_unit: String,
    pub found_on_target: usize,
    pub found_on_swap: usize,
    pub inconclusive: usize,
    pub ratio_min: f64,
    pub ratio_median: f64,
    pub ratio_max: f64,
    pub pairs: Vec<SwapPair>,
}

/// One cell of swap pairs, priced by every oracle.
#[derive(Clone, Debug, Serialize)]
pub struct SwapCell {
    pub curve: serde_json::Value,
    pub n: u32,
    pub a: u64,
    pub r: u64,
    pub cofactor: u64,
    pub factor_base: String,
    pub dimension: u32,
    pub signed_points: usize,
    pub signed_orbits: usize,
    pub m: u32,
    pub pairs: usize,
    pub oracles: Vec<SwapPrice>,
    pub wall_ns: u64,
}

/// Price every oracle on `R` and on `R − P + Q`, pairwise.
///
/// Section 3.2 of the decomposition note localises a whole-base
/// detector's witness by asking it about `R − P + Q` instead of `R`,
/// and that reduction is only free if a detector charges the same for
/// the swapped point as for the original.  Here `R` is built as a sum
/// of `m` distinct base points landing in `⟨G⟩`, `P` is one of them,
/// and `Q` is drawn from the base points of `P`'s cofactor class that
/// are neither summands nor their negatives -- so `R − P + Q` is
/// literally another `m`-sum of base points, which is the branch the
/// swap relies on.  Every oracle sees both points of every pair and
/// reports its native count on each; the ratio is what is being asked.
pub fn price_swap_cell(n: u32, m: u32, cfg: &OraclePricingConfig) -> Option<SwapCell> {
    let started = Instant::now();
    let (inst, frob, description, fb, table) = cell_base(n, m, cfg)?;
    let kc = inst.koblitz.as_ref()?;
    let g = BinaryGroup(&inst.fast);
    let r = inst.r;
    let basis = fb.subspace_basis.clone()?;
    let s4 = (m == 3).then(|| SubspaceOracle::new(&basis, 1, &inst.gf));
    let st = FieldStructure::new(n, &kc.curve.irreducible);
    let index_of = frob.index_map();
    let algebra = {
        let x_r = inst.gf.to_element(inst.generator.x);
        build_decomposition_system(&frob.subspace_basis, &x_r, &kc.curve.b, m as usize, &st)
            .is_some_and(|sys| sys.n_vars <= cfg.max_unknowns)
    };

    // Cofactor class of every base point: `[r]P` in the small torsion.
    let mut ops = GroupOps::default();
    let class: Vec<FastPoint> = fb.points.iter().map(|&p| g.mul(&mut ops, p, r)).collect();

    let mut rng = StdRng::seed_from_u64(cfg.seed ^ ((n as u64) << 8) ^ m as u64 ^ 0x5741_5000);
    let mut targets: Vec<(FastPoint, FastPoint)> = Vec::new();
    let mut guard = 0usize;
    while targets.len() < cfg.targets && guard < 1000 * cfg.targets {
        guard += 1;
        let mut picks: Vec<usize> = Vec::with_capacity(m as usize);
        while picks.len() < m as usize {
            let i = rng.gen_range(0..fb.points.len());
            if !picks.contains(&i) && !picks.iter().any(|&j| fb.neg_index[j] == i) {
                picks.push(i);
            }
        }
        let mut target = FastPoint::INFINITY;
        for &i in &picks {
            target = g.add(&mut ops, target, fb.points[i]);
        }
        if target.infinity || !g.mul(&mut ops, target, r).infinity {
            continue;
        }
        let p = picks[0];
        let pool: Vec<usize> = (0..fb.points.len())
            .filter(|&q| {
                class[q] == class[p] && !picks.contains(&q) && !picks.contains(&fb.neg_index[q])
            })
            .collect();
        if pool.is_empty() {
            continue;
        }
        let q = pool[rng.gen_range(0..pool.len())];
        let minus_p = g.add(&mut ops, target, g.neg(fb.points[p]));
        let swapped = g.add(&mut ops, minus_p, fb.points[q]);
        assert!(
            g.mul(&mut ops, swapped, r).infinity,
            "class match keeps the swap in <G>"
        );
        targets.push((target, swapped));
    }
    if targets.len() < cfg.targets {
        return None;
    }

    let price = |target: FastPoint| -> Vec<(&'static str, &'static str, SwapCall)> {
        let mut out = Vec::new();
        let mut o = GroupOps::default();
        let t0 = Instant::now();
        let found = enumerate_counted(&g, &fb, m, target, &mut o).is_some();
        out.push((
            "enumerate",
            "group_additions",
            SwapCall {
                verdict: if found {
                    Verdict::Found
                } else {
                    Verdict::Refuted
                },
                native: o.adds,
                wall_ns: t0.elapsed().as_nanos() as u64,
            },
        ));

        let mut o = GroupOps::default();
        let mut ctr = OracleCounters::default();
        let t0 = Instant::now();
        let found = decompose_mitm(&g, &fb, &table, m, &mut o, &mut ctr, target).is_some();
        out.push((
            "meet_in_the_middle",
            "pair_table_probes",
            SwapCall {
                verdict: if found {
                    Verdict::Found
                } else {
                    Verdict::Refuted
                },
                native: ctr.lookups,
                wall_ns: t0.elapsed().as_nanos() as u64,
            },
        ));

        if let Some(oracle) = &s4 {
            let mut o = GroupOps::default();
            let t0 = Instant::now();
            let (witness, pairs) = oracle.decompose(target.x, &inst.gf);
            let lifted = witness
                .as_ref()
                .is_some_and(|xs| lift_abscissae(&g, &fb, &mut o, xs, target).is_some());
            out.push((
                "semaev_s4_pairs_and_solve",
                "pairs",
                SwapCall {
                    verdict: if lifted {
                        Verdict::Found
                    } else {
                        Verdict::Refuted
                    },
                    native: pairs,
                    wall_ns: t0.elapsed().as_nanos() as u64,
                },
            ));
        }

        if !algebra {
            return out;
        }
        let target_big = inst.fast.lower(target);
        let before = f4_word_ops_total();
        let t0 = Instant::now();
        let (by_f4, stats) = groebner_decompose(
            kc,
            &frob,
            &index_of,
            &st,
            &target_big,
            m as usize,
            SolverEngine::default(),
            cfg.f4_node_budget,
        );
        let wall = t0.elapsed().as_nanos() as u64;
        out.push((
            "matrix_f4_splitting",
            "word_xors",
            SwapCall {
                verdict: match (&by_f4, stats.exhausted) {
                    (Some(_), _) => Verdict::Found,
                    (None, false) => Verdict::Refuted,
                    (None, true) => Verdict::Inconclusive,
                },
                native: f4_word_ops_total() - before,
                wall_ns: wall,
            },
        ));

        let options = SatDecompositionOptions {
            conflict_budget: cfg.sat_conflict_budget,
            ..Default::default()
        };
        let t0 = Instant::now();
        let (by_sat, sstats) = sat_decompose_with(
            kc,
            &frob,
            &index_of,
            &st,
            &target_big,
            m as usize,
            cfg.sat_max_models,
            Some(2),
            options,
        );
        out.push((
            "cdcl_sat_native_xor",
            "conflicts",
            SwapCall {
                verdict: match (&by_sat, sstats.refuted) {
                    (Some(_), _) => Verdict::Found,
                    (None, true) => Verdict::Refuted,
                    (None, false) => Verdict::Inconclusive,
                },
                native: sstats.conflicts,
                wall_ns: t0.elapsed().as_nanos() as u64,
            },
        ));
        out
    };

    let mut rows: Vec<(&str, &str, Vec<SwapPair>)> = Vec::new();
    for &(target, swapped) in &targets {
        for ((name, unit, on_target), (_, _, on_swap)) in
            price(target).into_iter().zip(price(swapped))
        {
            let ratio = on_swap.native as f64 / on_target.native.max(1) as f64;
            let pair = SwapPair {
                on_target,
                on_swap,
                ratio,
            };
            match rows.iter_mut().find(|(o, _, _)| *o == name) {
                Some((_, _, pairs)) => pairs.push(pair),
                None => rows.push((name, unit, vec![pair])),
            }
        }
    }
    let oracles = rows
        .into_iter()
        .map(|(name, unit, pairs)| {
            let ratios: Vec<f64> = pairs.iter().map(|p| p.ratio).collect();
            SwapPrice {
                oracle: name.into(),
                native_unit: unit.into(),
                found_on_target: pairs
                    .iter()
                    .filter(|p| p.on_target.verdict == Verdict::Found)
                    .count(),
                found_on_swap: pairs
                    .iter()
                    .filter(|p| p.on_swap.verdict == Verdict::Found)
                    .count(),
                inconclusive: pairs
                    .iter()
                    .filter(|p| {
                        p.on_target.verdict == Verdict::Inconclusive
                            || p.on_swap.verdict == Verdict::Inconclusive
                    })
                    .count(),
                ratio_min: ratios.iter().copied().fold(f64::INFINITY, f64::min),
                ratio_median: median(ratios.clone()),
                ratio_max: ratios.iter().copied().fold(f64::NEG_INFINITY, f64::max),
                pairs,
            }
        })
        .collect();

    Some(SwapCell {
        curve: inst.describe(),
        n,
        a: inst.a,
        r,
        cofactor: inst.cofactor,
        factor_base: description,
        dimension: frob.ell,
        signed_points: fb.points.len(),
        signed_orbits: fb.columns,
        m,
        pairs: targets.len(),
        oracles,
        wall_ns: started.elapsed().as_nanos() as u64,
    })
}

/// Price the swap pairs of every cell of the configuration.
pub fn price_swaps(cfg: &OraclePricingConfig, mut progress: impl FnMut(&str)) -> Vec<SwapCell> {
    let mut out = Vec::new();
    for &(n, m) in &cfg.cells {
        progress(&format!("swaps: n = {n}, m = {m}"));
        match price_swap_cell(n, m, cfg) {
            Some(cell) => {
                for o in &cell.oracles {
                    progress(&format!(
                        "swaps: n = {n}, m = {m}: {} ratio {:.3}..{:.3} (median {:.3})",
                        o.oracle, o.ratio_min, o.ratio_max, o.ratio_median
                    ));
                }
                out.push(cell);
            }
            None => progress(&format!("swaps: n = {n}, m = {m}: no instance")),
        }
    }
    out
}

/// Markdown table of the cells.
pub fn format_oracle_markdown(cells: &[OracleCell]) -> String {
    let mut out = String::new();
    out.push_str("| n | dim | m | unknowns | eqs | deg | FFD | hit rate | oracle | found/refuted/inconc | native (median refuted) | ms (median refuted) | GAE/target | projected S | vs floor |\n");
    out.push_str("|--:|--:|--:|--:|--:|--:|:--|--:|:--|:--|--:|--:|--:|--:|--:|\n");
    for c in cells {
        let ffd = match (c.ffd_min, c.ffd_max) {
            (Some(a), Some(b)) if a == b => format!("{a}"),
            (Some(a), Some(b)) => format!("{a}–{b}"),
            _ => "—".into(),
        };
        for (o, p) in c.oracles.iter().zip(&c.projected) {
            out.push_str(&format!(
                "| {} | {} | {} | {} | {} | {} | {} | {:.2} | {} | {}/{}/{} | {} | {} | {:.3e} | {:.3e} | {:.3e} |\n",
                c.n,
                c.dimension,
                c.m,
                c.unknowns,
                c.equations,
                c.system_degree,
                ffd,
                c.hit_rate,
                o.oracle,
                o.found,
                o.refuted,
                o.inconclusive,
                if o.native_median_refuted.is_nan() {
                    "—".to_string()
                } else {
                    format!("{:.0}", o.native_median_refuted)
                },
                if o.ms_median_refuted.is_nan() {
                    "—".to_string()
                } else {
                    format!("{:.3}", o.ms_median_refuted)
                },
                o.gae_per_target_mean,
                p.s_projected,
                p.s_over_rho_floor,
            ));
        }
    }
    out
}

/// Expected steps of the signed-Frobenius rho on the same subgroup, for
/// the projection's denominator.
pub fn rho_floor_ops(cell: &OracleCell) -> f64 {
    generic_floor_ops(cell.r as f64, 2.0 * cell.n as f64)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_oracle_agrees_on_a_small_cell() {
        let cfg = OraclePricingConfig {
            targets: 4,
            ..OraclePricingConfig::default()
        };
        let cell = price_cell(9, 2, &cfg).expect("K_0 / 2^9");
        assert_eq!(cell.disagreements, 0, "{cell:?}");
        assert!(cell.unknowns > 0 && cell.equations > 0);
        assert_eq!(cell.system_degree, 2);
        let names: Vec<&str> = cell.oracles.iter().map(|o| o.oracle.as_str()).collect();
        assert!(names.contains(&"matrix_f4_splitting"));
        assert!(names.contains(&"cdcl_sat_native_xor"));
        for o in &cell.oracles {
            assert_eq!(
                o.found + o.refuted + o.inconclusive,
                cell.targets,
                "{}",
                o.oracle
            );
        }
        let f4 = cell
            .oracles
            .iter()
            .find(|o| o.oracle == "matrix_f4_splitting")
            .unwrap();
        assert!(f4.native_total > 0, "F4 word ops must be counted");
        assert_eq!(cell.projected.len(), cell.oracles.len());
    }

    #[test]
    fn a_chained_cell_is_cubic_and_prices_the_s4_oracle_too() {
        let cfg = OraclePricingConfig {
            targets: 3,
            ..OraclePricingConfig::default()
        };
        let cell = price_cell(9, 3, &cfg).expect("K_0 / 2^9, m = 3");
        assert_eq!(cell.disagreements, 0, "{cell:?}");
        assert_eq!(cell.system_degree, 3);
        let s4 = cell
            .oracles
            .iter()
            .find(|o| o.oracle == "semaev_s4_pairs_and_solve")
            .expect("the S4 oracle is priced at m = 3");
        assert_eq!(
            s4.extra_totals.get("lift_failures").copied().unwrap_or(0),
            0,
            "every S4 witness must lift over the signed base"
        );
        assert!(rho_floor_ops(&cell) > 0.0);
        let table = format_oracle_markdown(&[cell]);
        assert!(table.contains("semaev_s4_pairs_and_solve"));
    }

    #[test]
    fn a_swapped_point_is_an_m_sum_and_every_oracle_sees_both_points() {
        let cfg = OraclePricingConfig {
            targets: 3,
            ..OraclePricingConfig::default()
        };
        let cell = price_swap_cell(9, 2, &cfg).expect("K_0 / 2^9, m = 2");
        assert_eq!(cell.pairs, 3);
        for o in &cell.oracles {
            assert_eq!(o.pairs.len(), cell.pairs, "{}", o.oracle);
            // `R − P + Q` is built as a sum of base points, so a conclusive
            // oracle must decompose it exactly as often as it finds `R`.
            if o.inconclusive == 0 {
                assert_eq!(o.found_on_swap, cell.pairs, "{}", o.oracle);
                assert_eq!(o.found_on_target, cell.pairs, "{}", o.oracle);
            }
            assert!(
                o.ratio_min <= o.ratio_median && o.ratio_median <= o.ratio_max,
                "{}",
                o.oracle
            );
        }
        let names: Vec<&str> = cell.oracles.iter().map(|o| o.oracle.as_str()).collect();
        assert!(names.contains(&"matrix_f4_splitting"));
        assert!(names.contains(&"cdcl_sat_native_xor"));
    }

    #[test]
    fn s4_agreement_is_checked_in_both_directions() {
        // (found, lifted, truth) -> agrees
        assert!(s4_agrees(true, true, true));
        assert!(
            !s4_agrees(true, true, false),
            "a witness on a refuted target"
        );
        assert!(
            !s4_agrees(true, false, true),
            "a witness that does not lift"
        );
        assert!(
            !s4_agrees(true, false, false),
            "a spurious witness on a refuted target"
        );
        assert!(s4_agrees(false, false, false));
        assert!(
            !s4_agrees(false, false, true),
            "a refutation on a decomposable target"
        );
    }
}
