//! **Why a blocked probe beats a fused one: the key's length, tested.**
//!
//! `RESEARCH_KOBLITZ_INDEX_CALCULUS.md` reports that blocking the
//! folded table's probe buys 1.83x where it buys a compact table 1.35x,
//! and leaves the mechanism open between three candidates.  Two of
//! those can be settled without a profiler.
//!
//! The rotation's `x < best` compiles to `cmovb` — disassemble
//! `canon_key_with` and look — so there is no data-dependent branch to
//! mispredict.  What is left is capacity: each rotation step is
//! `lea, shr, or, and, cmp, cmovb`, six uops, and at `n = 61` the key
//! is some 390 of them plus `coords`.  A Cascade Lake reorder buffer
//! holds 224.  If that is what stops consecutive probes overlapping,
//! then shortening the key must collapse the gap once the key fits —
//! around `k ≈ 17` rotations, where 6k crosses half the window — and
//! not before.  A pure-latency story predicts no knee at all, just a
//! gap that shrinks smoothly with `k`.
//!
//! So: canonicalise with `k` rotations instead of `n`.  The key is
//! wrong for `k < n`, which does not matter — it is still spread over
//! the same range, so the filter turns away the same fraction and the
//! memory traffic is the one being measured.
use std::time::Instant;

use cryptanalysis_suite::cryptanalysis::koblitz_fast::{FastCurve, FrobeniusCanon};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;

fn main() {
    let degree: u32 = 61;
    let points: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(183_488);
    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let fb = build_subgroup_orbit_factor_base(&kc, 1, points).expect("base");
    let pf = fb.points.len();
    let bytes = PairSumTable::folded_byte_size(fb.signed_orbits.len(), pf, degree);
    let t0 = Instant::now();
    let table = PairSumTable::build_within(&kc, &fb, bytes).expect("folded");
    assert!(table.is_folded());
    println!(
        "folded |F| = {pf} ({:.2} GiB, {} pairs) built in {:.1} s",
        bytes as f64 / (1u128 << 30) as f64,
        table.len(),
        t0.elapsed().as_secs_f64()
    );

    let fc = FastCurve::new(&kc.curve).expect("fast curve");
    let g = fc.lift(kc.generator());
    let canon = FrobeniusCanon::new(&fc.field, fc.n).expect("normal element");
    let n = degree;
    let mask = (1u64 << n) - 1;
    // `FrobeniusCanon::canon` with the rotation count cut to `k`.
    let key_k = |x: u64, k: u32| -> u64 {
        let c = canon.coords(x);
        let (mut best, mut v) = (c, c);
        for _ in 1..k {
            v = ((v << 1) | (v >> (n - 1))) & mask;
            if v < best {
                best = v;
            }
        }
        best + 1
    };

    let sa: Vec<_> = (1u64..=200_000)
        .map(|t| fc.mul_u64(g, t * 1_000_003 + 5))
        .collect();
    let sb: Vec<_> = (1u64..=200_000)
        .map(|t| fc.mul_u64(g, t * 1_000_003 + 500_000_009))
        .collect();
    let mut keys: Vec<u64> = Vec::with_capacity(1024);

    println!();
    println!("  k   uops/key   fused   blocked    gap   fused-blk   key alone");
    for k in [2u32, 4, 6, 8, 10, 12, 14, 16, 20, 32, 61] {
        // Both loops on both streams, averaged, so a difference between
        // the streams cannot be read as a difference between the loops.
        let (mut fused, mut blocked, mut keyonly) = (0.0, 0.0, 0.0);
        for st in [&sa, &sb] {
            let t0 = Instant::now();
            let mut h = 0usize;
            for &q in st {
                if table.contains_key(key_k(q.x, k)) {
                    h += 1;
                }
            }
            fused += t0.elapsed().as_secs_f64() * 1e9 / st.len() as f64 / 2.0;

            let t0 = Instant::now();
            let mut h2 = 0usize;
            for part in st.chunks(1024) {
                keys.clear();
                keys.extend(part.iter().map(|q| key_k(q.x, k)));
                for &key in &keys {
                    if table.contains_key(key) {
                        h2 += 1;
                    }
                }
            }
            blocked += t0.elapsed().as_secs_f64() * 1e9 / st.len() as f64 / 2.0;
            assert_eq!(h, h2, "the two loops disagreed at k = {k}");

            let t0 = Instant::now();
            for &q in st {
                std::hint::black_box(key_k(q.x, k));
            }
            keyonly += t0.elapsed().as_secs_f64() * 1e9 / st.len() as f64 / 2.0;
        }
        println!(
            "{k:4}   {:8}  {fused:6.1}  {blocked:7.1}  {:5.2}x  {:6.1}   {keyonly:6.1} ns",
            6 * (k - 1) + 40,
            fused / blocked,
            fused - blocked
        );
    }
}
