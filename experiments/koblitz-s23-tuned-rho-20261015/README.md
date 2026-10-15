# Section 23 against the tuned rho: one unseen point, six sizes, four rho references

**Status (2026-10-15): protocol frozen; nothing measured yet.** This
directory freezes the protocol and its tools. The run starts when this
branch (`claude/ic-s23-tuned-rho`) is pushed: workflow
[`s23-tuned-rho.yml`](../../.github/workflows/s23-tuned-rho.yml) runs on
one GitHub-hosted runner (Tier 1, instance scoped). Its artifact will be
archived here as `run_github_<id>/`. The frozen design is
[`protocol.json`](protocol.json).

## Question

Ledger §23 (crypto `research/notes/index-calculus/RESEARCH_IC_BOUNDARY_LEDGER.md`)
compared the index calculus with Pollard rho on one unseen public point,
online and cold. Its sizes were `n = 47, 57, 41, 53, 59, 61` (`2^36.6` to
`2^47.2`), with 64 points each. Rule v3 (crypto `research/ic_tool_program/rule/v3`)
re-ran that round at the IC programme's baseline v3. Both rounds used one rho
reference, ParallelRho inside the same process.

The n=83 reconcile run (`../koblitz-n83-reconcile-20261014`) found that A's
tuned `StrongRhoG` (rT770: fold kernel, 64 lanes, DP 6) was 1.3–1.9× faster
than the default strong rho at n=83. With rT770 as the reference, the IC's
online advantage there was not separated from parity.

This round asks the same question with stronger references. On §23's
points, what are the online ratio, the cold ratio, the break-even count and
the Bernstein–Lange model at each size? It answers per reference:

| reference | what it is |
|:--|:--|
| `parallel` | §23's and rule v3's own: ParallelRho in the IC's process (64 lanes in lockstep) |
| `strong` | the default `StrongRhoG` parameters (32 lanes, DP 4, escape off) on the one-word `Gf2` field kernel |
| `strong_wide` | rA770 exactly: the default `StrongRhoG<WideGf2,u64>` (32 lanes, DP 4) |
| `tuned` | rT770's configuration (64 lanes, DP 6, escape off, A's `selected_config.json`) |

This is the "gap to the tuned rho" that `docs/ic/BASELINES.md` (cryptanalysis#922)
lists as unmeasured at n=41, 53 and 61.

![Design](figures/design.png)

*Figure 1. The design: four arms on each frozen point, the controls first
([source](figures/design.tex), [vector](figures/design.pdf)). Schematic; no data.*

## What runs

- **The IC** is crypto's `ic price --single-target` at `995ea207`: baseline
  v3, the code rule v3 measured. It runs on §23's parameter files with §23's
  rho seed `0x230000 + i`.
  - One process per point. Each process makes three repetitions of the IC
    and ParallelRho, and the median is the figure (§23's rule).
  - Online is §23's five-phase interval. Setup is the median repetition's
    `setup_ns`.
- **The three external rho arms** run on one worker,
  [`rho/s23_strong_rho_eval.rs`](rho/s23_strong_rho_eval.rs). It is derived
  from A's tuned worker at crypto `770f6a69`
  (`examples/n83_rho_optimization_eval.rs`, sha256 `fb14072f…`), and two
  things change:
  - **The curve.** It is `KoblitzCurve::new(a, n)`, taken from the command
    line. n=83 still asserts the exact legacy curve.
  - **The `fold` kernel.** Its `Gf2_128` exists only for `64 < n ≤ 127`, so at
    `n ≤ 64` the worker runs the library's one-word `Gf2`: the walk's native
    field, with pclmulqdq fold reduction where the modulus allows it. The
    receipt's `field_type` records which kernel ran.

  The walk, the jump derivation, the configs and the timer boundaries are
  the parent's. Online runs from the target's membership and subgroup check
  to a generic `[d]G = Q` replay. Setup is the excluded preparation (curve,
  normal basis, G-only jumps). A walk-only recut is reported beside it.
  Walk seed `0x230000 + i`.
- **Points.** These are §23's T01–T64 at each size: 384 public hash-to-curve
  points, frozen in [`inputs/targets.json`](inputs/targets.json) from §23's
  committed reports. The IC regenerates each one from its seed, and the
  verifier checks equality. T01–T04 run again as the A/A. **All 384 points
  are kept.** The estimate is about 2–3.5 h of a 6 h job. A time guard
  (330 min) would skip whole point blocks, and any it skips are reported.
- **Order and isolation.** One process at a time runs on one pinned CPU
  (`min(sched_getaffinity)`), with `isolated_bench`'s clean environment and
  `RAYON_NUM_THREADS=1`. The arm order rotates with the point. The Tier 1
  noise gate (throttling, steal, major faults) is recorded per process.
  - A failed or contended attempt is kept and run again, up to twice
    (§23's rule).
  - If all three attempts are flagged, the first valid one is used, marked
    as flagged, and the figures are also given without it.

## Controls (before the panel)

- **Identity.** On n=83's Q0, the derived worker must take rT770's
  5,096,116 steps (tuned, seed 202610061) and rA770's 10,203,425 steps
  (`strong_wide`, same seed), and recover 3141592653589793. This shows the
  derived worker is rT770's and rA770's walk. A failure voids the round.
- **Positive control.** The ln time ratio of `strong_wide` between seeds
  202610064 and 202610063 must be within 0.10 of the exact ln step ratio
  0.978 (14,229,982 / 5,353,957). A failure labels the readings
  `inconclusive_controls`.
- **Per row.** One scalar across the IC, ParallelRho and the three external
  arms. The IC's point equals the frozen point. The worker's order and
  generator equal the IC's fixture. The scalar replays in crypto's
  `oracle.py`.
- **Claims.** §23's own `claims.py` assembles and checks every IC row's
  `vs_rho` claim (identities, both certificates replayed in `oracle.py`,
  `validate_claim`).
  - It runs at crypto `96911f55`, rule v3's results commit, with two label
    edits that `restore_sources.py` asserts: the isolation text and the CPU.
  - At crypto main, the stricter checker no longer accepts §23's rows.
  - `verify_receipt.py` substitutes each external rho into the same claim
    and runs the same checker.

## Statistics (frozen)

Per size and reference, over the R1 rows:

- **Online:** mean rho online / mean IC online (§23's statistic), with a
  95% paired bootstrap interval over targets (10,000 resamples, seed
  2026101501). The reading is `ic_online_faster`, `rho_online_faster` or
  `not_separated`.
- **Cold:** mean (IC setup + online) / mean (rho setup + online), with the
  same bootstrap.
- **Break-even:** IC setup / (rho online − IC online) targets, or "never".
- **Bernstein–Lange (a model; no BL walk runs):** with `c` the reference's
  median ms per step, the BL online cost is `2.3353·r·c²/(2n·IC setup)` ms.
  The model is reported as IC online / BL.

An online ratio is never quoted without the cold ratio and the BL model
beside it. **Class: accounting.** No algorithm changes; the reference does.

## Local validation (correctness only; no timing is reported)

The local runs ran in a shared, contended container with rustc 1.97.0. The
workflow uses 1.99.0. Receipts are in [`smoke/`](smoke/).

- `restore_sources.py` restores both snapshots and the harness checkout,
  and all 26 digests match `protocol.json`.
- Both crates build: `crates/v3` (`ic_v3`) and `crates/r770`
  (`rho_s23_r770`).
- **Controls:** the identity control reproduced rT770's 5,096,116 and
  rA770's 10,203,425 steps on Q0, with scalar 3141592653589793. The
  positive control passed.
- **Panel:** `run_schedule.py --sizes k0n41 --targets 3 --aa 1` ran 18
  attempts, all valid (2 flagged as contended and re-run). Every arm recovered the same scalar on every point.
  - §23's `claims.py` passed 4 of 4 IC rows.
  - The substituted external-rho claims passed 9 of 9.
  - `verify_receipt.py --smoke` completed end to end.
  - An earlier smoke at k1n47 exercised the retry path: three contended
    attempts, kept, and the flagged-row fallback.
- The workflow YAML parses.

## Limits

- **Tier 1, instance scoped.** One runner and one pinned exposed CPU on a
  shared VM; exclusivity is not certified.
- **The IC binary is rebuilt here** with rustc 1.99.0 from v3's source. It
  is not rule v3's binary (`9c332039…`). crypto `995ea207` has no
  `Cargo.lock`, so `crates/v3/Cargo.lock` is crypto `770f6a69`'s, pruned.
- **`tuned` is rT770's configuration, not rT770's field kernel,** at these
  sizes: `Gf2_128` does not exist for `n ≤ 64` (see above).
- **BL is a model here.** The n=83 BL arm (`../koblitz-n83-bl-arm-20261014`)
  is the only measured BL arm.
- **Scope.** Nothing transfers to n=83 or ECC2K-130.

## Files

- `protocol.json`: the frozen design.
- `restore_sources.py`: snapshots, harness and digests.
- `crates/{v3,r770}`: the two crates.
- `rho/s23_strong_rho_eval.rs`: the derived rho worker.
- `configs/`: the default configs (the tuned config comes from crypto
  `770f6a69`).
- `inputs/targets.json`: the 384 frozen points.
- `run_schedule.py`: the schedule.
- `verify_receipt.py`: the audit and statistics.
- `figures/`: the design figure.
- `smoke/`: the local validation receipts.

## Reproduce

```sh
git clone --filter=blob:none --no-checkout https://github.com/aburan28/crypto C
python3 restore_sources.py --crypto-repo C
(cd crates/v3 && cargo build --release --locked); (cd crates/r770 && cargo build --release --locked)
python3 run_schedule.py --ic $CARGO_TARGET_DIR/release/ic_v3 --rho $CARGO_TARGET_DIR/release/rho_s23_r770 \
  --crypto-repo C --receipt-dir R --cpu 0
S23_ISOLATION_LABEL=... S23_CPUS=0 IC_RUNS=$PWD/R/runs IC_OUT=$PWD/R/claims_s23 \
  python3 C/research/ic_single_target_20260930/claims.py
python3 verify_receipt.py --receipt-dir R --crypto-repo C
```
