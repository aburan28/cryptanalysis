#!/usr/bin/env python3
"""Derive the probe-path profiler (a diagnostic binary, never a timed arm).

Input: the two-level root-table producer written by `make_online_source.py`
(`koblitz_orbit_dlp_fast_online_tablefilter.rs`). Output:
`koblitz_orbit_dlp_fast_online_tableprofile.rs` (bin `ic_table_profile_r770`).

`claude/n83-probe-pipeline`'s `make_profile_source.py` @ ddbb86a9c with its
eight variants unchanged, plus root-table variants (koblitz-n83-tablefilter-20261015):
it also builds, from the base table's entries, the 16-byte compact table and
the blocked filter (`KIC_ROOT_FILTER_LOG2_BITS`, default 28) and times

* `filter_pipelined`: the new layout's in-situ loop (keys + filter-word
  prefetch, then the filter test with survivors' slot prefetch, then the
  survivors' compact lookups), cumulative over `roots_conv_canon`;
* `compact_pipelined`: keys + compact-slot prefetch, then compact lookups;
* lookup-only loops over the stored keys: `lookup_independent_compact`,
  `lookup_independent_filter`, and, in batches of one state's keys
  (prefetch all, then look up all), `lookup_prefetched_base`,
  `lookup_prefetched_compact`, `lookup_prefetched_filter`. If prefetching
  hides the filter's misses but not the 4 GiB table's, the table's cost is
  address translation (TLB reach and page walks), not cache misses alone.

One counted insertion adds `KIC_PROBE_PROFILE=<states>:<rounds>[:<variant>]`:
right after the index build (before the rank stage and the log table, so it
also runs on a small constructed base, `construct:83:1:<K>`), and instead of
everything after it, it takes the first target,
walks the first `<states>` index states of that target's Feistel order (the
combined producer's order and key), and times five cumulative variants of
the per-state probe work, all probes of every state, no lift and no early
exit, `<rounds>` times in rotated order:

* `roots`: the 2n candidate inputs and the batched S3 root solve;
* `roots_conv`: plus `to_normal` of every partner root;
* `roots_conv_canon`: plus `lift_scan` canonicalization;
* `inline_lookup`: plus the root-table lookup in the combined producer's
  interleaved order (key, lookup, next key);
* `pipelined_lookup`: the same keys, each followed by a prefetch of its
  home slot, then all lookups in the same order;

two lookup-only loops over the stored keys of those states:
`lookup_dependent` (each address depends on the previous lookup, so the
loads serialize: a latency bound) and `lookup_independent`; and
`cross_state_pipelined` (a state's lookups consumed only after the next
state's keys are computed and prefetched: a deeper pipeline, for comparison).

Differences of the cumulative variants are each component's marginal
ns/probe in situ. With `<variant>` (0-7) only that variant runs, so that an
instruction counter (callgrind, `--toggle-collect=*probe_profile*`) gives
its instructions per probe; instruction counts per probe do not depend on
the table size, which is why a small constructed base is enough for them. It prints one JSON object and exits. It is a diagnostic:
the instrument (Instant per variant pass) differs from the online clock,
and its numbers are never a speedup claim.
"""

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / "snapshots" / "r770" / "examples"
SOURCE = EXAMPLES / "koblitz_orbit_dlp_fast_online_tablefilter.rs"
OUTPUT = EXAMPLES / "koblitz_orbit_dlp_fast_online_tableprofile.rs"

sys.path.insert(0, str(HERE))
from make_combined_source import replace  # noqa: E402

HOOK_OLD = "        let index_elapsed = index_started.elapsed();\n"
HOOK_NEW = HOOK_OLD + """        if let Ok(spec) = std::env::var("KIC_PROBE_PROFILE") {
            let target = match target_inputs[0] {
                TargetInput128::PublicPoint(target) => target,
                TargetInput128::KnownAnswerScalar(scalar) => {
                    fast.scalar_mul(generator, &BigUint::from(scalar))
                }
            };
            probe_profile(&spec, &gf, &basis, &solver, &index, target);
            std::process::exit(0);
        }
"""

ANCHOR = "    /// `P` picks the target scan's probe loop at compile time.\n"
PROFILE_CODE = r'''    /// Diagnostic only (make_profile_source.py): cumulative per-component
    /// timings of the probe path over the first states of one target's
    /// Feistel order. Not part of any timed arm.
    fn probe_profile(
        spec: &str,
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        index: &Index128,
        target: FastPoint128,
    ) {
        let mut parts = spec.split(':');
        let states_wanted: usize = parts.next().unwrap().parse().expect("states");
        let rounds: usize = parts.next().unwrap_or("5").parse().expect("rounds");
        let only: Option<usize> = parts.next().map(|v| v.parse().expect("variant"));
        let (target_x, target_y) = target.expect("target is not infinity");
        let mut query_hash =
            target_x ^ target_y.rotate_left(29) ^ 0x9E37_79B9_7F4A_7C15_9E37_79B9_7F4A_7C15;
        query_hash = (query_hash ^ (query_hash >> 30))
            .wrapping_mul(0xBF58_476D_1CE4_E5B9_BF58_476D_1CE4_E5B9);
        query_hash = (query_hash ^ (query_hash >> 27))
            .wrapping_mul(0x94D0_49BB_1331_11EB_94D0_49BB_1331_11EB);
        query_hash ^= query_hash >> 31;
        let len = index.states.len();
        let permutation = ScanPermutation::new(len, query_hash as usize as u64);
        let mut order = Vec::with_capacity(states_wanted);
        let mut position = 0u64;
        while order.len() < states_wanted && position < permutation.domain {
            let state_index = permutation.apply(position);
            position += 1;
            if state_index < len as u64 {
                order.push(state_index as usize);
            }
        }
        let n = gf.n;
        let mut scan = StateScan128::new(n);
        let mut stored_keys: Vec<u128> = Vec::new();
        // Collect the keys once (also the probe count).
        for &state_index in &order {
            let state = &index.states[state_index];
            scan.inputs.clear();
            for shift in 0..n {
                for &normal_root in &state.normal_roots {
                    scan.inputs.push((basis.to_poly.apply(basis.rotate(normal_root, shift)), target_x));
                }
            }
            scan.batch.solve(gf, basis, solver, &scan.inputs);
            for result in &scan.batch.results {
                if let Some(partners) = *result {
                    for partner in partners {
                        stored_keys.push(target_canonical::<CANON_LIFT>(basis, basis.to_normal.apply(partner)).0);
                    }
                }
            }
        }
        let probes = stored_keys.len() as f64;
        let table_started = Instant::now();
        let mut compact = CompactRootTable128::with_capacity(index.states.len() * 2);
        let mut filter = RootFilter128::new(root_filter_log2_bits_from_env());
        for &(key, value) in &index.table.slots {
            if key != u128::MAX {
                compact.insert_if_absent(key, value);
                filter.insert(key);
            }
        }
        assert_eq!(compact.len, index.table.len);
        let table_build_ms = table_started.elapsed().as_secs_f64() * 1e3;
        let batch = 4 * n as usize;
        const NAMES: [&str; 15] = [
            "roots",
            "roots_conv",
            "roots_conv_canon",
            "inline_lookup",
            "pipelined_lookup",
            "lookup_dependent",
            "lookup_independent",
            "cross_state_pipelined",
            "filter_pipelined",
            "compact_pipelined",
            "lookup_independent_compact",
            "lookup_independent_filter",
            "lookup_prefetched_base",
            "lookup_prefetched_compact",
            "lookup_prefetched_filter",
        ];
        let mut samples: Vec<Vec<f64>> = vec![Vec::new(); NAMES.len()];
        let mut sink = 0u128;
        let mut hits = [0u64; NAMES.len()];
        let mut filter_survivors = 0u64;
        for round in 0..rounds {
            for offset in 0..NAMES.len() {
                let variant = (round + offset) % NAMES.len();
                if only.is_some_and(|wanted| wanted != variant) {
                    continue;
                }
                let started = Instant::now();
                let mut acc = 0u128;
                let mut found = 0u64;
                if variant >= 10 {
                    for chunk in stored_keys.chunks(batch) {
                        match variant {
                            10 => {
                                for &key in chunk {
                                    found += compact.get(key).is_some() as u64;
                                }
                            }
                            11 => {
                                for &key in chunk {
                                    found += filter.contains(key) as u64;
                                }
                            }
                            12 => {
                                for &key in chunk {
                                    prefetch_root_slot(&index.table, key);
                                }
                                for &key in chunk {
                                    found += index.table.get(key).is_some() as u64;
                                }
                            }
                            13 => {
                                for &key in chunk {
                                    compact.prefetch(key);
                                }
                                for &key in chunk {
                                    found += compact.get(key).is_some() as u64;
                                }
                            }
                            _ => {
                                for &key in chunk {
                                    filter.prefetch(key);
                                }
                                for &key in chunk {
                                    found += filter.contains(key) as u64;
                                }
                            }
                        }
                    }
                } else if variant == 8 || variant == 9 {
                    let mut survivors: Vec<usize> = Vec::with_capacity(batch);
                    for &state_index in &order {
                        let state = &index.states[state_index];
                        scan.inputs.clear();
                        for shift in 0..n {
                            for &normal_root in &state.normal_roots {
                                scan.inputs
                                    .push((basis.to_poly.apply(basis.rotate(normal_root, shift)), target_x));
                            }
                        }
                        scan.batch.solve(gf, basis, solver, &scan.inputs);
                        scan.keys.clear();
                        for result in &scan.batch.results {
                            let Some(partners) = *result else { continue };
                            for partner in partners {
                                let (canonical, partner_shift) =
                                    target_canonical::<CANON_LIFT>(basis, basis.to_normal.apply(partner));
                                if variant == 8 {
                                    filter.prefetch(canonical);
                                } else {
                                    compact.prefetch(canonical);
                                }
                                scan.keys.push(ProbeKey128 { canonical, partner, partner_shift, candidate: 0 });
                            }
                        }
                        survivors.clear();
                        for (position, key) in scan.keys.iter().enumerate() {
                            if variant == 9 || filter.contains(key.canonical) {
                                if variant == 8 {
                                    compact.prefetch(key.canonical);
                                }
                                survivors.push(position);
                            }
                        }
                        for &position in &survivors {
                            found += compact.get(scan.keys[position].canonical).is_some() as u64;
                        }
                        acc = acc.wrapping_add(survivors.len() as u128);
                    }
                } else if variant == 7 {
                    let mut previous: Vec<u128> = Vec::new();
                    for &state_index in &order {
                        let state = &index.states[state_index];
                        scan.inputs.clear();
                        for shift in 0..n {
                            for &normal_root in &state.normal_roots {
                                scan.inputs
                                    .push((basis.to_poly.apply(basis.rotate(normal_root, shift)), target_x));
                            }
                        }
                        scan.batch.solve(gf, basis, solver, &scan.inputs);
                        let mut current = Vec::with_capacity(4 * n as usize);
                        for result in &scan.batch.results {
                            let Some(partners) = *result else { continue };
                            for partner in partners {
                                let (canonical, _) =
                                    target_canonical::<CANON_LIFT>(basis, basis.to_normal.apply(partner));
                                prefetch_root_slot(&index.table, canonical);
                                current.push(canonical);
                            }
                        }
                        for &key in &previous {
                            found += index.table.get(key).is_some() as u64;
                        }
                        previous = current;
                    }
                    for &key in &previous {
                        found += index.table.get(key).is_some() as u64;
                    }
                } else if variant >= 5 {
                    let mut previous = 0u64;
                    for &key in &stored_keys {
                        let key = if variant == 5 { key ^ (previous as u128 & black_box(0u128)) } else { key };
                        let value = index.table.get(key);
                        previous = value.unwrap_or(1);
                        found += value.is_some() as u64;
                    }
                    acc ^= previous as u128;
                } else {
                    for &state_index in &order {
                        let state = &index.states[state_index];
                        scan.inputs.clear();
                        for shift in 0..n {
                            for &normal_root in &state.normal_roots {
                                scan.inputs
                                    .push((basis.to_poly.apply(basis.rotate(normal_root, shift)), target_x));
                            }
                        }
                        scan.batch.solve(gf, basis, solver, &scan.inputs);
                        if variant == 4 {
                            scan.keys.clear();
                        }
                        for result in &scan.batch.results {
                            let Some(partners) = *result else { continue };
                            for partner in partners {
                                if variant == 0 {
                                    // rotate-accumulate: an XOR of both partners would
                                    // cancel `first` and let the compiler drop work.
                                    acc = acc.rotate_left(7) ^ partner;
                                    continue;
                                }
                                let normal = basis.to_normal.apply(partner);
                                if variant == 1 {
                                    acc = acc.rotate_left(7) ^ normal;
                                    continue;
                                }
                                let (canonical, partner_shift) = target_canonical::<CANON_LIFT>(basis, normal);
                                if variant == 2 {
                                    acc = acc.rotate_left(7) ^ canonical ^ partner_shift as u128;
                                    continue;
                                }
                                if variant == 3 {
                                    found += index.table.get(canonical).is_some() as u64;
                                    continue;
                                }
                                prefetch_root_slot(&index.table, canonical);
                                scan.keys.push(ProbeKey128 { canonical, partner, partner_shift, candidate: 0 });
                            }
                        }
                        if variant == 4 {
                            for key in &scan.keys {
                                found += index.table.get(key.canonical).is_some() as u64;
                            }
                        }
                    }
                }
                let elapsed = started.elapsed().as_secs_f64() * 1e9;
                sink ^= black_box(acc);
                hits[variant] = found;
                if variant == 8 {
                    filter_survivors = acc as u64;
                }
                samples[variant].push(elapsed / probes);
            }
        }
        let mut report = serde_json::Map::new();
        for (variant, name) in NAMES.iter().enumerate() {
            if samples[variant].is_empty() {
                continue;
            }
            let mut values = samples[variant].clone();
            values.sort_by(|a, b| a.partial_cmp(b).unwrap());
            report.insert(
                name.to_string(),
                json!({"ns_per_probe_min": values[0], "ns_per_probe_median": values[values.len() / 2],
                       "ns_per_probe_all": samples[variant], "table_hits": hits[variant]}),
            );
        }
        println!(
            "{}",
            json!({"kind":"probe_path_profile_diagnostic", "states":order.len(), "probes":stored_keys.len(),
                   "rounds":rounds, "canonicalizer":"lift", "order":"feistel",
                   "root_tables":{"base_bytes":index.table.slots.len() * 32, "compact_bytes":compact.bytes(),
                                  "filter_bytes":filter.bytes(), "filter_log2_bits":filter.log2_bits,
                                  "filter_hashes":ROOT_FILTER_HASHES,
                                  "filter_ones_fraction":filter.ones_fraction(),
                                  "filter_survivors_per_round":filter_survivors,
                                  "compact_and_filter_build_ms":table_build_ms,
                                  "entries":index.table.len},
                   "variants":Value::Object(report), "sink_low_bit":(sink & 1) as u64,
                   "note":"diagnostic instrument; cumulative variants, differences are marginal in-situ costs; not a timed arm"})
        );
    }

'''


def derive(text):
    text = replace(text, HOOK_OLD, HOOK_NEW)
    text = replace(text, ANCHOR, PROFILE_CODE + ANCHOR)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = derive(SOURCE.read_text())
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("derived profiler source differs from " + str(OUTPUT))
    else:
        OUTPUT.write_text(text)
    print("profile_source_sha256=" + hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
