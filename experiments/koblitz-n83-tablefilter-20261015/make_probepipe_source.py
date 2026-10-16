#!/usr/bin/env python3
"""Derive the probe-pipeline online producer from the combined producer, exactly.

Input: `snapshots/r770/examples/koblitz_orbit_dlp_fast_online_logcache.rs`
(crypto 770f6a69 plus B's `ic_log_cache.patch`, restored and digest-checked
by `restore.py`).

1. `make_combined_source.py` is `claude/n83-combined`'s
   `make_online_source.py` @ 88e1929fb, verbatim (its digest is pinned in
   `protocol.json`). Its `derive()` gives the combined (lift_scan x Feistel)
   producer text, whose SHA-256 must equal the combined protocol's frozen
   `online_source_sha256` (`COMBINED_SHA256` below), so step 2 starts from
   the exact measured text.
2. `pipeline_edits`: counted, exact string replacements inside the wide
   module add a third compile-time selector `P` on the target scan, chosen
   once per process by `KIC_PROBE_PIPELINE`:

   * `off` (default): `scan_state128`, unchanged, byte for byte. This is the
     combined producer's probe loop.
   * `prefetch`: `scan_state128_pipelined`. Same root batch. Then, in the
     same candidate order (shift outer, stored root inner, partner order of
     the root solver), it computes every partner's normal-basis word and
     canonical rotation, and issues a software prefetch of the key's home
     slot in the 4 GiB root table. Only then does it consume the keys in
     that same order, with the same probe counter, the same table lookup,
     the same lift / relation check and the same early return. The probe
     count, the relation and the published fields of every target are
     therefore identical to `off`'s. The only extra work is the keys of the
     probes that follow the successful one in the final state (at most
     `4n - 1` canonicalizations, untimed by the counter, timed by the clock).

The rank stage always runs `extract128::<CANON_FULL, ORDER_LEFT_MAJOR,
PIPE_OFF>`. Nothing else changes. `--check` regenerates and requires byte
identity with the existing output.
"""

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_combined_source as combined  # noqa: E402  (claude/n83-combined, verbatim)

EXAMPLES = HERE / "snapshots" / "r770" / "examples"
SOURCE = EXAMPLES / "koblitz_orbit_dlp_fast_online_logcache.rs"
OUTPUT = EXAMPLES / "koblitz_orbit_dlp_fast_online_probepipe.rs"
# protocol.json "sources.online_source_sha256" of claude/n83-combined @ 88e1929fb.
COMBINED_SHA256 = "f65e518a1644962f7b20dcc718d47a0620b43871cd083523e6f827a6d9f56a7e"
WIDE_START = combined.WIDE_START
WIDE_END = combined.WIDE_END
replace = combined.replace

HEAD_OLD = """// (Feistel, claude/n83-scan-order).
"""
HEAD_NEW = """// (Feistel, claude/n83-scan-order).
// koblitz-n83-probepipe-20261015: derived from the combined producer by
// make_online_source.py; adds the KIC_PROBE_PIPELINE target-scan selector
// (software-pipelined root-table probes with prefetch).
"""

SCRATCH_OLD = """    struct StateScan128 {
        inputs: Vec<(u128, u128)>,
        batch: RootBatch128,
    }

    impl StateScan128 {
        fn new(n: u32) -> Self {
            let entries = 2 * n as usize;
            Self {
                inputs: Vec::with_capacity(entries),
                batch: RootBatch128::with_capacity(entries),
            }
        }
    }
"""
SCRATCH_NEW = """    struct StateScan128 {
        inputs: Vec<(u128, u128)>,
        batch: RootBatch128,
        keys: Vec<ProbeKey128>,
    }

    impl StateScan128 {
        fn new(n: u32) -> Self {
            let entries = 2 * n as usize;
            Self {
                inputs: Vec::with_capacity(entries),
                batch: RootBatch128::with_capacity(entries),
                keys: Vec::with_capacity(2 * entries),
            }
        }
    }
"""

PIPE_ANCHOR = """    /// The wide search with the same candidate order as the frozen wide
    /// example; laps are taken only around `lift128`, so the probe loop
    /// carries no timer.
"""
PIPE_CODE = """    // koblitz-n83-probepipe-20261015: target-scan probe pipeline selector
    // (KIC_PROBE_PIPELINE), a const generic of the target scan so every arm
    // is its own monomorphized loop.
    const PIPE_OFF: u8 = 0;
    const PIPE_PREFETCH: u8 = 1;

    fn probe_pipeline_from_env() -> (u8, &'static str) {
        match std::env::var("KIC_PROBE_PIPELINE").as_deref() {
            Err(_) | Ok("") | Ok("off") => (PIPE_OFF, "off"),
            Ok("prefetch") => (PIPE_PREFETCH, "prefetch"),
            Ok(other) => panic!("unknown KIC_PROBE_PIPELINE {other}"),
        }
    }

    /// One partner probe of a state, computed ahead of its table lookup.
    #[derive(Clone, Copy)]
    struct ProbeKey128 {
        canonical: u128,
        partner: u128,
        partner_shift: u32,
        candidate: u32,
    }

    /// Hint the cache line of `key`'s home slot. A prefetch never faults and
    /// changes no architectural state; the lookup itself is unchanged.
    #[inline(always)]
    fn prefetch_root_slot(table: &RootTable128, key: u128) {
        #[cfg(target_arch = "x86_64")]
        {
            let slot = table.slot(key);
            debug_assert!(slot < table.slots.len());
            let address = table.slots.as_ptr().wrapping_add(slot) as *const i8;
            // SAFETY: `_mm_prefetch` is a hint; it does not dereference
            // `address` architecturally and cannot fault. SSE is part of
            // the x86_64 baseline.
            #[allow(unused_unsafe)]
            unsafe {
                std::arch::x86_64::_mm_prefetch(address, std::arch::x86_64::_MM_HINT_T0);
            }
        }
        #[cfg(not(target_arch = "x86_64"))]
        {
            let _ = (table, key);
        }
    }

    /// [`scan_state128`] with its probes software-pipelined: the same root
    /// batch; then every partner's canonical key in the same candidate order
    /// (shift outer, stored root inner, solver partner order), each followed
    /// by a prefetch of its home slot; then the lookups, lift and relation
    /// check in that same order with the same probe counter and the same
    /// early return. Probe count, relation and laps are those of
    /// `scan_state128`; memory latency overlaps the key computation.
    #[inline(always)]
    #[allow(clippy::too_many_arguments)]
    fn scan_state128_pipelined<const C: u8>(
        gf: &Gf2_128,
        fast: &FastBinaryCurve128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        index: &Index128,
        base: &Base128,
        target: FastPoint128,
        target_x: u128,
        state: &State128,
        scan: &mut StateScan128,
        probes: &mut u64,
        clock: &mut PhaseClock,
        split: &mut ExtractSplit,
    ) -> Option<Relation128> {
        let n = gf.n;
        scan.inputs.clear();
        for shift in 0..n {
            for &normal_root in &state.normal_roots {
                let absolute = basis.to_poly.apply(basis.rotate(normal_root, shift));
                scan.inputs.push((absolute, target_x));
            }
        }
        scan.batch.solve(gf, basis, solver, &scan.inputs);
        split.root_calls += scan.inputs.len() as u64;
        scan.keys.clear();
        for (candidate, result) in scan.batch.results.iter().enumerate() {
            let Some(partners) = *result else {
                continue;
            };
            for partner in partners {
                let (canonical, partner_shift) =
                    target_canonical::<C>(basis, basis.to_normal.apply(partner));
                prefetch_root_slot(&index.table, canonical);
                scan.keys.push(ProbeKey128 {
                    canonical,
                    partner,
                    partner_shift,
                    candidate: candidate as u32,
                });
            }
        }
        let roots_per_shift = state.normal_roots.len();
        for key in &scan.keys {
            *probes += 1;
            let Some(value) = index.table.get(key.canonical) else {
                continue;
            };
            let candidate = key.candidate as usize;
            let shift = candidate / roots_per_shift;
            let left_x = index.shifted[state.left as usize][shift];
            let right_x =
                index.shifted[state.right as usize][(shift + state.relative as usize) % n as usize];
            let absolute = scan.inputs[candidate].0;
            let partner = key.partner;
            let partner_shift = key.partner_shift;
            let (left2, right2, relative2, stored_shift) = unpack(value);
            let left_shift2 = ((stored_shift + n - partner_shift) % n) as usize;
            let right_shift2 = (left_shift2 + relative2) % n as usize;
            let codes = [
                left_x,
                right_x,
                index.shifted[left2][left_shift2],
                index.shifted[right2][right_shift2],
            ];
            split.pdp += clock.lap();
            let lifted = lift128(fast, base, &codes, target);
            split.relation_check += clock.lap();
            split.relation_checks += 1;
            if let Some(point_indices) = lifted {
                return Some(Relation128 {
                    point_indices,
                    x_codes: codes,
                    intermediates: [absolute, partner],
                    probes: *probes,
                });
            }
        }
        None
    }

    /// `P` picks the target scan's probe loop at compile time.
    #[inline(always)]
    #[allow(clippy::too_many_arguments)]
    fn scan_state128_select<const C: u8, const P: u8>(
        gf: &Gf2_128,
        fast: &FastBinaryCurve128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        index: &Index128,
        base: &Base128,
        target: FastPoint128,
        target_x: u128,
        state: &State128,
        scan: &mut StateScan128,
        probes: &mut u64,
        clock: &mut PhaseClock,
        split: &mut ExtractSplit,
    ) -> Option<Relation128> {
        if P == PIPE_PREFETCH {
            scan_state128_pipelined::<C>(
                gf, fast, basis, solver, index, base, target, target_x, state, scan, probes, clock,
                split,
            )
        } else {
            scan_state128::<C>(
                gf, fast, basis, solver, index, base, target, target_x, state, scan, probes, clock,
                split,
            )
        }
    }

"""

MACRO_OLD = """            macro_rules! target_extract {
                ($c:expr) => {
                    if scan_order == ORDER_FEISTEL {
                        extract128::<{ $c }, ORDER_FEISTEL>(
                            &gf, &fast, &basis, &solver, &index, &base, target, start,
                            &mut clock, &mut split,
                        )
                    } else {
                        extract128::<{ $c }, ORDER_LEFT_MAJOR>(
                            &gf, &fast, &basis, &solver, &index, &base, target, start,
                            &mut clock, &mut split,
                        )
                    }
                };
            }
"""
MACRO_NEW = """            macro_rules! target_extract_pipe {
                ($c:expr, $o:expr) => {
                    if probe_pipeline == PIPE_PREFETCH {
                        extract128::<{ $c }, { $o }, PIPE_PREFETCH>(
                            &gf, &fast, &basis, &solver, &index, &base, target, start,
                            &mut clock, &mut split,
                        )
                    } else {
                        extract128::<{ $c }, { $o }, PIPE_OFF>(
                            &gf, &fast, &basis, &solver, &index, &base, target, start,
                            &mut clock, &mut split,
                        )
                    }
                };
            }
            macro_rules! target_extract {
                ($c:expr) => {
                    if scan_order == ORDER_FEISTEL {
                        target_extract_pipe!($c, ORDER_FEISTEL)
                    } else {
                        target_extract_pipe!($c, ORDER_LEFT_MAJOR)
                    }
                };
            }
"""


def pipeline_edits(head, wide):
    head = replace(head, HEAD_OLD, HEAD_NEW)
    wide = replace(wide, SCRATCH_OLD, SCRATCH_NEW)
    wide = replace(wide, PIPE_ANCHOR, PIPE_CODE + PIPE_ANCHOR)
    wide = replace(wide, "    fn extract128_timed<const C: u8, const O: u8>(\n",
                   "    fn extract128_timed<const C: u8, const O: u8, const P: u8>(\n")
    wide = replace(wide, "if let Some(relation) = scan_state128::<C>(\n",
                   "if let Some(relation) = scan_state128_select::<C, P>(\n", count=2)
    wide = replace(wide, "    fn extract128<const C: u8, const O: u8>(\n",
                   "    fn extract128<const C: u8, const O: u8, const P: u8>(\n")
    wide = replace(wide, "        let relation = extract128_timed::<C, O>(\n",
                   "        let relation = extract128_timed::<C, O, P>(\n")
    wide = replace(wide, "            let relation = extract128::<CANON_FULL, ORDER_LEFT_MAJOR>(\n",
                   "            let relation = extract128::<CANON_FULL, ORDER_LEFT_MAJOR, PIPE_OFF>(\n")
    wide = replace(wide, "        let (target_canon, target_canon_name) = target_canon_from_env();\n",
                   "        let (target_canon, target_canon_name) = target_canon_from_env();\n"
                   "        let (probe_pipeline, probe_pipeline_name) = probe_pipeline_from_env();\n")
    wide = replace(wide, MACRO_OLD, MACRO_NEW)
    wide = replace(wide, '"scan_order":scan_order_name,\n',
                   '"scan_order":scan_order_name,\n"probe_pipeline":probe_pipeline_name,\n', count=2)
    return head, wide


def combined_text():
    text = combined.derive(SOURCE.read_text())
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest != COMBINED_SHA256:
        raise ValueError("combined derivation differs from claude/n83-combined's frozen producer: " + digest)
    return text


def derive(text):
    head, rest = text.split(WIDE_START, 1)
    wide, tail = rest.split(WIDE_END, 1)
    head, wide = pipeline_edits(head, wide)
    return head + WIDE_START + wide + WIDE_END + tail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = derive(combined_text())
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("derived online source differs from " + str(OUTPUT))
    else:
        OUTPUT.write_text(text)
    print("online_source_sha256=" + hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
