---
title: "Two-limb lift_scan in the n = 83 index-calculus pipeline"
date: 2026-10-15
---

# Two-limb lift_scan in the n = 83 index-calculus pipeline

**Status (2026-10-15): protocol frozen and run started; no timing result
yet.** The Tier 1 run is GitHub Actions run [38776966036](https://github.com/aburan28/cryptanalysis/actions/runs/38776966036), started by the push of commit `37dcdfaf8` to branch `claude/n83-liftscan`. Every number below is an exact
count, an exactness check, or an earlier experiment's figure. None is a
timing measurement of this experiment. The stage ratio, the online ratio,
the new baseline `S` and the tuned-rho gap are **pending**. They will come
from `verify_receipt.py` on the archived receipt, under the decision rule in
[`protocol.json`](protocol.json).

## Question

Can an exact, faster least-rotation canonicalizer lower the cost of the
current n = 83 index-calculus baseline? We test this at two levels:

- **Stage level.** In the frozen E-1 canonical root stage, does the two-limb
  binary-lifting `lift_scan` beat variant B, the zero-gap scan? This uses
  the same frozen pairs as the Tier 1 canonical replay.
- **Online level.** Does it lower the full one-target online interval of the
  current pipeline on Q0 and on B's 16 fresh points? On these points we also
  report the distance to the tuned rho.

This is the first step under the new success criterion (AGENTS.md "Success
criterion: iterative improvement of the index-calculus baseline", PR #919).
That criterion counts every verified, measured improvement to the IC
baseline, and makes each one the new baseline.

At n = 131, `lift_scan` beat the zero-gap scan by 1.8–3.8× inside a
decomposition-style loop
([`canon-n131-loop-20261014`](../canon-n131-loop-20261014/README.md),
[`canon-n131-20261014`](../canon-n131-20261014/README.md)). At n = 83, the
Tier 1 replay measured the zero-gap scan at 1.086 [1.076, 1.094] over the
full scan on the canonicalization phase
([`packed_index_e1_canonical_tier1_20261014`](../koblitz-n83-index-design-20260929/packed_index_e1_canonical_tier1_20261014/README.md)).

## Where canonicalization sits in the online path (source audit)

![Where canonicalization sits. (a) The one-target online interval and its
five phases. (b) The per-probe chain inside target_PDP. (c) The E-1 stage,
where canonicalization is its own timed phase. Phase times and counts in (a)
and (b) are from reconcile run 38617911080 (`iB770c` on Q0). They are another
experiment's figures, shown for location only
([source](figures/online_path.tex), [vector](figures/online_path.pdf)).](figures/online_path.png)

- **The canonicalizer in the online path is the full scan, not variant B.**
  The one-target pipeline is crypto `770f6a69`
  `examples/koblitz_orbit_dlp_fast_online.rs` plus B's `ic_log_cache.patch`.
  Its wide path (`mod wide`, n = 83) canonicalizes every partner root in
  `scan_state128` with
  `basis.canonical(basis.to_normal.apply(partner))`. That is
  `NormalBasis128::canonical`, the full 83-rotation scan.
  - The producer also carries a variant-B selector (`canonical_sparse`,
    `KIC_SPARSE_CANONICAL=1`). It reaches only `canonical_selected` in
    `build_index128`, which is target-independent setup outside the online
    interval.
  - Variant B is the canonicalizer of the E-1 packed-index **stage** only
    (`native_packed_index.rs`, `packed_bucket22_fastcanon`). It is not the
    canonicalizer of the one-target online path.
  - The online baseline arm is therefore the full scan. Variant B online
    (`qG`) is a secondary arm.
- **Its place in the interval.** The online interval is the producer's own
  clock, from `target_query_begin` to `recovery_check_end`, with five
  exclusive phases. Canonicalization is inside `target_PDP`. It runs once per
  probe, after the batched S3 root solve and the `to_normal` byte-table
  conversion, and before the root-table lookup. The clock does not time it
  separately.
- **Its share of the interval.** In reconcile run 38617911080 (`iB770c` on
  Q0), `target_PDP` was 4,755.8 of 4,756.0 ms (99.997%), over 8,845,441
  probes and 4,422,738 S3 root calls with 1 relation check. That is another
  experiment's figure; it locates canonicalization but does not size it. This
  run measures the share directly:
  - The planted arm `qFx2` does one more, discarded, full scan per probe. So
    `(qFx2 - qF)/qF` is the marginal share of one canonicalization in the
    baseline interval, with a bootstrap interval.
  - `(qF - qL)/qF` is the saving `lift_scan` realizes.
  - The `target_pdp_ms / online_ms` share is reported too.
  - All three are **pending** the run.

## The canonicalizer

[`lift2/src/lib.rs`](lift2/src/lib.rs) implements `L2<N, B>`. It holds an
`N`-bit cyclic word in two `u64` limbs, `lo` with bits `0..B-1` and `hi` with
bits `B..N-1`. The production geometry is `N = 83`, `B = 64`, so the limbs
hold 64 and 19 bits. It is the variant-A analogue of canon-n131's
`lift_scan`, cut down from three limbs to two:

- `Z_1 = !x`, and `Z_{2a} = Z_a & rotl(Z_a, a)`, for runs of length 1, 2, 4,
  ..., 64.
- Greedy top-down lifting gives the tops of all longest cyclic zero runs. It
  uses only constant rotations and mask selects, behind an `asm!` value
  barrier.
- A loop over those tops then keeps the least rotation, with ties going to
  the smaller shift.
- The words `0` and `mask` return shift 0, as the full scan does.

The same source file is compiled into the stage binary and into the online
producer through `#[path]` modules. The online producer monomorphizes it per
wide degree, so every rotation shift is a constant.

## Exactness (verified locally; the CI run repeats all of it before timing)

| Check | Size | Disagreements |
| --- | ---: | ---: |
| `lift2` tests: every word at N = 3..20 (2,097,144 words), each under every two-limb split ⌈N/2⌉ ≤ B < N for N ≤ 16 and 3–4 splits for N = 17..20, composite N included (periodic and tied words) | 7,252,648 (word, split) cases | 0 |
| N = 83: 0, all ones, every weight-1 and weight-82 word | 168 | 0 |
| N = 83: one zero run of every length 1..82 at every top position (± random background) | 13,612 | 0 |
| N = 83: longest runs across the limb boundary (bits 58–70, 60–64, 63–64, 64–66), ending at bit 82, at bit 0, and wrapping 82→0 | 1,446 | 0 |
| N = 83: two- and three-way ties of the longest run | 200,000 | 0 |
| N = 83: fixed-seed words of mixed density | 2,000,000 | 0 |
| every dispatched wide degree (14 degrees, 65 … 127) on fixed-seed and edge words | 14 × 50,005 | 0 |
| stage `packed_bucket22_verifycanon`: every word the frozen E-1 stage canonicalizes (4,000,000 index + 8,000,000 target + 64 sample), full vs variant B vs `lift_scan` | 12,000,064 | 0 and 0 |
| stage pair certificate (20 fields incl. lookup-sample keys and shifts), modes `liftcanon`, `fastcanon_x2`, `verifycanon` | 3 runs | equals frozen `7cfba635...acaff8` |
| online `KIC_TARGET_CANON=verify`: every probe word of the one-target scan, full vs variant B vs `lift_scan` | 27,225,926 (Q0, w00, w01, w02 locally; all 17 points on the runner) | 0 and 0 |

The test can fail. Two mutations were tried:

- reversing the tie-break: 11 of 24 tests fail;
- zeroing the cross-limb carry in `shl`: 22 of 24 fail.

A third mutation removed the last lifting stage. It still passes, and should:
the candidate set then becomes a superset of the longest-run tops, which is
slower but still exact.

![Exact rotation counts in the frozen E-1 target stage (8,000,000 words). Full
scan and variant B are the frozen E-1 rows. The lift_scan count is the number
of nonzero-shift candidate rotations, from the local exactness run; the 13
constant rotations of the lifting are not counted. These are counts, not times
([source](figures/rotation_counts.tex),
[vector](figures/rotation_counts.pdf)).](figures/rotation_counts.png)

## Frozen design

[`protocol.json`](protocol.json) and [`schedule.json`](schedule.json) were
written and committed before any timing. `make_schedule.py --check` and
`restore.py` re-verify them, and every source digest, on the runner.

| Arm | Binary / mode | Role |
| --- | --- | --- |
| `sB` | stage `packed_bucket22_fastcanon` | stage baseline: variant B |
| `sA` | stage `packed_bucket22_liftcanon` | stage candidate: `lift_scan` |
| `sBaa` | stage `packed_bucket22_fastcanon` | stage A/A control |
| `sBx2` | stage `packed_bucket22_fastcanon_x2` | stage planted positive control: one more, discarded, variant-B call per word |
| `sV` | stage `packed_bucket22_verifycanon` | exactness, 12,000,064 words, not timed |
| `qF` / `fF` | online `KIC_TARGET_CANON=full` | online baseline: the pipeline's full scan, unchanged behaviour |
| `qL` / `fL` | online `lift` | online candidate |
| `qG` | online `gap` | secondary: variant B in the online path |
| `qFaa` | online `full` | online A/A control |
| `qFx2` | online `full_x2` | planted positive control; also sizes one canonicalization per probe |
| `qV` | online `verify` | exactness on Q0 and every fresh point, not timed |
| `rT` | A's tuned rho (Fold/64/DP6, crypto 770f6a69) | distance to the strongest n = 83 rho measured so far (reconcile `rT770`) |

- **Stage panel.** The frozen E-1 workload `981ac530e67e` on curve
  `EC1N83Ckb1h876c2921cb64`, with 2,000,000 pair states and a 1,024 MiB RSS
  cap. The binary is the frozen source with one change, the canonicalizer
  behind `Cycle::canonical`. There are 16 blocks of the four timed arms in
  seeded shuffled order.
  - Every arm must reproduce the frozen E-1 pair certificate and its mode's
    frozen rotation counts.
  - Primary: the canonicalization phase `timing_ns.target_cycle_canonical`,
    as the per-block ratio sB/sA. The estimate is the median of the 16, with
    a paired bootstrap (10,000 resamples; seed 20261011; indices 250 and
    9749).
  - Secondary: the target stage.
- **Online panels.** Curve `EC1N83Ce1h35c7ced6b497`, with the retained K600
  base `d4a4da26...a9f7`. B's archived factor-log table is re-verified in the
  pinned oracle before timing, and again in every process.
  - Q0 has 8 blocks: `qF`, `qL`, `qG`, `qFaa` and `qFx2`, plus `rT` at seed
    202610060 + block. The primary is the median of the per-block qF/qL
    ratios.
  - B's 16 fresh points (seeds 0..15) each get `fF`, `fL` and `rT` at seed
    830000 + w. The primary is the section-23 ratio of means, bootstrapped
    over points.
- **Order and isolation.** Exactness comes first, then the stage blocks,
  then Q1, F1, ..., Q8, F8. The whole run is one GitHub-hosted
  `ubuntu-24.04` runner. Every process is pinned to one CPU, with the
  `isolated_bench` Tier 1 counters and memory gates on each.
- **Gates and controls.** All identity checks must hold on every point:
  - the same probes, relation and scalar in every IC arm;
  - IC and rho agreeing on the scalar;
  - an oracle replay of `[d]G = Q`;
  - Q0's scalar equal to the sidecar.

  The A/A intervals must lie inside [0.97, 1.03], and the planted lower
  bounds must exceed 1. Otherwise that level is `invalid`.
- **Decision.** A lower bound above 1 is `improvement`; an upper bound below
  1 is `regression`; otherwise `not_separated`.
  - The online level is an improvement only when both Q0 and the fresh
    section-23 primary are improvements.
  - An online improvement makes the `lift_scan` pipeline the new one-target
    baseline (the ratchet). A stage-only win is recorded as a stage
    improvement.
- **S.** `S_probe = probes / sqrt(r)` is unchanged by construction, because
  probes are a pair field. `S_rho = (IC online / tuned-rho ms per step) / sqrt(r)`
  prices the online interval in this job's rho steps. It is reported for the
  old and the new baseline, with its delta. Here √r = 92,573,139.2 and
  r = 8,569,786,107,849,059.
- **Runtime estimate.** About 1.5–2.3 h of panel time after a 15–25 min
  build. That rests on the reconcile run, where the cached IC process wall
  was 41–45 s and the tuned rho took 2–3 s. The time guard writes
  `skipped_time_guard` rows rather than dropping them.

## Result

**Pending** run 38776966036. The archive step is:

1. Download artifact `n83-liftscan-<run_id>-<attempt>` into
   `run_github_<run_id>/`.
2. Run `python3 verify_receipt.py run_github_<run_id>/panel` with the
   snapshots restored (it must reproduce `result.json` byte for byte).
3. Run `python3 make_figures.py run_github_<run_id>/panel/result.json`.
4. Fill this section from `result_table.md`:
   - the stage ratio and the online ratios, each with its interval;
   - the canonicalization share;
   - the new baseline `S_rho` and its delta;
   - the tuned-rho gap on Q0 and the fresh points.

## Local validation (2026-10-15, cloud agent VM; no timing claims)

The VM is a 4-vCPU Firecracker guest shared with other agents. Its clocks
are not evidence, and no time from it is reported.

- **Build and tests.**
  - `lift2`: 24 tests passed.
  - stage crate: 5 tests passed. These include the frozen
    `zero_gap_canonical_matches_full_rotation_scan` and the new
    `lift_planted_and_verify_modes_match_full_scan_at_n83`.
  - online crate: the producer's own 3 tests and the tuned rho's 4 tests
    passed.
  - Toolchain: rustc 1.97.0 here. The runner pins 1.99.0, as the reconcile
    run did.
- **Exactness.** See the table above. The local smoke receipt is in
  [`smoke/`](smoke/README.md), with correctness only: `correctness.json`
  holds no timing values.
- **Smoke run.** `run_schedule.py --segments X,S1,Q1,F1
  --max-runs-per-segment 6` ran the real binaries through the real wrapper,
  gates and verifier. A container restart cut it short after the five exactness rows. A second part then ran `--segments S1,Q1 --one-per-arm`. All 15 rows were valid. Every IC arm on Q0 found the same 8,845,441 probes, the same relation and the scalar 3141592653589793, which equals the sidecar. The tuned rho agreed. A full dry run of the analysis and figure scripts on synthetic timings worked end to end; its outputs were discarded.

## Files

| File | Role |
| --- | --- |
| `protocol.json`, `schedule.json`, `make_schedule.py` | frozen protocol and run order |
| `lift2/` | the two-limb `lift_scan` crate and its exhaustive tests |
| `stage/` | E-1 stage binary (frozen source plus the canonicalizer selector), frozen `Cargo.lock` |
| `online/`, `make_online_source.py` | online producer derived from B's producer by counted exact replacements, plus A's tuned rho; reconcile's `Cargo.lock` |
| `restore.py`, `check_log_table.py` | restore and digest-check both crypto revisions and all local sources; re-verify the factor-log table |
| `arm.py`, `run_schedule.py` | one arm per pinned process; the schedule runner (reconcile's, adapted) |
| `verify_receipt.py` | gates, statistics, decision rule; `result.json`, `result_table.md` |
| `make_figures.py`, `figures/` | figure sources (TikZ), PDF and PNG renders |
| `.github/workflows/n83-liftscan.yml` | the Tier 1 job (push to `claude/n83-liftscan`; receipts, README, figures and figure scripts excluded from its path filter) |
| `README.pdf` | this report: `pandoc README.md -o README.pdf --pdf-engine=pdflatex -H report_header.tex --lua-filter report_filter.lua -V geometry:margin=2cm -V fontsize=10pt -V colorlinks=true` |

## Limits

- The verdicts are Tier 1 and instance-scoped: one runner, one pinned CPU,
  not host-isolated.
- Q0's intervals cover repeat and timing variation, not target variation.
  The fresh panel carries the target variation.
- The stage's canonicalization phase brackets every word with an `Instant`
  pair. That overhead is common to both arms, and it dilutes the stage ratio.
- The online ratio is the improvement that counts for the baseline.
- The index build still uses the full scan, because it is target-independent
  setup. Moving it to `lift_scan` would change setup cost, not the online
  interval. It is the obvious next step for end-to-end cold `S`.
- The tuned-rho gap is the distance remaining. It is not a pass/fail gate,
  and nothing here is a claim to beat rho.
