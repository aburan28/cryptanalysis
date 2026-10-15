#!/usr/bin/env python3
"""Derive the scan-order online producer from B's patched producer, exactly.

Input: `snapshots/r770/examples/koblitz_orbit_dlp_fast_online_logcache.rs`
(crypto 770f6a69 `koblitz_orbit_dlp_fast_online.rs` plus B's
`ic_log_cache.patch`, restored and digest-checked by `restore.py`).
Output: `snapshots/r770/examples/koblitz_orbit_dlp_fast_online_scanorder.rs`.

Every edit is an exact, counted string replacement inside the wide (`u128`)
module, so the derivation fails rather than drifts if the input changes.
The edits add one thing: a compile-time state-order selector `O` on the
target scan (`extract128_timed`, `extract128`), chosen once per process by
`KIC_SCAN_ORDER`:

* `left_major` (default, and the rank stage always): the pipeline's own
  order. The scan starts at state `start mod S` and walks the state vector,
  which `build_index128` fills left-orbit-major (left, right, relative), to
  the end and wraps. Bit-identical behaviour to B's producer.
* `feistel`: the same S states, each exactly once, in the order of a keyed
  four-round balanced Feistel bijection on `[0, 2^(2h))` (`2^(2h) >= S`),
  restricted to `[0, S)` by skipping out-of-range images. The key is the
  same public-point hash that B's producer uses as `start`. The order is
  computed inside the timed interval, one evaluation per visited index.

With `KIC_SCAN_START_OVERRIDE=<state index>` (left-major only) the start
state is that index instead of the hash. This is the planted positive
control: started inside B's own hit-free stretch, the scan must reach B's
relation after exactly the predicted number of probes.

Nothing else changes. The per-state scan (`scan_state128`: shift outer,
stored root inner, the full 83-rotation canonicalizer `NormalBasis128::canonical`
on every partner root), the index, the lift and relation check, the five
phase timers and the online interval are B's. Setup also runs a bijection
self-test of the Feistel order on the real S (two keys) before
`setup_complete`, in every arm. `--check` regenerates and requires byte
identity with the existing output.
"""

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / "snapshots" / "r770" / "examples"
SOURCE = EXAMPLES / "koblitz_orbit_dlp_fast_online_logcache.rs"
OUTPUT = EXAMPLES / "koblitz_orbit_dlp_fast_online_scanorder.rs"
WIDE_START = "mod wide {\n"
WIDE_END = "\nfn main() -> ExitCode {\n"

ORDER_CODE = """    use std::time::Instant;

    // koblitz-n83-scanorder-20261015: target-scan state order selector
    // (KIC_SCAN_ORDER), a const generic of the target scan so every arm is
    // its own monomorphized loop.
    const ORDER_LEFT_MAJOR: u8 = 0;
    const ORDER_FEISTEL: u8 = 1;

    fn scan_order_from_env() -> (u8, &'static str) {
        match std::env::var("KIC_SCAN_ORDER").as_deref() {
            Err(_) | Ok("") | Ok("left_major") => (ORDER_LEFT_MAJOR, "left_major"),
            Ok("feistel") => (ORDER_FEISTEL, "feistel"),
            Ok(other) => panic!("unknown KIC_SCAN_ORDER {other}"),
        }
    }

    fn scan_start_override_from_env() -> Option<usize> {
        match std::env::var("KIC_SCAN_START_OVERRIDE").as_deref() {
            Err(_) | Ok("") => None,
            Ok(value) => Some(value.parse().expect("KIC_SCAN_START_OVERRIDE must be a state index")),
        }
    }

    /// Keyed bijection on `[0, 2^(2·half))`: a balanced four-round Feistel
    /// network with a keyed multiply-shift round function. Any round
    /// function gives a bijection; restricting the images to `[0, len)` by
    /// skipping the others visits every state index exactly once.
    struct ScanPermutation {
        half: u32,
        mask: u64,
        keys: [u64; 4],
        domain: u64,
    }

    impl ScanPermutation {
        fn new(len: usize, key: u64) -> Self {
            let mut bits = 1u32;
            while (1u64 << bits) < len as u64 {
                bits += 1;
            }
            let half = (bits + 1) / 2;
            let mut state = key ^ 0x6A09_E667_F3BC_C908;
            let mut keys = [0u64; 4];
            for slot in keys.iter_mut() {
                // splitmix64
                state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
                let mut z = state;
                z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
                z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
                *slot = z ^ (z >> 31);
            }
            Self { half, mask: (1u64 << half) - 1, keys, domain: 1u64 << (2 * half) }
        }

        #[inline(always)]
        fn round(&self, value: u64, key: u64) -> u64 {
            ((value ^ key).wrapping_mul(0x9E37_79B9_7F4A_7C15) ^ key.rotate_left(29))
                .wrapping_mul(0xD6E8_FEB8_6659_FD93)
                >> (64 - self.half)
        }

        #[inline(always)]
        fn apply(&self, index: u64) -> u64 {
            let mut left = index >> self.half;
            let mut right = index & self.mask;
            for &key in &self.keys {
                let next = left ^ self.round(right, key);
                left = right;
                right = next & self.mask;
            }
            (left << self.half) | right
        }
    }

    /// Bijection check on the real state count: every index in `[0, len)`
    /// is produced exactly once and nothing else survives the range filter.
    fn scan_permutation_selftest(len: usize, key: u64) -> bool {
        let permutation = ScanPermutation::new(len, key);
        let mut seen = vec![0u64; len.div_ceil(64)];
        let mut visited = 0usize;
        for index in 0..permutation.domain {
            let image = permutation.apply(index);
            if image >= permutation.domain {
                return false;
            }
            if image < len as u64 {
                let (word, bit) = ((image / 64) as usize, image % 64);
                if seen[word] >> bit & 1 == 1 {
                    return false;
                }
                seen[word] |= 1 << bit;
                visited += 1;
            }
        }
        visited == len
    }

    #[cfg(test)]
    mod scan_order_tests {
        use super::*;

        #[test]
        fn feistel_order_is_a_bijection_on_every_small_length() {
            for len in 1..=2100usize {
                for key in [0u64, 1, 0xDEAD_BEEF, u64::MAX, len as u64 * 0x9E37] {
                    assert!(scan_permutation_selftest(len, key), "len {len} key {key}");
                }
            }
        }

        #[test]
        fn feistel_order_is_a_bijection_on_the_n83_k600_state_count() {
            // 600 * 600 * 83 regular states (the K600 receipts' regular_states).
            assert!(scan_permutation_selftest(29_880_000, 0x0123_4567_89AB_CDEF));
        }

        #[test]
        fn feistel_order_depends_on_the_key() {
            let a = ScanPermutation::new(29_880_000, 1);
            let b = ScanPermutation::new(29_880_000, 2);
            let differ = (0..1000u64).filter(|&i| a.apply(i) != b.apply(i)).count();
            assert!(differ > 990);
        }
    }
"""

EXTRACT_OLD = """    fn extract128_timed(
        gf: &Gf2_128,
        fast: &FastBinaryCurve128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        index: &Index128,
        base: &Base128,
        target: FastPoint128,
        start: usize,
        clock: &mut PhaseClock,
        split: &mut ExtractSplit,
    ) -> Option<Relation128> {
        let (target_x, _) = target?;
        let mut probes = 0u64;
        let mut scan = StateScan128::new(gf.n);
        let start = start % index.states.len().max(1);
        for state in index.states[start..].iter().chain(&index.states[..start]) {
            if let Some(relation) = scan_state128(
                gf,
                fast,
                basis,
                solver,
                index,
                base,
                target,
                target_x,
                state,
                &mut scan,
                &mut probes,
                clock,
                split,
            ) {
                return Some(relation);
            }
        }
        None
    }
"""

EXTRACT_NEW = """    fn extract128_timed<const O: u8>(
        gf: &Gf2_128,
        fast: &FastBinaryCurve128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        index: &Index128,
        base: &Base128,
        target: FastPoint128,
        start: usize,
        clock: &mut PhaseClock,
        split: &mut ExtractSplit,
    ) -> Option<Relation128> {
        let (target_x, _) = target?;
        let mut probes = 0u64;
        let mut scan = StateScan128::new(gf.n);
        if O == ORDER_FEISTEL {
            // Same states, each once, in a keyed pseudo-random order; the
            // key is the public-point hash B's producer uses as `start`.
            let len = index.states.len();
            let permutation = ScanPermutation::new(len, start as u64);
            for position in 0..permutation.domain {
                let state_index = permutation.apply(position);
                if state_index >= len as u64 {
                    continue;
                }
                if let Some(relation) = scan_state128(
                    gf,
                    fast,
                    basis,
                    solver,
                    index,
                    base,
                    target,
                    target_x,
                    &index.states[state_index as usize],
                    &mut scan,
                    &mut probes,
                    clock,
                    split,
                ) {
                    return Some(relation);
                }
            }
            return None;
        }
        let start = start % index.states.len().max(1);
        for state in index.states[start..].iter().chain(&index.states[..start]) {
            if let Some(relation) = scan_state128(
                gf,
                fast,
                basis,
                solver,
                index,
                base,
                target,
                target_x,
                state,
                &mut scan,
                &mut probes,
                clock,
                split,
            ) {
                return Some(relation);
            }
        }
        None
    }
"""


def replace(text, old, new, count=1):
    found = text.count(old)
    if found != count:
        raise ValueError("expected %d occurrence(s), found %d: %r" % (count, found, old[:80]))
    return text.replace(old, new)


def derive(text):
    head, rest = text.split(WIDE_START, 1)
    wide, tail = rest.split(WIDE_END, 1)
    head = replace(head, "#![recursion_limit = \"256\"]\n", """#![recursion_limit = "256"]

// koblitz-n83-scanorder-20261015: derived from the log-cache producer by
// make_online_source.py; adds the KIC_SCAN_ORDER target-scan state order.
""")
    wide = replace(wide, "    use std::time::Instant;\n", ORDER_CODE)
    wide = replace(wide, EXTRACT_OLD, EXTRACT_NEW)
    wide = replace(wide, "    fn extract128(\n", "    fn extract128<const O: u8>(\n")
    wide = replace(wide, "        let relation = extract128_timed(\n", "        let relation = extract128_timed::<O>(\n")
    # Rank stage: always the pipeline's own order.
    wide = replace(wide, """            let relation = extract128(
                &gf,
                &fast,
                &basis,
                &solver,
                &index,
                &base,
                point,""", """            let relation = extract128::<ORDER_LEFT_MAJOR>(
                &gf,
                &fast,
                &basis,
                &solver,
                &index,
                &base,
                point,""")
    # Setup: read the selectors and self-test the bijection before setup ends.
    wide = replace(wide, "        let setup_complete_elapsed = process_started.elapsed();\n", """        let (scan_order, scan_order_name) = scan_order_from_env();
        let scan_start_override = scan_start_override_from_env();
        assert!(
            scan_start_override.is_none() || scan_order == ORDER_LEFT_MAJOR,
            "KIC_SCAN_START_OVERRIDE is a left-major planted control"
        );
        let scan_selftest_started = Instant::now();
        let scan_selftest_keys = [0x0123_4567_89AB_CDEFu64, 0xFEDC_BA98_7654_3210u64];
        let scan_selftest_ok = scan_selftest_keys
            .iter()
            .all(|&key| scan_permutation_selftest(index.states.len(), key));
        assert!(scan_selftest_ok, "feistel scan order is not a bijection on the state vector");
        let scan_selftest_ms = ms(scan_selftest_started.elapsed());
        let setup_complete_elapsed = process_started.elapsed();
""")
    wide = replace(wide, """            let start = query_hash as usize;
            let query_phase = clock.lap();
            let mut split = ExtractSplit::default();
            let relation = extract128(
                &gf,
                &fast,
                &basis,
                &solver,
                &index,
                &base,
                target,
                start,
                &mut clock,
                &mut split,
            );""", """            let start = scan_start_override.unwrap_or(query_hash as usize);
            let query_phase = clock.lap();
            let mut split = ExtractSplit::default();
            let relation = if scan_order == ORDER_FEISTEL {
                extract128::<ORDER_FEISTEL>(
                    &gf, &fast, &basis, &solver, &index, &base, target, start, &mut clock,
                    &mut split,
                )
            } else {
                extract128::<ORDER_LEFT_MAJOR>(
                    &gf, &fast, &basis, &solver, &index, &base, target, start, &mut clock,
                    &mut split,
                )
            };""")
    wide = replace(wide, """                "target_ms":elapsed,
            });""", """                "target_ms":elapsed,
                "scan_order":scan_order_name,
                "scan_start_override":scan_start_override,
                "scan_start_or_key":start as u64,
            });""")
    wide = replace(wide, """            "sparse_canonical_enabled":basis.sparse_canonical,
""", """            "sparse_canonical_enabled":basis.sparse_canonical,
            "scan_order":scan_order_name,
            "scan_start_override":scan_start_override,
            "scan_order_selftest":{"states":index.states.len(), "keys":scan_selftest_keys.len(),
                                   "bijection":scan_selftest_ok, "ms":scan_selftest_ms,
                                   "accounting":"setup (setup_input_control), before setup_complete"},
""")
    return head + WIDE_START + wide + WIDE_END + tail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = derive(SOURCE.read_text())
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("derived online source differs from " + str(OUTPUT))
    else:
        OUTPUT.write_text(text)
    print("online_source_sha256=" + hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
