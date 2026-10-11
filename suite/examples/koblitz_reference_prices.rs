//! Ledger §19.1 (b) and (c): what a well-built rho step and the folded
//! table's build cost, in the Koblitz collection thread's unit.
//!
//! The thread counts one unit per rho step and one per stored pair of the
//! folded table.  Both do more than an addition: a step canonicalises its
//! point over the `2n` signed Frobenius conjugates, and a stored pair's
//! key is the normal-basis canonical form of the sum's abscissa.  This
//! measures, in one process, on one thread, in interleaved rounds so that
//! drift hits every quantity alike:
//!
//! - **the unit**, one batched affine addition (`add_many` over 1,024
//!   points), as `koblitz_phase_prices` measures it;
//! - **(b) a canonical walk's step**: one unit plus the table-driven
//!   canonicalisation the batch rho of §19 runs
//!   (`SignedFrobeniusClasses::canon`: normal-basis coordinates, the least
//!   rotation, `x` and `y` carried to it by `FrobeniusPowers`, the sign);
//! - **(b) Bailey et al.'s step**, `P ↦ P + φ^j(P)` with `j` read off the
//!   normal-basis weight of `x`: one unit plus the coordinates, a popcount
//!   and two table-applied Frobenius powers.  That walk never
//!   canonicalises, so its step is the cheapest a walk on the classes can
//!   take; its step *count* is not measured here;
//! - **(c) the folded table's build**, `build_folded_within` on a base of
//!   `points` points, per stored pair;
//! - two diagnostics that nothing in §19.1 declared: `add_pairwise` over
//!   1,024 independent pairs, the batched addition a parallel walk would
//!   actually run; and one affine addition with its own inversion, the
//!   unit of the boundary ledger's single-target rows (§18.8).
//!
//! Each quantity is divided by the unit measured in the same round, and
//! the report gives the median over rounds with the range.
//!
//!     cargo run --release --example koblitz_reference_prices -- 41 15744 > prices-n41.json
//!     cargo run --release --example koblitz_reference_prices -- 53 0 > prices-n53.json
use cryptanalysis_suite::cryptanalysis::ic_boundary::{
    koblitz_instance, BinaryGroup, CountedGroup, GroupOps, RhoClasses, SignedFrobeniusClasses,
};
use cryptanalysis_suite::cryptanalysis::koblitz_fast::{
    BatchScratch, FastPoint, FrobeniusCanon, FrobeniusPowers,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_subgroup_orbit_factor_base, PairSumTable,
};
use serde_json::json;
use std::hint::black_box;
use std::time::Instant;

const ADDS: usize = 2_000_000;
const CANONS: usize = 4_000_000;

fn median_range(v: &[f64]) -> serde_json::Value {
    let mut s = v.to_vec();
    s.sort_by(f64::total_cmp);
    json!({"median": s[s.len() / 2], "min": s[0], "max": s[s.len() - 1], "rounds": s})
}

fn main() {
    let arg = |i: usize| std::env::args().nth(i);
    let degree: u32 = arg(1).and_then(|s| s.parse().ok()).unwrap_or(41);
    let base_points: usize = arg(2).and_then(|s| s.parse().ok()).unwrap_or(0);
    let a: u8 = arg(3).and_then(|s| s.parse().ok()).unwrap_or(0);
    let rounds: usize = arg(4).and_then(|s| s.parse().ok()).unwrap_or(7);
    let inst = koblitz_instance(a, degree).expect("a usable Koblitz curve");
    let kc = inst.koblitz.as_ref().expect("a Koblitz curve");
    let fc = &inst.fast;
    let bg = BinaryGroup(fc);
    let classes = SignedFrobeniusClasses::new(&inst).expect("signed-Frobenius classes");
    let canon = FrobeniusCanon::new(&fc.field, degree).expect("a normal basis");
    let powers = FrobeniusPowers::new(&fc.field, degree);
    let mut ops = GroupOps::default();
    // Points of the subgroup, as a walk meets them.
    let pts: Vec<FastPoint> = (0..4096u64)
        .map(|i| {
            bg.mul(
                &mut ops,
                inst.generator,
                1 + i.wrapping_mul(0x9E37_79B9_7F4A_7C15) % (inst.r - 1),
            )
        })
        .collect();
    let g = pts[4095];
    let batch: Vec<FastPoint> = pts[..1024].to_vec();
    // Sixteen jumps, gathered per walk the way an r-adding walk would.
    let jumps: Vec<FastPoint> = pts[2048..2064].to_vec();
    let gathered: Vec<FastPoint> = batch.iter().map(|p| jumps[(p.x % 16) as usize]).collect();
    let fb = (base_points > 0)
        .then(|| build_subgroup_orbit_factor_base(kc, 1, base_points).expect("a factor base"));
    let one_thread = rayon::ThreadPoolBuilder::new()
        .num_threads(1)
        .build()
        .expect("a pool");

    let mut scratch = BatchScratch::default();
    let mut out: Vec<FastPoint> = Vec::with_capacity(1024);
    let (mut unit, mut canon_units, mut bailey_units, mut pairwise_units, mut build_units) =
        (Vec::new(), Vec::new(), Vec::new(), Vec::new(), Vec::new());
    let mut affine_units = Vec::new();
    let mut stored = 0usize;
    let mut sink = 0u64;
    for _ in 0..rounds {
        // The unit.
        let reps = ADDS / batch.len();
        let t = Instant::now();
        for _ in 0..reps {
            out.clear();
            fc.add_many(g, &batch, &mut out, &mut scratch);
        }
        let add_ns = t.elapsed().as_secs_f64() * 1e9 / (reps * batch.len()) as f64;
        sink ^= out[17].x;
        unit.push(add_ns);

        // (b) the canonical walk's canonicalisation.
        let t = Instant::now();
        for i in 0..CANONS {
            let (rep, mu) = classes.canon(&bg, pts[i & 4095]);
            sink ^= rep.x ^ rep.y ^ mu;
        }
        canon_units.push(t.elapsed().as_secs_f64() * 1e9 / CANONS as f64 / add_ns);

        // (b) Bailey's step overhead: the weight in the normal basis, the
        // power it selects, and φ^j(P).
        let t = Instant::now();
        for i in 0..CANONS {
            let p = pts[i & 4095];
            let j = 3 + (canon.coords(p.x).count_ones() / 2) % 8;
            sink ^= powers.apply(j, p.x) ^ powers.apply(j, p.y);
        }
        bailey_units.push(t.elapsed().as_secs_f64() * 1e9 / CANONS as f64 / add_ns);

        // Diagnostic: the batched addition of 1,024 independent walks.
        let t = Instant::now();
        for _ in 0..reps {
            out.clear();
            fc.add_pairwise(&batch, &gathered, &mut out, &mut scratch);
        }
        pairwise_units.push(t.elapsed().as_secs_f64() * 1e9 / (reps * batch.len()) as f64 / add_ns);
        sink ^= out[5].y;

        // Diagnostic: one affine addition, its own inversion included.
        let t = Instant::now();
        for i in 0..ADDS / 4 {
            let s = fc.add(batch[i & 1023], gathered[i & 1023]);
            sink ^= s.x;
        }
        affine_units.push(t.elapsed().as_secs_f64() * 1e9 / (ADDS / 4) as f64 / add_ns);

        // (c) the folded table's build, on one thread.
        if let Some(fb) = &fb {
            let t = Instant::now();
            let table = one_thread
                .install(|| {
                    PairSumTable::build_folded_within(kc, fb, PairSumTable::DEFAULT_BYTE_BUDGET)
                })
                .expect("a folded table within the default budget");
            let ns = t.elapsed().as_secs_f64() * 1e9;
            stored = table.len();
            build_units.push(ns / stored as f64 / add_ns);
            black_box(&table);
        }
    }
    black_box(sink);
    let canon_m = median_range(&canon_units)["median"]
        .as_f64()
        .unwrap_or(f64::NAN);
    let bailey_m = median_range(&bailey_units)["median"]
        .as_f64()
        .unwrap_or(f64::NAN);
    let report = json!({
        "what_this_is": "Ledger section 19.1 (b) and (c): the price of a rho step and of a folded-table stored pair, in the Koblitz collection thread's unit (one batched affine addition, add_many over 1,024 points), measured in one process on one thread in interleaved rounds; each quantity is divided by the unit of its own round.",
        "curve": inst.name, "a": a, "n": degree, "r": inst.r, "log2_r": (inst.r as f64).log2(),
        "rounds": rounds,
        "unit_ns": median_range(&unit),
        "b_canonical_canonicalisation_units": median_range(&canon_units),
        "b_canonical_step_units": 1.0 + canon_m,
        "b_bailey_overhead_units": median_range(&bailey_units),
        "b_bailey_step_units": 1.0 + bailey_m,
        "diagnostic_add_pairwise_units": median_range(&pairwise_units),
        "diagnostic_affine_add_units": median_range(&affine_units),
        "c_build": fb.as_ref().map(|fb| json!({
            "base_points": fb.points.len(),
            "signed_orbits": fb.signed_orbits.len(),
            "stored_pairs": stored,
            "units_per_stored_pair": median_range(&build_units),
            "what": "build_folded_within, whole call, single-threaded, over the stored pairs: two passes over every row (count, then fill), each a batched addition and a normal-basis canonical key per pair, plus the per-point work around them",
        })),
        "setup_group_operations_for_the_sample_points": ops.gae(),
    });
    println!("{}", serde_json::to_string_pretty(&report).expect("json"));
}
