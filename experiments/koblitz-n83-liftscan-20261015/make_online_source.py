#!/usr/bin/env python3
"""Derive the lift_scan online producer from B's patched producer, exactly.

Input: `snapshots/r770/examples/koblitz_orbit_dlp_fast_online_logcache.rs`
(crypto 770f6a69 `koblitz_orbit_dlp_fast_online.rs` plus B's
`ic_log_cache.patch`, restored and digest-checked by `restore.py`).
Output: `snapshots/r770/examples/koblitz_orbit_dlp_fast_online_liftscan.rs`.

Every edit is an exact, counted string replacement inside the wide (`u128`)
module, so the derivation fails rather than drifts if the input changes.
The edits add one thing: a compile-time canonicalizer selector `C` on the
target scan (`scan_state128`, `extract128_timed`, `extract128`) for the
partner-root canonicalization, chosen once per process by
`KIC_TARGET_CANON`:

* `full` (default, and the rank stage always): the pipeline's own
  `NormalBasis128::canonical`, the full 83-rotation scan. Bit-identical
  behaviour to B's producer.
* `gap`: `NormalBasis128::canonical_sparse`, the producer's own exact
  zero-gap selector (variant B), so far used only by the index build under
  `KIC_SPARSE_CANONICAL=1`.
* `lift`: the two-limb binary-lifting `lift_scan` (`lift2/src/lib.rs`).
* `full_x2`: planted positive control, the full scan plus one more,
  discarded (`black_box`), full scan of the same word.
* `verify`: returns the full scan and counts, per probe word, every
  disagreement of `gap` and `lift` with it; not a timing arm.

The relation search order, the index (built with `canonical_selected`, the
full scan unless `KIC_SPARSE_CANONICAL=1`), the five phase timers and the
online interval are unchanged. `--check` regenerates and requires byte
identity with the existing output.
"""

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / "snapshots" / "r770" / "examples"
SOURCE = EXAMPLES / "koblitz_orbit_dlp_fast_online_logcache.rs"
OUTPUT = EXAMPLES / "koblitz_orbit_dlp_fast_online_liftscan.rs"
WIDE_START = "mod wide {\n"
WIDE_END = "\nfn main() -> ExitCode {\n"


def replace(text, old, new, count=1):
    found = text.count(old)
    if found != count:
        raise ValueError("expected %d occurrence(s), found %d: %r" % (count, found, old[:80]))
    return text.replace(old, new)


def derive(text):
    head, rest = text.split(WIDE_START, 1)
    wide, tail = rest.split(WIDE_END, 1)
    head = replace(head, "#![recursion_limit = \"256\"]\n", """#![recursion_limit = "256"]

// koblitz-n83-liftscan-20261015: derived from the log-cache producer by
// make_online_source.py; adds the KIC_TARGET_CANON target canonicalizer.
#[path = "../../../lift2/src/lib.rs"]
#[allow(dead_code)]
mod lift2;
""")
    wide = replace(wide, "    use std::time::Instant;\n", """    use std::time::Instant;
    use std::hint::black_box;
    use std::sync::atomic::{AtomicU64, Ordering};

    // Target canonicalizer selector (KIC_TARGET_CANON), a const generic of
    // the target scan so every arm is its own monomorphized loop.
    const CANON_FULL: u8 = 0;
    const CANON_GAP: u8 = 1;
    const CANON_LIFT: u8 = 2;
    const CANON_FULL_X2: u8 = 3;
    const CANON_VERIFY: u8 = 4;
    static VERIFY_WORDS: AtomicU64 = AtomicU64::new(0);
    static VERIFY_GAP_MISMATCHES: AtomicU64 = AtomicU64::new(0);
    static VERIFY_LIFT_MISMATCHES: AtomicU64 = AtomicU64::new(0);

    fn target_canon_from_env() -> (u8, &'static str) {
        match std::env::var("KIC_TARGET_CANON").as_deref() {
            Err(_) | Ok("") | Ok("full") => (CANON_FULL, "full"),
            Ok("gap") => (CANON_GAP, "gap"),
            Ok("lift") => (CANON_LIFT, "lift"),
            Ok("full_x2") => (CANON_FULL_X2, "full_x2"),
            Ok("verify") => (CANON_VERIFY, "verify"),
            Ok(other) => panic!("unknown KIC_TARGET_CANON {other}"),
        }
    }

    /// Canonical rotation `(min_s rotl(v, s), least s)` of a partner root.
    #[inline(always)]
    fn target_canonical<const C: u8>(basis: &NormalBasis128, v: u128) -> (u128, u32) {
        match C {
            CANON_FULL => basis.canonical(v),
            CANON_GAP => basis.canonical_sparse(v),
            CANON_LIFT => super::lift2::lift_scan_wide(v, basis.n),
            CANON_FULL_X2 => {
                let result = basis.canonical(v);
                black_box(basis.canonical(black_box(v)));
                result
            }
            _ => {
                let result = basis.canonical(v);
                VERIFY_WORDS.fetch_add(1, Ordering::Relaxed);
                if basis.canonical_sparse(v) != result {
                    VERIFY_GAP_MISMATCHES.fetch_add(1, Ordering::Relaxed);
                }
                if super::lift2::lift_scan_wide(v, basis.n) != result {
                    VERIFY_LIFT_MISMATCHES.fetch_add(1, Ordering::Relaxed);
                }
                result
            }
        }
    }
""")
    wide = replace(wide, "    fn scan_state128(\n", "    fn scan_state128<const C: u8>(\n")
    wide = replace(wide, """                    let (canonical, partner_shift) =
                        basis.canonical(basis.to_normal.apply(partner));""",
                   """                    let (canonical, partner_shift) =
                        target_canonical::<C>(basis, basis.to_normal.apply(partner));""")
    wide = replace(wide, "    fn extract128_timed(\n", "    fn extract128_timed<const C: u8>(\n")
    wide = replace(wide, "            if let Some(relation) = scan_state128(\n",
                   "            if let Some(relation) = scan_state128::<C>(\n")
    wide = replace(wide, "    fn extract128(\n", "    fn extract128<const C: u8>(\n")
    wide = replace(wide, "        let relation = extract128_timed(\n", "        let relation = extract128_timed::<C>(\n")
    # Rank stage: always the pipeline's full scan.
    wide = replace(wide, """            let relation = extract128(
                &gf,
                &fast,
                &basis,
                &solver,
                &index,
                &base,
                point,""", """            let relation = extract128::<CANON_FULL>(
                &gf,
                &fast,
                &basis,
                &solver,
                &index,
                &base,
                point,""")
    wide = replace(wide, "        let mut single_target_phases = None;\n",
                   "        let mut single_target_phases = None;\n"
                   "        let (target_canon, target_canon_name) = target_canon_from_env();\n")
    wide = replace(wide, """            let mut split = ExtractSplit::default();
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
            );""", """            let mut split = ExtractSplit::default();
            VERIFY_WORDS.store(0, Ordering::Relaxed);
            VERIFY_GAP_MISMATCHES.store(0, Ordering::Relaxed);
            VERIFY_LIFT_MISMATCHES.store(0, Ordering::Relaxed);
            macro_rules! target_extract {
                ($c:expr) => {
                    extract128::<{ $c }>(
                        &gf, &fast, &basis, &solver, &index, &base, target, start,
                        &mut clock, &mut split,
                    )
                };
            }
            let relation = match target_canon {
                CANON_FULL => target_extract!(CANON_FULL),
                CANON_GAP => target_extract!(CANON_GAP),
                CANON_LIFT => target_extract!(CANON_LIFT),
                CANON_FULL_X2 => target_extract!(CANON_FULL_X2),
                _ => target_extract!(CANON_VERIFY),
            };""")
    wide = replace(wide, """                "target_ms":elapsed,
            });""", """                "target_ms":elapsed,
                "target_canonicalizer":target_canon_name,
                "target_canon_verification":if target_canon == CANON_VERIFY {
                    json!({"words":VERIFY_WORDS.load(Ordering::Relaxed),
                           "gap_mismatches_vs_full":VERIFY_GAP_MISMATCHES.load(Ordering::Relaxed),
                           "lift_mismatches_vs_full":VERIFY_LIFT_MISMATCHES.load(Ordering::Relaxed)})
                } else { Value::Null },
            });""")
    wide = replace(wide, """            "sparse_canonical_enabled":basis.sparse_canonical,
""", """            "sparse_canonical_enabled":basis.sparse_canonical,
            "target_canonicalizer":target_canon_name,
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
