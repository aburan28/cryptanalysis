# Protocol: replay of n = 83 rank block K1 and one timed K600 base construction

Frozen 2026-10-17, before any run of this protocol. Committed on its own,
ahead of the workflow that runs it (`.github/workflows/n83-replay.yml`).

## Purpose

Close, or bound, two open items of `koblitz-n83-stacked-20261016` (run
38862448935, one GitHub `ubuntu-24.04` runner, AMD EPYC 9V74):

1. **R1 (sheriff SHF-20261016-3caa6f; residual R1-R in SHF-20261017-e4d7f6).**
   The result was not replayed on another host class. Replay rank block K1
   for kP and kS and check that the work is identical and how the per-probe
   wall time behaves on the host the job gets.
2. **K2 / K-N1, the uncharged phase.** Factor-base construction was charged
   to neither arm (`base_source` `retained_header`). Time one cold
   construction of the K600 base in the same job.

This is a replay of frozen code, not a new experiment: nothing here can
promote, demote or replace a baseline row.

## Frozen inputs (unchanged, digest-checked by the stacked experiment's own steps)

| input | sha256 |
| --- | --- |
| `experiments/koblitz-n83-stacked-20261016/protocol.json` | `094f59931521bdaf4138d8e81fc165652500d771b555864be44a8408cddd1cc7` |
| `experiments/koblitz-n83-stacked-20261016/schedule.json` | `79849500f357558478d84de73729b9256dff7df7f79ab050856aa9b63cfb0d22` |
| `experiments/koblitz-n83-stacked-20261016/arm.py` | `cd18afb07860f98d5abd2165b986e6a36a6e24ff3d8c6268a1360210e3cd602a` |
| `experiments/koblitz-n83-stacked-20261016/run_schedule.py` | `1f5614146acb450889763ad5b91089d31c1581e37a897f5ca02e25b0d903f6b0` |
| `scripts/isolated_bench.py` | `48361f0d0a5138e9e2f1264ff3de689fddb9d1a5181afd089e70c153e3a089cc` |
| archived K1 kS record, `run_github_38862448935/panel/runs/00042.stdout.txt` | `d3bcbef8636573a7359254d4890454e4776000414a9de499ddc61ab872dcbe8d` |
| archived K1 kP record, `run_github_38862448935/panel/runs/00043.stdout.txt` | `2dd4bf0b361d5b60bea75a9e363ec61b1af6c9dc03cef2b178e85a4872d92396` |
| `experiments/koblitz-n83-replay-20261017/replay.py` (driver and analysis, this commit) | `b5b72ebfa29c33f81c96b8022cdcefe05ada5694c3978bf11350cf99d60d308e` |

The producer is the stacked experiment's `ic_online_stacked_r770`, built by
the stacked workflow's own steps, copied unchanged: restore crypto
`770f6a69` with `restore.py` (which checks every pinned digest, including
the derived producer source `83b58988…`), Rust 1.99.0, `cargo test` of
`lift2` and `online`, `cargo build --release --locked`, and the
re-verification of B's archived factor-log table. The binary's sha256 is
recorded; on another CPU vendor or image it may differ, and that is
recorded, not gated.

## Runs (one job, one pinned CPU, one fresh process per run, this order)

Every run goes through the stacked experiment's `run_schedule.one()` and
`arm.py` unchanged (same environment whitelist, Tier 1 counters, noise
gate, factor-log check against B's archived table). The rank arms keep the
original `KIC_RANK_*` flags from `protocol.json`: kS `KIC_RANK_CANON=lift`,
`KIC_RANK_ORDER=feistel`, `KIC_RANK_PROBE=target` (folded, compact table);
kP `KIC_RANK_CANON=full`, `KIC_RANK_ORDER=left_major`, `KIC_RANK_PROBE=off`
(unfolded, base table). Each rank process runs to full rank (600
attempts): the frozen producer has no attempt cap.

| label | arm | point | seed | base argument | archived twin |
| --- | --- | --- | --- | --- | --- |
| R1 | kS | K1 point `s000` | 101 | retained K600 file | serial 42 |
| R2 | kP | K1 point `s000` | 101 | retained K600 file | serial 43 |
| R3 | kP | K1 point `s000` | 101 | retained K600 file | serial 43 |
| R4 | kS | K1 point `s000` | 101 | retained K600 file | serial 42 |
| R5 | cS | Q0 | 7 | retained K600 file (control) | serial 2 |
| R6 | cS | Q0 | 7 | `construct:83:1:600` | none |

R6 is the timed cold construction. It uses the producer's own
`construct:<n>:<a>:<columns>` path, the constructor and recipe that built
this base (`experiments/n83-compact-orbit-size-sweep-20261012`, arm K600:
`construct:83:1:600`, "scan polynomial x from one; rational lifts;
cofactor projection; first K distinct signed-Frobenius orbits",
`base_scanned_x` 1266, base hash `d4a4da26…f9e7`). X is R6's
`timing_ms.base_load` (setup start to the base built and indexed by x); R5's
`base_load` is the retained-file load on the same host, so X minus R5's is
also reported.

The job also records `lscpu`, `/proc/cpuinfo` model name, `nproc`, memory and
the runner image (`host-class.json`), so the host class is evidenced.

## What is read

- Per rank run: `rank_attempt_probes` and `rank_attempt_ns` (600 each),
  `rank_probes_total`, `rank_root_calls_total`, `rank_relations_blake3`,
  `timing_ms.rank_stage`. The first 100 attempts are read separately.
- Per cS run: `base_source`, `base_scanned_x`, `base_hash`,
  `timing_ms.base_load`, `setup_total`, `cold_in_process_ms`.

## Pass / fail (frozen)

The replay **passes** only if all of:

1. All six runs are `valid` in `run_schedule.one()` / `arm.py` terms (exit
   0, verified scalar, full rank, factor logs equal to B's archived table,
   index digests equal to B's index).
2. Per-attempt probe counts equal the archived K1 records exactly: every
   kS run's `rank_attempt_probes` equals serial 42's, every kP run's equals
   serial 43's, both on the first 100 attempts and on all 600
   (archived first-100 digests: kS `8eed0160…64a6`, kP `6081e1be…aafe8a`;
   all-600: kS `94856f30…791b`, kP `d1d99f7e…cc6e`; sha256 of the compact
   JSON list), and `rank_relations_blake3` equals the archived value.
3. R6 reports `base_source` `constructed_in_process_x_scan` and a base hash
   equal to R5's (the retained base, `d4a4da26…f9e7`).

Any other outcome is `replay_fail` and is reported as such, with every row.

**Reported, not gated** (wall time is host-specific):

- The per-probe wall-time ratio kP / kS on this host. Primary:
  sum of `rank_stage` ms over the two kP runs per probe, over the same for
  the two kS runs. Compared with the archived K1 value 2.2905 (same
  statistic, serials 43 / 42) and the both-block value 2.2837 that the
  stacked README quotes. Secondary: first-100-attempt ratio from
  `rank_attempt_ns` (archived K1: 2.2982). This is per-probe wall time,
  not a host-speed factor: a kP probe (full canonicalization) and a kS
  probe (lift_scan) are not the same work.
- The construction time X (s) and X minus the retained load.

**Host class.** The replay counts as "another host class" only if the
recorded CPU model differs from `AMD EPYC 9V74 80-Core Processor`. If the
job lands on the same model, it is a same-class replay: checks 1-3 still
test determinism, but R1 stays open and a `workflow_dispatch` with another
`runs_on` label is the next step. A non-x86 runner compiles the producer
without `_mm_prefetch` (its `cfg(not(target_arch = "x86_64"))` path), so
there the per-probe ratio mixes code path and host; checks 1-3 still apply.

## What this does not do

- It does not emit group-operation counts: the frozen producer has none, so
  the §5a 0 / 0.1 / 1 GAE band stays uncomputable. That needs a producer
  change in a new protocol (stacked README, follow-up 1).
- It does not re-measure the cold arms cP / cS on the 20 points, so it gives
  no new end-to-end R or `S`. Any R(X) figure built from X and the archived
  run mixes two hosts and is labelled illustrative.

## Outputs

The workflow uploads `host-class.json`, the build and restore receipts, the
panel (`runs.jsonl`, per-run stdout / stderr, `runner_start.json`) and
`replay_result.json` / `replay_result.md`. Archiving them into this
directory, and any update to `docs/ic/baselines.json`, is a separate commit.
