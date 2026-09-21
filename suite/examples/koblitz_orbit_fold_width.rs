//! **The base a memory budget affords, once the pair table is folded by
//! the signed Frobenius group.**
//!
//! Three representations of the same set of pair sums, each cheaper per
//! stored pair than the last and dearer per lookup:
//!
//! - the full table, sixteen bytes a pair, summands included;
//! - the compact table, about four and a half, summands recovered by one
//!   `|F|`-long scan on a hit;
//! - the folded table, the same four and a half but `2n` times fewer
//!   pairs, because the base is closed under `π` and negation and so the
//!   pair sums are too — paid for by canonicalising each looked-up
//!   point, which is `n − 1` squarings.
//!
//! Since the descent spends `2r/|F|²` probes, a table that stores `2n`
//! times fewer pairs affords a base `√(2n)` times wider and a descent
//! `2n` times shorter.  Whether that is a win is the ratio of `2n` to
//! what the canonicalisation adds to a probe, and both sides are
//! measured here rather than assumed.

use std::time::Instant;

use cryptanalysis_suite::cryptanalysis::koblitz_fast::{FastCurve, FastPoint};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use serde_json::json;

/// Largest `points` whose table fits the budget, by bisection.
fn widest<F: Fn(usize) -> u128>(size: F, budget: u128) -> usize {
    let (mut lo, mut hi) = (1usize, 1usize);
    while size(hi) <= budget && hi < 1 << 26 {
        lo = hi;
        hi *= 2;
    }
    while lo + 1 < hi {
        let mid = (lo + hi) / 2;
        if size(mid) <= budget {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    lo
}

fn main() {
    let degree: u32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(61);
    let budget_gib: u128 = std::env::args()
        .nth(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(4);
    let budget = budget_gib << 30;

    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let r = kc.subgroup_order.clone();
    let r_bits = r.bits();
    let r_f = r.to_string().parse::<f64>().unwrap();

    // A folded table's width depends on the orbit count as well as the
    // point count, and a subgroup-orbit base has one signed orbit per
    // `2n` points.  Measure that ratio on a real base rather than
    // assuming the orbits are all full length.
    let probe_fb = build_subgroup_orbit_factor_base(&kc, 1, 2000).expect("factor base");
    let per_orbit = probe_fb.points.len() as f64 / probe_fb.signed_orbits.len() as f64;
    println!(
        "n = {degree}, r = 2^{:.1}, base has {:.1} points per signed orbit (2n = {})",
        (r_bits as f64),
        per_orbit,
        2 * degree
    );

    let full = widest(PairSumTable::byte_size, budget);
    let compact = widest(|p| PairSumTable::compact_byte_size(p, degree), budget);
    let folded = widest(
        |p| {
            let orbits = ((p as f64 / per_orbit).ceil() as usize).max(1);
            PairSumTable::folded_byte_size(orbits, p, degree)
        },
        budget,
    );

    let probes = |p: usize| 2.0 * r_f / (p as f64 * p as f64);
    println!();
    println!("at {budget_gib} GiB:");
    for (name, width) in [("full", full), ("compact", compact), ("folded", folded)] {
        println!(
            "  {name:8} base {width:9}  descent probes 2r/|F|^2 = {:.3e}",
            probes(width)
        );
    }
    println!(
        "  fold widens the base {:.2}x and divides the probes by {:.1}",
        folded as f64 / compact as f64,
        probes(compact) / probes(folded)
    );

    // What a probe costs on each representation — at *equal memory*,
    // which is the only comparison the claim is about.  Measuring the
    // fold against a compact table small enough to sit in cache would
    // flatter the baseline and overstate what the canonicalisation
    // costs, so both tables here are built to about the same number of
    // bytes and both are served by DRAM.
    let compact_points: usize = std::env::args()
        .nth(3)
        .and_then(|s| s.parse().ok())
        .unwrap_or(16000);
    let fb_c = build_subgroup_orbit_factor_base(&kc, 1, compact_points).expect("compact base");
    // The folded base is chosen so its table costs the same BYTES as the
    // compact one, by bisecting the sizing law — not by scaling the point
    // count by a factor that is supposed to equal it.  A heuristic width
    // is how an earlier version of this measurement came to give the
    // folded table 1.8 times the memory while calling the comparison
    // equal.
    let budget_c = PairSumTable::compact_byte_size(fb_c.points.len(), degree);
    let folded_points = widest(
        |p| {
            let orbits = ((p as f64 / per_orbit).ceil() as usize).max(1);
            PairSumTable::folded_byte_size(orbits, p, degree)
        },
        budget_c,
    );
    let fb_f = build_subgroup_orbit_factor_base(&kc, 1, folded_points).expect("folded base");
    let (pc, pf) = (fb_c.points.len(), fb_f.points.len());
    let bytes_c = PairSumTable::compact_byte_size(pc, degree);
    let bytes_f = PairSumTable::folded_byte_size(fb_f.signed_orbits.len(), pf, degree);
    println!();
    println!(
        "equal-memory pair: compact |F| = {pc} ({:.2} GiB), folded |F| = {pf} ({:.2} GiB)",
        bytes_c as f64 / (1u128 << 30) as f64,
        bytes_f as f64 / (1u128 << 30) as f64
    );

    let t0 = Instant::now();
    let compact_t = PairSumTable::build_within(&kc, &fb_c, bytes_c).expect("compact");
    let compact_build = t0.elapsed().as_secs_f64();
    let t0 = Instant::now();
    let folded_t = PairSumTable::build_within(&kc, &fb_f, bytes_f).expect("folded");
    let folded_build = t0.elapsed().as_secs_f64();
    assert!(folded_t.is_folded() && !compact_t.is_folded());
    println!(
        "  stored pairs: compact {} in {compact_build:.1} s, folded {} in {folded_build:.1} s",
        compact_t.len(),
        folded_t.len()
    );

    let fc = FastCurve::new(&kc.curve).expect("fast curve");
    let g = fc.lift(kc.generator());
    let mut timing = Vec::new();
    for (name, table, width) in [("compact", &compact_t, pc), ("folded", &folded_t, pf)] {
        // Seconds per *decomposed* target, which is the quantity the
        // descent actually spends and the only one immune to the fact
        // that a scan stops at its first witness.  A per-probe figure
        // divided by an assumed probe count would flatter whichever
        // side short-circuits more often, and at these widths that is
        // the folded one nearly every time.
        let budget = 30.0f64;
        let start = Instant::now();
        let mut found = 0usize;
        let mut attempts = 0usize;
        for t in 1u64.. {
            let target = fc.mul_u64(g, t * 7 + 1);
            if target.infinity {
                continue;
            }
            attempts += 1;
            if table.decompose_fast(target, 3).is_some() {
                found += 1;
            }
            if start.elapsed().as_secs_f64() > budget && found > 0 {
                break;
            }
        }
        let secs = start.elapsed().as_secs_f64();
        let per_found = secs / found.max(1) as f64;
        let rate = found as f64 / attempts as f64;
        println!(
            "  {name:8} |F| = {width:6}: {found:4} of {attempts:6} targets in {secs:5.1} s              -> {per_found:8.4} s a decomposition (hit rate {rate:.3})"
        );
        timing.push((name.to_string(), per_found, found, attempts, rate));
    }
    // The probe and the recovery, measured apart.  A probe is the
    // question "is this a sum of two base points"; recovering which two
    // is an `|F|`-long scan paid only on a hit, and charging it to the
    // probes it sits among would misattribute most of the cost at a
    // base this wide.
    let mut probe_ns = Vec::new();
    let mut recover_ms = Vec::new();
    // A lone probe, a probe in a block, and the descent's own loop: the
    // three are far enough apart that which one a claim about "a probe"
    // means has to be said.
    let mut blocked_ns = Vec::new();
    let mut descent_ns_v = Vec::new();
    let mut chunk_sweep = Vec::new();
    for (name, table, width, base) in [
        ("compact", &compact_t, pc, &fb_c),
        ("folded", &folded_t, pf, &fb_f),
    ] {
        let stream: Vec<_> = (1u64..=200_000)
            .map(|t| fc.mul_u64(g, t * 1_000_003 + 5))
            .collect();
        let start = Instant::now();
        let mut hits = 0usize;
        for &q in &stream {
            if table.contains_pair(q) {
                hits += 1;
            }
        }
        let ns = start.elapsed().as_secs_f64() * 1e9 / stream.len() as f64;
        // Whether the canonicalisation and the lookup cost what they
        // cost *together*.  A probe canonicalises out of a 16 KiB table
        // and then reads one line out of a table three orders of
        // magnitude larger; alternating the two evicts the small one.
        // Doing them in chunks — canonicalise `c` targets, then look up
        // `c` keys — keeps the canon tables hot across a run and leaves
        // the lookups adjacent and independent.
        //
        // `c = 1` is the shipped probe with the buffer's overhead, so it
        // is the control, not the baseline.  The two streams are
        // disjoint: measuring a chunked probe on the keys the fused one
        // has just walked would credit chunking with the residency the
        // first pass paid for.
        let stream_b: Vec<_> = (1u64..=200_000)
            .map(|t| fc.mul_u64(g, t * 1_000_003 + 500_000_009))
            .collect();
        let mut keybuf: Vec<u64> = Vec::with_capacity(4096);
        let mut chunked = Vec::new();
        let fused_on = |st: &Vec<FastPoint>| {
            let t0 = Instant::now();
            let mut h = 0usize;
            for &q in st {
                if table.contains_pair(q) {
                    h += 1;
                }
            }
            (t0.elapsed().as_secs_f64() * 1e9 / st.len() as f64, h)
        };
        // Warm both streams into whatever residency 200 000 random
        // probes of a 0.64 GiB table leaves, so the first `c` measured
        // is not the only cold one.
        fused_on(&stream);
        fused_on(&stream_b);
        // 1024 is `BLOCK` in `witnesses_fast_inner`, so it is the one
        // the descent actually uses and the one the note quotes; the
        // rest of the sweep is there to show where the gain saturates.
        for c in [1usize, 4, 16, 64, 256, 1024, 4096] {
            // Each side is measured on both streams and averaged, so a
            // difference between the streams cannot be read as a
            // difference between the loops.
            let mut fused = 0.0;
            let mut batched = 0.0;
            let mut pref = 0.0;
            let mut hits_f = 0usize;
            let mut hits_b = 0usize;
            for st in [&stream, &stream_b] {
                let (ns, h) = fused_on(st);
                fused += ns / 2.0;
                hits_f += h;
                let t0 = Instant::now();
                let mut h2 = 0usize;
                for part in st.chunks(c) {
                    keybuf.clear();
                    for &q in part {
                        keybuf.push(table.probe_key(q));
                    }
                    for &k in &keybuf {
                        if table.contains_key(k) {
                            h2 += 1;
                        }
                    }
                }
                batched += t0.elapsed().as_secs_f64() * 1e9 / st.len() as f64 / 2.0;
                hits_b += h2;
                // The descent's own loop: the same blocking, plus the
                // 32-key prefetch it runs ahead of the probe.
                let t0 = Instant::now();
                let mut h3 = 0usize;
                for part in st.chunks(c) {
                    keybuf.clear();
                    for &q in part {
                        keybuf.push(table.probe_key(q));
                    }
                    for &k in keybuf.iter().take(32) {
                        table.prefetch_key(k);
                    }
                    for w in 0..keybuf.len() {
                        if let Some(&ahead) = keybuf.get(w + 32) {
                            table.prefetch_key(ahead);
                        }
                        if table.contains_key(keybuf[w]) {
                            h3 += 1;
                        }
                    }
                }
                pref += t0.elapsed().as_secs_f64() * 1e9 / st.len() as f64 / 2.0;
                assert_eq!(h3, h2, "the prefetching probe answered differently");
            }
            assert_eq!(hits_f, hits_b, "the chunked probe answered differently");
            println!(
                "  {name:8} chunk {c:5}: fused {fused:7.1}, chunked {batched:7.1}, \
                 +prefetch {pref:7.1} ns  ({:.2}x / {:.2}x)   [{hits_f} hits]",
                fused / batched,
                fused / pref
            );
            chunked.push(json!({
                "chunk": c, "fused_ns": fused,
                "chunked_ns": batched, "chunked_prefetch_ns": pref,
            }));
        }

        // And the descent's own loop, measured rather than read off
        // the source: `witnesses_fast` with `m = 3` and a sink that
        // never stops, so it walks the whole base and the figure is a
        // true per-base-point cost.  It carries the batched inversion
        // `add_many` does as well as the key and the lookup, which the
        // chunked figures above do not — the same for both tables, so
        // the folded-minus-compact difference is still the fold's.
        let mut scanned = 0usize;
        let start = Instant::now();
        let mut targets = 0usize;
        while start.elapsed().as_secs_f64() < 4.0 {
            targets += 1;
            let t = fc.mul_u64(g, targets as u64 * 7_700_017 + 3);
            table.witnesses_fast(t, 3, &mut |_| true);
            scanned += width;
        }
        let descent_ns = start.elapsed().as_secs_f64() * 1e9 / scanned as f64;
        println!(
            "  {name:8} descent loop (witnesses_fast m = 3, {targets} targets): \
             {descent_ns:7.1} ns a base point"
        );

        // Recovery, on targets known to be sums of two base points.
        let mut out = Vec::new();
        // Summands from far-apart orbits, and never a `±` pair: `P + (−P)`
        // is `O`, whose key every orbit representative stores, and timing
        // recovery on it would measure the one degenerate target rather
        // than the ordinary case.
        let stride = base.points.len() / 37;
        let known: Vec<_> = (0..24)
            .map(|i| {
                fc.add(
                    fc.lift(&base.points[(i * stride) % base.points.len()]),
                    fc.lift(&base.points[(i * stride + stride / 2 + 1) % base.points.len()]),
                )
            })
            .filter(|p| !p.infinity)
            .collect();
        let start = Instant::now();
        for &q in &known {
            table.pairs_for(q, &mut out);
        }
        let ms = start.elapsed().as_secs_f64() * 1e3 / known.len().max(1) as f64;
        // And the worst case the orbit tag has: `O` is the sum of every
        // `±` pair, so its key is stored once by every representative.
        let start = Instant::now();
        table.pairs_for(FastPoint::INFINITY, &mut out);
        let degenerate_ms = start.elapsed().as_secs_f64() * 1e3;
        let degenerate_pairs = out.len();
        println!(
            "  {name:8} probe {ns:7.1} ns ({hits} of {} hit), recovery {ms:7.3} ms; \
             the degenerate key O: {degenerate_ms:7.2} ms for {degenerate_pairs} pairs",
            stream.len()
        );
        probe_ns.push(ns);
        recover_ms.push(ms);
        descent_ns_v.push(descent_ns);
        // The descent's own block size, not the best of the sweep: a
        // figure quoted as "blocked 1024" has to be the one measured at
        // 1024.
        blocked_ns.push(
            chunked
                .iter()
                .find(|c| c["chunk"] == 1024)
                .expect("the sweep must measure BLOCK")["chunked_prefetch_ns"]
                .as_f64()
                .unwrap(),
        );
        chunk_sweep.push(json!({"table": name, "sweep": chunked}));
    }
    println!(
        "  the fold multiplies a probe by {:.2}x one at a time, {:.2}x in a block, \
         {:.2}x in the descent loop, and divides the probes per target by {:.1}x",
        probe_ns[1] / probe_ns[0],
        blocked_ns[1] / blocked_ns[0],
        descent_ns_v[1] / descent_ns_v[0],
        probes(pc) / probes(pf)
    );

    let net = timing[0].1 / timing[1].1;
    println!();
    println!(
        "at equal memory the fold decomposes a target {net:.1}x faster          ({:.4} s -> {:.4} s)",
        timing[0].1, timing[1].1
    );

    let report = json!({
        "degree": degree,
        "subgroup_bits": r_bits,
        "budget_gib": budget_gib,
        "points_per_signed_orbit": per_orbit,
        "widest_base": {"full": full, "compact": compact, "folded": folded},
        "descent_probes": {
            "full": probes(full), "compact": probes(compact), "folded": probes(folded),
        },
        "measured": {
            "compact_base": pc,
            "folded_base": pf,
            "compact_bytes": bytes_c.to_string(),
            "folded_bytes": bytes_f.to_string(),
            "compact_pairs": compact_t.len(),
            "folded_pairs": folded_t.len(),
            "stored_ratio": compact_t.len() as f64 / folded_t.len() as f64,
            "compact_build_secs": compact_build,
            "folded_build_secs": folded_build,
            "secs_per_decomposition_compact": timing[0].1,
            "secs_per_decomposition_folded": timing[1].1,
            "decomposed_compact": timing[0].2,
            "attempts_compact": timing[0].3,
            "hit_rate_compact": timing[0].4,
            "decomposed_folded": timing[1].2,
            "attempts_folded": timing[1].3,
            "hit_rate_folded": timing[1].4,
            "ns_per_probe_compact": probe_ns[0],
            "ns_per_probe_folded": probe_ns[1],
            "ns_per_probe_blocked_compact": blocked_ns[0],
            "ns_per_probe_blocked_folded": blocked_ns[1],
            "ns_per_base_point_descent_compact": descent_ns_v[0],
            "ns_per_base_point_descent_folded": descent_ns_v[1],
            "chunk_sweep": chunk_sweep,
            "recover_ms_compact": recover_ms[0],
            "recover_ms_folded": recover_ms[1],
            "probes_per_target_compact": probes(pc),
            "probes_per_target_folded": probes(pf),
            "net_speedup_at_equal_memory": net,
        },
    });
    println!();
    println!("{}", serde_json::to_string_pretty(&report).unwrap());
}
