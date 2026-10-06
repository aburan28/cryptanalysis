//! The conversion factor a tier ladder needs to be priced in one unit.
//!
//! AGENTS.md §2 asks for one unit, and §6 rules out wall-clock as the
//! headline.  The pair-table thread has been reporting seconds, which
//! makes its tiers incomparable with everything else on the scoreboard:
//! the ledger's unit is `S = group-addition equivalents / sqrt(r)`, and
//! a pair-table probe is not a group addition.
//!
//! So measure the conversion, on this host, in this process, on the
//! base the ladder actually runs: how many group additions a single
//! table probe costs, per tier.  Everything else in the pipeline is
//! already counted natively — the build does one addition per stored
//! pair, rho does one per step — so this one factor is what stands
//! between the tier ladder and the ledger's axis.
//!
//! The factor is per tier on purpose.  A probe is a hash and a short
//! scan either way; what differs is whether the table it reads is in
//! cache, and at 12,688 points the folded table is 16 MiB against the
//! full table's 1,592.  That difference is a property of this host and
//! is recorded as such, not smuggled into an operation count.
//!
//!     cargo run --release --example koblitz_probe_conversion -- 61 12000

use cryptanalysis_suite::cryptanalysis::koblitz_fast::{BatchScratch, FastCurve, FastPoint};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use std::time::Instant;

/// Enough probes that the timer's resolution is not the measurement.
const PROBES: usize = 200_000;
/// Group additions timed against the same clock.
const ADDS: usize = 2_000_000;
/// `BLOCK` in `witnesses_fast_inner`: the block the descent really uses.
const BLOCK: usize = 1024;

fn main() {
    let degree: u32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(61);
    let points: usize = std::env::args()
        .nth(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(12000);
    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let fb = build_subgroup_orbit_factor_base(&kc, 1, points).expect("factor base");
    let fc = FastCurve::new(&kc.curve).expect("fast curve");
    let n = fb.points.len();
    let orbits = fb.signed_orbits.len();
    let r = kc.subgroup_order.to_u64_digits()[0];

    // The unit: one affine group addition on this curve, on this host.
    // Measured twice, because the pipeline performs both kinds.
    //
    // A *chained* addition pays its own field inversion; a *batched*
    // one shares a single inversion across the slice by Montgomery's
    // trick, which is what the rho walk does across its parallel walks
    // and what the pair-table build does down a row.  The batched
    // addition is therefore the honest unit here: it is the cheaper of
    // the two, so quoting probes in batched additions charges the
    // probe the most, which is the direction an accounting correction
    // should err in.
    let g = fc.lift(kc.generator());
    let mut acc = fc.lift(&fb.points[0]);
    let t = Instant::now();
    for _ in 0..ADDS {
        acc = fc.add(acc, g);
    }
    let chained_ns = t.elapsed().as_secs_f64() * 1e9 / ADDS as f64;
    std::hint::black_box(acc);

    let batch: Vec<FastPoint> = (0..1024).map(|i| fc.lift(&fb.points[i % n])).collect();
    let mut scratch = BatchScratch::default();
    let mut out: Vec<FastPoint> = Vec::with_capacity(batch.len());
    let rounds = ADDS / batch.len();
    let t = Instant::now();
    for _ in 0..rounds {
        out.clear();
        fc.add_many(g, &batch, &mut out, &mut scratch);
    }
    let add_ns = t.elapsed().as_secs_f64() * 1e9 / (rounds * batch.len()) as f64;
    std::hint::black_box(out.len());

    println!(
        "base {n} points, {orbits} signed orbits, degree {degree}, r = 2^{:.1}",
        (r as f64).log2()
    );
    println!("one group addition, chained (own inversion):  {chained_ns:.2} ns");
    println!("one group addition, batched (shared inverse): {add_ns:.2} ns   <- the unit");

    // The same probes against each representation of the same base, so
    // the only thing that differs between the rows is the table.
    let mut rng: u64 = 0x9e37_79b9_7f4a_7c15;
    let mut targets: Vec<FastPoint> = Vec::with_capacity(PROBES);
    for _ in 0..PROBES {
        rng = rng
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        targets.push(fc.mul_u64(g, 1 + rng % (r - 1)));
    }

    let tiers: [(&str, Option<PairSumTable>); 3] = [
        (
            "folded",
            PairSumTable::build_folded_within(&kc, &fb, PairSumTable::DEFAULT_BYTE_BUDGET),
        ),
        (
            "compact",
            PairSumTable::build_compact_within(&kc, &fb, PairSumTable::DEFAULT_BYTE_BUDGET),
        ),
        (
            "full",
            PairSumTable::build_full_within(&kc, &fb, PairSumTable::DEFAULT_BYTE_BUDGET),
        ),
    ];
    println!(
        "\n{:<8} {:>14} {:>12} {:>10} {:>10} {:>10} {:>10} {:>9} {:>9} {:>9} {:>9}",
        "tier",
        "stored pairs",
        "build s",
        "lone ns",
        "blkd ns",
        "scan ns",
        "aim ns",
        "lone/add",
        "blkd/add",
        "scan/add",
        "aim/add"
    );
    for (name, table) in tiers {
        let Some(table) = table else {
            println!("{name:<8} {:>14}", "did not fit");
            continue;
        };
        // Rebuild under the clock: the build is a counted phase too, and
        // its native count is one addition per stored pair.
        let t = Instant::now();
        let rebuilt = match name {
            "folded" => {
                PairSumTable::build_folded_within(&kc, &fb, PairSumTable::DEFAULT_BYTE_BUDGET)
            }
            "compact" => {
                PairSumTable::build_compact_within(&kc, &fb, PairSumTable::DEFAULT_BYTE_BUDGET)
            }
            _ => PairSumTable::build_full_within(&kc, &fb, PairSumTable::DEFAULT_BYTE_BUDGET),
        }
        .expect("it fit a moment ago");
        let build_s = t.elapsed().as_secs_f64();
        drop(rebuilt);

        // Shape 1: one target at a time.  Not what the pipeline does;
        // measured because it is what earlier notes quoted.
        let t = Instant::now();
        let mut hits = 0usize;
        for &target in &targets {
            if table.contains_pair(target) {
                hits += 1;
            }
        }
        let lone_ns = t.elapsed().as_secs_f64() * 1e9 / PROBES as f64;
        std::hint::black_box(hits);

        // Shape 2: the descent's own loop — keys computed a block at a
        // time with a 32-key prefetch running ahead of the probe, which
        // is what `witnesses_fast_inner` does at `BLOCK = 1024`.  This
        // is the shape the `m = 2` descent probes in, so it is the
        // conversion for `descent_trials_total`.
        let mut keybuf: Vec<u64> = Vec::with_capacity(BLOCK);
        let t = Instant::now();
        let mut blocked_hits = 0usize;
        for part in targets.chunks(BLOCK) {
            keybuf.clear();
            keybuf.extend(part.iter().map(|&q| table.probe_key(q)));
            for &k in keybuf.iter().take(32) {
                table.prefetch_key(k);
            }
            for w in 0..keybuf.len() {
                if let Some(&ahead) = keybuf.get(w + 32) {
                    table.prefetch_key(ahead);
                }
                if table.contains_key(keybuf[w]) {
                    blocked_hits += 1;
                }
            }
        }
        let blocked_ns = t.elapsed().as_secs_f64() * 1e9 / PROBES as f64;
        assert_eq!(
            blocked_hits, hits,
            "{name}: the blocked probe answered differently"
        );

        // Shape 3: the `m = 3` scan, with a sink that never stops so the
        // whole window is walked and the figure is a true per-base-point
        // cost.  This is the unit `summands_scanned_total` counts, and
        // collection spends 351,750,000 of them against the descent's
        // 51,328,107 — so this, not either shape above, is the
        // conversion that decides the ledger.
        let mut scanned = 0usize;
        let mut scan_targets = 0usize;
        let start = Instant::now();
        while start.elapsed().as_secs_f64() < 3.0 {
            scan_targets += 1;
            let t = fc.mul_u64(g, scan_targets as u64 * 7_700_017 + 3);
            table.witnesses_fast(t, 3, &mut |_| true);
            scanned += n;
        }
        let scan_ns = start.elapsed().as_secs_f64() * 1e9 / scanned as f64;

        // Shape 4: the same scan aimed at a named subset rather than
        // swept over the base.  It costs a gather — one `FastPoint` copy
        // per summand, because a column's points are not contiguous in
        // the base ordering — and that copy must be inside this figure,
        // not assumed away: aiming is only a saving if the scan it makes
        // is no dearer per summand than the sweep it replaces.
        //
        // The subset is a tenth of the base, which is the order of what
        // aiming actually scans once coverage is nearly complete, and it
        // is deliberately stridden rather than contiguous so the gather
        // pays the scattered reads a real target set would.
        let aimed_idxs: Vec<u32> = (0..n as u32).filter(|i| i % 10 == 3).collect();
        let mut aim_scratch = ScanScratch::default();
        let mut aimed_scanned = 0usize;
        let mut aimed_targets = 0usize;
        let start = Instant::now();
        while start.elapsed().as_secs_f64() < 3.0 {
            aimed_targets += 1;
            let t = fc.mul_u64(g, aimed_targets as u64 * 7_700_017 + 3);
            table.witnesses_fast_scan(
                t,
                3,
                Scan::Indices(&aimed_idxs),
                &mut aim_scratch,
                &mut |_| true,
            );
            aimed_scanned += aimed_idxs.len();
        }
        let aimed_ns = start.elapsed().as_secs_f64() * 1e9 / aimed_scanned as f64;

        println!(
            "{name:<8} {:>14} {build_s:>12.2} {lone_ns:>10.1} {blocked_ns:>10.1} {scan_ns:>10.1} {aimed_ns:>10.1}       {:>9.2} {:>9.2} {:>9.2} {:>9.2}",
            table.len(),
            lone_ns / add_ns,
            blocked_ns / add_ns,
            scan_ns / add_ns,
            aimed_ns / add_ns
        );
    }
    println!(
        "\nrecord both numbers with the run: the adds-per-probe factor is a\n\
         property of this host and this base, and a ledger that quotes S\n\
         without it has converted a foreign unit by assumption."
    );
}
