//! Area `dlp`: generic discrete logarithms: Pollard rho (Floyd, distinguished
//! points, automorphism-folded), BSGS, Gaudry–Schost, Pohlig–Hellman and
//! the collaborative rho walker.
//!
//! Every kernel is a full solve of a fixed planted instance through the
//! public entry point a research pipeline or CI job calls, with the walk's
//! seed fixed, so the work is the same every run and the fingerprint covers
//! the recovered logarithm and every operation counter the entry point
//! reports (wall-clock fields excluded).  Instances are sized so one solve
//! is 10–300 ms at one thread.
//!
//! These are the crypto crate's `dlp` kernels, same IDs and inputs, with
//! two exceptions: this crate has no `ecc2k130_guard`, so there is no
//! cycle-certificate cell, and its `pohlig_hellman_curve` solves a digit
//! by BSGS or rho rather than a linear search, so its Pohlig–Hellman cell
//! solves eight targets (under its own ID) to reach the size floor.
//!
//! Parallelism: only the `bsgs_fast` kernels use rayon.  The `_w1` kernel
//! pins the plan to one worker, so every counter is thread-count
//! independent.  The `_w4` kernel pins it to four workers (so it has the
//! same chains at any pool size) and fingerprints what is independent of
//! thread timing: the verified logarithms, `baby_steps` and
//! `table_entries`.  Its `giant_steps`, `candidates` and
//! `false_candidates` depend on when the other workers see the early-exit
//! flag, so they are left out.

use crate::harness::{Closure, Fp, Kernel, Tier, Workload};
use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::aut_folded_rho::{
    aut_folded_rho_dlp, FoldedRhoOptions, J0CurveAut,
};
use cryptanalysis_suite::cryptanalysis::bsgs_fast::{toy40, BsgsFast, BsgsFastPlan, FastPoint};
use cryptanalysis_suite::cryptanalysis::cga_hnc::{pt_scalar_mul, Pt2};
use cryptanalysis_suite::cryptanalysis::ecdlp_variants::gaudry_schost::{
    gaudry_schost_negation, GaudrySchostOptions,
};
use cryptanalysis_suite::cryptanalysis::ecdlp_variants::EcGroup;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    koblitz_signed_frobenius_rho_with_progress, KoblitzCurve, KoblitzSignedRhoOptions,
    KoblitzSignedRhoReport,
};
use cryptanalysis_suite::cryptanalysis::pohlig_hellman::pohlig_hellman_curve;
use cryptanalysis_suite::cryptanalysis::pollard_collab::{
    demo_curve, run_walker, JobSpec, WalkerOutcome,
};
use cryptanalysis_suite::cryptanalysis::pollard_rho::{
    pollard_rho_dlp_zp, pollard_rho_dp_dlp_zp_multi, DpRhoOptions, RhoOptions,
};
use cryptanalysis_suite::ecc::curve::CurveParams;
use cryptanalysis_suite::ecc::point::Point;
use num_bigint::{BigInt, BigUint};

// ── Fingerprint helpers ─────────────────────────────────────────────

fn fp_big(fp: Fp, x: &BigUint) -> Fp {
    fp.words(&x.to_u64_digits())
}

fn fp_bigint(fp: Fp, x: &BigInt) -> Fp {
    let (sign, digits) = x.to_u64_digits();
    fp.u64(sign as u64).words(&digits)
}

/// `x mod m` for a fixed pseudo-random `x`: the planted logarithms.
fn planted(i: u64, m: u64) -> u64 {
    let mut z = i.wrapping_add(0x9e37_79b9_7f4a_7c15);
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    1 + (z ^ (z >> 31)) % (m - 1)
}

// ── Pollard rho over Z_p^* (BigUint) ─────────────────────────────────

/// `p = 2q + 1` with `q` prime (36-bit); `4` generates the order-`q`
/// subgroup.
const SAFE_Q36: u64 = 34_454_481_053;
/// `p = 2q + 1` with `q` prime (34-bit).
const SAFE_Q34: u64 = 8_684_676_989;

/// Floyd rho (`pollard_rho_dlp_zp`, the generic `pollard_rho_dlp` with
/// `Z_p^*` closures) on the order-`q` subgroup, `q` 36 bits.
fn rho_floyd_zp_q36() -> Box<dyn Workload> {
    let q = BigUint::from(SAFE_Q36);
    let p = &q * 2u32 + 1u32;
    let g = BigUint::from(4u32);
    let x = BigUint::from(planted(1, SAFE_Q36));
    let h = g.modpow(&x, &p);
    let opts = RhoOptions {
        max_iterations: 1 << 24,
        max_restarts: 4,
        seed: Some(0x0dd5_eed1),
    };
    Box::new(Closure(move || {
        let sol = pollard_rho_dlp_zp(&g, &h, &p, &q, &opts).expect("rho solves");
        assert_eq!(g.modpow(&sol.x, &p), h);
        fp_big(Fp::new(), &sol.x).u64(sol.iterations).finish()
    }))
}

/// Distinguished-point rho with a per-target table
/// (`pollard_rho_dp_dlp_zp_multi`), three targets in the order-`q`
/// subgroup, `q` 34 bits, `dp_bits = 8`.
fn rho_dp_zp_multi_q34_x3() -> Box<dyn Workload> {
    let q = BigUint::from(SAFE_Q34);
    let p = &q * 2u32 + 1u32;
    let g = BigUint::from(4u32);
    let targets: Vec<BigUint> = (0..3)
        .map(|i| g.modpow(&BigUint::from(planted(100 + i, SAFE_Q34)), &p))
        .collect();
    let opts = DpRhoOptions {
        dp_bits: 8,
        max_walkers: 1 << 20,
        max_steps_per_walker: 1 << 16,
        seed: Some(0x0d0d_5eed),
    };
    Box::new(Closure(move || {
        let sols = pollard_rho_dp_dlp_zp_multi(&g, &targets, &p, &q, &opts).expect("solves");
        let mut fp = Fp::new().usize(sols.len());
        for s in &sols {
            fp = fp_big(fp, &s.x).u64(s.iterations);
        }
        fp.finish()
    }))
}

// ── Single-word BSGS (bsgs_fast) ─────────────────────────────────────

fn bsgs_targets(count: u64, x0: u64, width: u64) -> Vec<FastPoint> {
    let curve = toy40();
    (0..count)
        .map(|i| curve.scalar_mul(curve.g, x0 + planted(200 + i, width)))
        .collect()
}

/// `BsgsFast::build` over the whole toy40 group (negation map, one worker,
/// 32 chains sharing an inversion) and `solve_many` of four targets.
fn bsgs_fast_toy40_w1_x4() -> Box<dyn Workload> {
    let curve = toy40();
    let qs = bsgs_targets(4, 0, curve.n);
    Box::new(Closure(move || {
        let plan = BsgsFastPlan::new(curve.n, 0, true, 1, 32);
        let mut solver = BsgsFast::build(curve, plan);
        let xs = solver.solve_many(&qs);
        let st = solver.stats();
        let mut fp = Fp::new();
        for x in &xs {
            fp = fp.u64(x.unwrap_or(u64::MAX));
        }
        fp.u64(st.baby_steps)
            .u64(st.giant_steps)
            .u64(st.candidates)
            .u64(st.false_candidates)
            .u64(st.table_entries)
            .finish()
    }))
}

/// `BsgsFast` on a `2^38`-wide interval of toy40 with four workers of 8
/// chains, eight targets.  Fingerprints the timing-independent outputs
/// only (see the module note).
fn bsgs_fast_toy40_w4_interval38_x8() -> Box<dyn Workload> {
    let curve = toy40();
    let x0 = 0x12_3456_789a % curve.n;
    let width = 1u64 << 38;
    let qs = bsgs_targets(8, x0, width);
    Box::new(Closure(move || {
        let plan = BsgsFastPlan::new(width, x0, true, 4, 8);
        let mut solver = BsgsFast::build(curve, plan);
        let xs = solver.solve_many(&qs);
        let st = solver.stats();
        let mut fp = Fp::new();
        for x in &xs {
            fp = fp.u64(x.unwrap_or(u64::MAX));
        }
        fp.u64(st.baby_steps).u64(st.table_entries).finish()
    }))
}

// ── Pohlig–Hellman on a smooth-order curve ───────────────────────────

/// `y² = x³ + 4` over a 47-bit prime; the point below has order
/// `N = 3 · 19⁴ · 151 · 181 · 13171` (found by a CM search on the six
/// `j = 0` twists).
fn ph_curve() -> CurveParams {
    CurveParams {
        name: "perfbench-j0-smooth47",
        p: BigUint::from(140_737_529_461_027u64),
        a: BigUint::from(0u32),
        b: BigUint::from(4u32),
        gx: BigUint::from(16_535_943_672_630u64),
        gy: BigUint::from(38_148_592_391_465u64),
        n: BigUint::from(140_737_531_856_763u64),
        h: 1,
    }
}

/// `pohlig_hellman_curve` (the invalid-curve attack's solver) with
/// smoothness bound `2^14`, for eight planted logarithms: factor the order
/// (trial division, Miller–Rabin, Pollard–Brent), solve each prime-power
/// digit by BSGS or rho, then CRT.  One solve takes a few milliseconds,
/// under the size floor, hence eight and the `_x8` ID.
fn pohlig_hellman_smooth47_x8() -> Box<dyn Workload> {
    let curve = ph_curve();
    let g = curve.generator();
    let cases: Vec<(BigUint, Point)> = (0..8)
        .map(|i| {
            let d = BigUint::from(planted(300 + i, 140_737_531_856_763));
            let q = g.scalar_mul(&d, &curve.a_fe());
            (d, q)
        })
        .collect();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for (d, q) in &cases {
            let r = pohlig_hellman_curve(&curve, &g, q, &curve.n, 1 << 14);
            assert_eq!(r.recovered_d.as_ref(), Some(d));
            fp = fp_big(fp, r.recovered_d.as_ref().expect("solved"));
            fp = fp.usize(r.factors.len());
            for (f, e) in &r.factors {
                fp = fp_big(fp, f).u64(u64::from(*e));
            }
            fp = fp.usize(r.residues.len());
            for (m, v) in &r.residues {
                fp = fp_big(fp_big(fp, m), v);
            }
            fp = fp.u64(r.total_steps);
        }
        fp.finish()
    }))
}

// ── Signed-Frobenius rho on a Koblitz curve ──────────────────────────

fn fp_signed_rho(fp: Fp, r: &KoblitzSignedRhoReport) -> Fp {
    let c = &r.charges;
    let fp = match &r.recovered_log {
        Some(x) => fp_big(fp.u64(1), x),
        None => fp.u64(0),
    };
    fp.bool(r.verified)
        .bool(r.exhausted)
        .u64(r.iterations)
        .u64(u64::from(r.restarts_attempted))
        .u64(u64::from(r.jump_table_rebuilds))
        .usize(r.parallel_walks)
        .u64(c.coefficient_draws)
        .u64(c.setup_scalar_multiplications)
        .u64(c.setup_group_additions)
        .u64(c.walk_group_additions)
        .u64(c.candidate_verification_scalar_multiplications)
        .u64(c.canonicalizations)
        .u64(c.frobenius_maps)
        .u64(c.negations_examined)
        .u64(c.partition_hashes)
        .u64(c.collisions)
        .u64(c.failed_collisions)
        .u64(c.fruitless_cycles)
        .u64(c.cycle_escape_doublings)
}

/// `koblitz_signed_frobenius_rho_with_progress` (single-word fast path,
/// orbit size `2n = 82`) on `K_0 / F_2^41`, whose subgroup order is a
/// 40-bit prime; default jumps and walks, fixed seed.
fn koblitz_signed_rho_k0_n41() -> Box<dyn Workload> {
    let kc = KoblitzCurve::new(0, 41).expect("K_0 over F_2^41");
    let r = kc.subgroup_order.to_u64_digits()[0];
    let d = BigUint::from(planted(400, r));
    let q: BinaryPoint = kc.mul(kc.generator(), &d);
    let opts = KoblitzSignedRhoOptions {
        seed: 0x4b30_3431,
        progress_interval: 0,
        ..KoblitzSignedRhoOptions::default()
    };
    Box::new(Closure(move || {
        let r = koblitz_signed_frobenius_rho_with_progress(&kc, &q, &opts, &mut |_| {});
        assert!(r.verified);
        fp_signed_rho(Fp::new(), &r).finish()
    }))
}

// ── Aut(E)-folded rho on a j = 0 curve ───────────────────────────────

/// `aut_folded_rho_dlp` (6-fold Floyd rho, BigInt arithmetic) on
/// `y² = x³ + 2` over a 25-bit prime with prime order `n`.
fn aut_folded_rho_j0_p25() -> Box<dyn Workload> {
    let aut = J0CurveAut {
        p: BigInt::from(33_756_013u64),
        a: BigInt::from(0),
        b: BigInt::from(2),
        n: BigInt::from(33_750_391u64),
        beta: BigInt::from(13_339_116u64),
        lambda: BigInt::from(25_380_340u64),
    };
    let g = Pt2::Aff(BigInt::from(8_339_409u64), BigInt::from(9_189_288u64));
    let d = BigInt::from(planted(500, 33_750_391));
    let h = pt_scalar_mul(&g, &d, &aut.a, &aut.p);
    let opts = FoldedRhoOptions {
        max_iterations: 1 << 22,
        max_restarts: 16,
        seed: Some(0x0a07_f01d),
    };
    Box::new(Closure(move || {
        let s = aut_folded_rho_dlp(&g, &h, &aut, &opts).expect("folded rho solves");
        fp_bigint(Fp::new(), &s.d)
            .u64(s.iterations)
            .u64(u64::from(s.restarts))
            .u64(s.effective_rho_factor.to_bits())
            .finish()
    }))
}

// ── Gaudry–Schost with the negation map (general arithmetic) ─────────

/// `ecdlp_variants::gaudry_schost_negation` on the 32-bit prime-order
/// `demo-32` curve, `dp_bits = 8`, 32 jumps.
fn gaudry_schost_negation_demo32() -> Box<dyn Workload> {
    let curve = demo_curve("demo-32").expect("demo-32");
    let n = curve.n.to_u64_digits()[0];
    let group = EcGroup::from_curve(&curve);
    let q = group.mul_setup(&BigUint::from(planted(600, n)));
    let opts = GaudrySchostOptions {
        dp_bits: 8,
        num_jumps: 32,
        max_walkers: 1 << 22,
        max_steps_per_walker: 0,
        block: 32,
        seed: Some(0x6a57_5eed),
    };
    Box::new(Closure(move || {
        let s = gaudry_schost_negation(&group, &q, &opts).expect("GS solves");
        fp_big(Fp::new(), &s.x)
            .u64(s.group_ops)
            .u64(s.field_inversions)
            .usize(s.table_size)
            .finish()
    }))
}

// ── Collaborative rho walkers ────────────────────────────────────────

/// `pollard_collab::run_walker` for walkers `0..8` of a `demo-32` job
/// with the negation map and `dp_bits = 10`: the per-lane unit of work of
/// the distributed campaign.
fn collab_walkers_demo32_x8() -> Box<dyn Workload> {
    let curve = demo_curve("demo-32").expect("demo-32");
    let n = curve.n.to_u64_digits()[0];
    let q = curve
        .generator()
        .scalar_mul(&BigUint::from(planted(700, n)), &curve.a_fe());
    let mut spec = JobSpec::new(&curve, &q, "perfbench", 0x0c07_1ab5).expect("job spec");
    spec.dp_bits = 10;
    spec.negation_map = true;
    let ctx = spec.build().expect("job context");
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for i in 0..8u64 {
            fp = match run_walker(&ctx, i) {
                WalkerOutcome::Dp(r) => fp
                    .u64(1)
                    .u64(r.walker)
                    .u64(r.steps)
                    .str(&r.x)
                    .str(&r.y)
                    .str(&r.a)
                    .str(&r.b),
                WalkerOutcome::DeadTrail { steps } => fp.u64(2).u64(steps),
            };
        }
        fp.finish()
    }))
}

pub fn register(kernels: &mut Vec<Kernel>) {
    let mut add =
        |id: &'static str, desc: &'static str, tier: Tier, setup: fn() -> Box<dyn Workload>| {
            kernels.push(Kernel {
                id,
                area: "dlp",
                desc,
                tier,
                setup,
            });
        };
    add(
        "dlp/rho_floyd_zp_q36",
        "pollard_rho_dlp_zp (Floyd, BigUint) on the 36-bit prime-order subgroup of a safe-prime Z_p^*",
        Tier::Quick,
        rho_floyd_zp_q36,
    );
    add(
        "dlp/rho_dp_zp_multi_q34_x3",
        "pollard_rho_dp_dlp_zp_multi, 3 targets, 34-bit subgroup of Z_p^*, dp_bits 8",
        Tier::Quick,
        rho_dp_zp_multi_q34_x3,
    );
    add(
        "dlp/bsgs_fast_toy40_w1_x4",
        "bsgs_fast::BsgsFast build + solve_many, whole toy40 group, neg map, 1 worker x 32 chains, 4 targets",
        Tier::Quick,
        bsgs_fast_toy40_w1_x4,
    );
    add(
        "dlp/bsgs_fast_toy40_w4_interval38_x8",
        "bsgs_fast::BsgsFast build + solve_many, 2^38 interval of toy40, 4 workers x 8 chains, 8 targets",
        Tier::Quick,
        bsgs_fast_toy40_w4_interval38_x8,
    );
    add(
        "dlp/pohlig_hellman_smooth47_x8",
        "pohlig_hellman_curve, 8 targets, on a j=0 curve over a 47-bit prime, order 3*19^4*151*181*13171",
        Tier::Quick,
        pohlig_hellman_smooth47_x8,
    );
    add(
        "dlp/koblitz_signed_rho_k0_n41",
        "koblitz_signed_frobenius_rho_with_progress (fast path, 82-fold) on K_0/F_2^41, 40-bit subgroup",
        Tier::Quick,
        koblitz_signed_rho_k0_n41,
    );
    add(
        "dlp/aut_folded_rho_j0_p25",
        "aut_folded_rho_dlp (6-fold Floyd rho, BigInt) on a prime-order j=0 curve over a 25-bit prime",
        Tier::Quick,
        aut_folded_rho_j0_p25,
    );
    add(
        "dlp/gaudry_schost_negation_demo32",
        "ecdlp_variants::gaudry_schost_negation on the 32-bit demo-32 curve, dp_bits 8, 32 jumps",
        Tier::Quick,
        gaudry_schost_negation_demo32,
    );
    add(
        "dlp/collab_walkers_demo32_x8",
        "pollard_collab::run_walker for 8 walkers of a demo-32 job, negation map, dp_bits 10",
        Tier::Quick,
        collab_walkers_demo32_x8,
    );
}
