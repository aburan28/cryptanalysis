# E-1: remove per-partner nested clock reads

The sparse 24-bit root-index target stage can retain its outer target clock,
process CPU clock, and exclusive query/S3/partner phase clocks while omitting
canonicalization and lookup clock reads inside every partner check. On the
frozen N83 workload, the unclocked inner path reduced median target process
CPU from 2.756 to 2.366 seconds and median target-stage wall from 3.011 to
2.693 seconds in a six-run local panel. It was faster on both measures in
every adjacent pair. These timings are exploratory until the same panel has
a qualifying [CPU isolation receipt](../../../docs/ISOLATED_BENCHMARKS.md).

The curve is `EC1N83Ckb1h876c2921cb64`, workload `981ac530e67e`, and
proposal `Q2026101020`. The parent base has 30,977,592 usable points and
186,612 folded columns. Both arms index 2,000,000 pair states and 4,000,000
distinct root keys in the same 83,922,944-byte sparse table, then scan the
same public target. The per-arm cap is 1,024 MiB RSS and 180 seconds. Each
row recorded `state_cap_no_relation` at the specified pair-state cap.

| Inner diagnostics | Median target process CPU | Median target stage wall | Median partner-check wall | Table bytes | Full-key probes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Per-partner clocks | 2.756 s | 3.011 s | 1.688 s | 83,922,944 | 471,510 |
| Unclocked inner path | 2.366 s | 2.693 s | 1.210 s | 83,922,944 | 471,510 |

The counterbalanced order was reference/candidate, candidate/reference,
reference/candidate. Every run processed 8,000,000 partner roots. Target
process CPU ranged from 2.718 to 3.070 seconds for the clocked reference and
2.221 to 2.374 seconds for the unclocked path. The unclocked arm records
`null` for its two nested diagnostic intervals; they are not exclusive phase
costs. Each raw row and [`summary.json`](summary.json) records the exclusive
identity `target_stage = query_preparation + S3_batch + partner_check +
residual`; the runner checks that the residual is nonnegative. The target
clock begins after reusable factor-base and index preparation. The index,
root keys, first witnesses, arithmetic counts, memory, relation checks, and
bounded target status matched across arms.

Five Rust release tests passed, including randomized exact-map and duplicate
first-witness comparisons. Independent wrapper replays of both arms produced
the same pair certificate
`2665304bcdb73b73a19a155744d2fcfde7cb8dfde41e7ef05c454b2a47add288`;
[`replay_check.json`](replay_check.json) retains their raw-output digests.

Run `python3 run.py` here to verify frozen inputs, build, and execute the
six-run panel. Set `N83_E1_TARGET_DIR` to a volume with enough Cargo space.
`make_manifest.py` validates source and input receipts and prepares a paired
manifest for isolated physical-host replay.
