# Results: replay of n = 83 rank block K1 and one timed K600 base construction

**Verdict (frozen rule): `replay_pass`.** Archived 2026-10-17 from GitHub
Actions run [39007026856](https://github.com/aburan28/cryptanalysis/actions/runs/39007026856)
(job 117321470019, conclusion success, head `d1c361e3`). Every gated check
passed, on a host whose CPU model differs from the original run's, so the
replay counts as another host class under the protocol's own definition.
This report adds no new experiment and promotes, demotes or replaces no
baseline row; it closes the stacked row's replication item (R1) for
determinism and measures the construction time X that the row left
uncharged (K2 / K-N1).

## What was preregistered

[`PROTOCOL.md`](PROTOCOL.md), frozen 2026-10-17 at commit `863f6090`, on
its own, before the workflow commit `d1c361e3` (`.github/workflows/n83-replay.yml`)
and before any run. The run's head is `d1c361e3`, so it executed the frozen
protocol and the driver [`replay.py`](replay.py) unchanged. Six runs in one
job, one pinned CPU, one fresh process per run, in this order: R1 kS, R2 kP,
R3 kP, R4 kS (rank block K1, point `s000`, rank seed 101, full rank, 600
attempts each, retained K600 base), R5 cS on Q0 loading the retained base
(control), R6 cS on Q0 constructing the base in process
(`construct:83:1:600`). The protocol fixed three pass conditions, the
reported-not-gated numbers and the host-class rule before the job ran.

## Evidence

[`run_github_39007026856/`](run_github_39007026856/) is the workflow artifact
`n83-replay-39007026856-1` (id 12094959671, 76,482 bytes, zip sha256
`b8226c794d7a3c5c7ab369487399f25869bff3661ca17c521c2c2da0b8fb951d`), downloaded
through the GitHub API, checked against that digest, and unzipped byte for
byte. [`ARTIFACT.json`](run_github_39007026856/ARTIFACT.json) records its
provenance and `SHA256SUMS` the digest of every file. The verdict and the
numbers below are in
[`panel/replay_result.json`](run_github_39007026856/panel/replay_result.json)
(identical to `analyze-stdout.json`); per-run records are in
`panel/runs/0000{1..6}.stdout.txt` and `panel/runs.jsonl`.

**Independent check (this archive, 2026-10-17).** The per-attempt probe
lists of R1-R4 were decoded from their `raw_b64` records and compared with
the archived K1 records (`koblitz-n83-stacked-20261016/run_github_38862448935/panel/runs/00042`
and `00043`, whose file digests equal the protocol's `d3bcbef8…be8d` and
`2dd4bf0b…2396`): all 600 entries and the first 100 are equal for every run,
and the sha256 of the compact JSON lists equals the protocol's digests (kS
first 100 `8eed0160…64a6`, all `94856f30…791b`; kP first 100
`6081e1be…aafe8a`, all `d1d99f7e…cc6e`). `rank_relations_blake3` equals the
archived value for every rank run. The pooled per-probe ratio was recomputed
from the run rows (2.658328). Both IC and rho binaries have the same sha256
as in the original run (`ic_online_stacked_r770` `79c7bcd1…2e7b`,
`rho_tuned_r770` `a426c244…0b2f`; `binaries.sha256` in both artifacts).

## Host class

| | original (run 38862448935) | replay (run 39007026856) |
| --- | --- | --- |
| CPU model | AMD EPYC 9V74 80-Core Processor | INTEL(R) XEON(R) PLATINUM 8573C (family 6, model 207) |
| runner | GitHub `ubuntu-24.04`, 4 vCPU, Azure | GitHub `ubuntu-24.04` (image 20261012.334.1), 4 vCPU, 16 GB, Azure |
| kernel, compiler, Rust | 6.17.0-1022-azure, gcc 13.3.0, rustc 1.99.0 | the same |

`another_host_class` is `true` by the frozen rule (CPU model differs). The
VM hostname string (`runnervm8k3b6` in `host-probe.json`) is the same in
both artifacts; it is set by the runner image, and the CPU vendor and model
(`lscpu.txt`, `host-class.json`) show different hardware. Image, kernel and
toolchain are the same, so the replay varies the CPU (vendor,
microarchitecture, caches), not the software stack.

## Gated criteria (frozen)

| # | criterion | result |
| --- | --- | --- |
| 1 | all six runs `valid` in `run_schedule.one()` / `arm.py` terms (exit 0, verified scalar, full rank, factor logs equal to B's table, index digests equal to B's) | **pass** (`all_runs_valid`; 6/6 `valid`, no issues) |
| 2a | per-attempt probes equal the archived K1 records, first 100 attempts | **pass** (`probes_first100_equal_archived`) |
| 2b | the same on all 600 attempts | **pass** (`probes_all_equal_archived`) |
| 2c | `rank_relations_blake3` equals the archived value | **pass** (`relations_equal_archived`) |
| 3a | R5 loads the retained base (`base_source` `retained_header`) | **pass** (`R5_retained`) |
| 3b | R6 constructs it (`constructed_in_process_x_scan`, `base_scanned_x` 1266) | **pass** (`R6_constructed`) |
| 3c | R6's base hash equals R5's (the retained base) | **pass** (`constructed_base_hash_equals_retained`; both `d4a4da26d6e7cb09367de922d9806631fe49989f70d378cae76f347f8d76a9f7`) |

Verdict: **`replay_pass`** (`replay-exit.txt`: `replay_exit=0`).

The protocol abbreviates the base hash as `d4a4da26…f9e7`; the full hash
used by every earlier n = 83 experiment, and observed here, ends in
`…a9f7`. The abbreviation in the frozen text is a typo; criterion 3 compares
R6 with R5, so it does not depend on it.

## Reported, not gated

![Rank-stage wall time per probe for each rank process on both hosts, and
the base load of R5 (retained file) and R6 (constructed), all from the
archived records ([source](figures/replay.tex), [SVG](figures/replay.svg),
[vector PDF](figures/replay.pdf), rendered by
[`make_figure.py`](make_figure.py)).](figures/replay.png)

| rank run | arm | rank stage (ms) | probes | wall ns per probe |
| --- | --- | ---: | ---: | ---: |
| R1 | kS | 208,961.7 | 1,000,454,051 | 208.87 |
| R2 | kP | 854,793.3 | 1,508,460,462 | 566.67 |
| R3 | kP | 822,191.2 | 1,508,460,462 | 545.05 |
| R4 | kS | 209,430.7 | 1,000,454,051 | 209.34 |
| archived serial 42 | kS | 255,964.7 | 1,000,454,051 | 255.85 |
| archived serial 43 | kP | 884,004.0 | 1,508,460,462 | 586.03 |

| per-probe wall ratio kP / kS | replay (Intel 8573C) | archived (EPYC 9V74) |
| --- | ---: | ---: |
| primary: pooled rank stage per probe | **2.6583** | 2.2905 (K1); 2.2837 (both blocks, the README's figure) |
| secondary: first 100 attempts, `rank_attempt_ns` | 2.7013 | 2.2982 |
| all 600 attempts, mean | 2.6596 | |

R3 carries a `major page faults` contention flag (status still `valid`, no
issue); it is the faster of the two kP runs, so it does not inflate the
ratio. On this host kS is 1.22x faster per probe than on the EPYC
(208.9-209.3 against 255.8 ns) and kP 1.05x (545-567 against 586 ns), so
the per-probe ratio rose. K1's rank-stage wall ratio is 4.0082 here against
3.4536 in the original run; K1's probe ratio is 1.5078 on both (both
blocks: 1.4773).

| construction (R5, R6; same host, same job) | value |
| --- | ---: |
| X = R6 `timing_ms.base_load` (scan x from 1, lift, cofactor projection, first 600 signed-Frobenius orbits, built and indexed) | **427.524 ms** |
| R5 `base_load` (retained file, parsing only) | 361.984 ms |
| X minus the retained load | **65.541 ms** |
| `base_scanned_x` | 1,266 |

## Interpretation and limits

- **Determinism across host classes: established for K1.** The rank stage's
  work (every per-attempt probe count, the relation set) is bit-identical on
  an Intel Xeon 8573C and the original AMD EPYC 9V74, as the protocol
  required. The host-independent part of the stacked row's gain, the
  rank-stage operation-count ratio 1.4773 (probes and root calls, both
  blocks), therefore stands; it is a count fixed by the rank seed.
- **The wall-time headline is host-dependent.** The per-probe wall ratio is
  2.66 on this host against 2.28 on the original, so the 3.24x end-to-end
  wall-time ratio (R = 3.2391 [2.9809, 3.5240]) and every `S` on the row are
  one-host figures. On this replay host the per-probe factor is larger, which
  would favour the stack, but the replay re-measured neither the cold arms
  nor the 20 points, so it gives no new R or `S` on any host (PROTOCOL,
  "What this does not do"). The row keeps its R and `S` with the host named.
  One replay on one other host class: n = 2 processes per arm, no interval,
  no third host.
- **Construction time X: measured, and small.** X = 0.428 s, of which
  0.066 s more than loading the retained file. Against the end-to-end cold
  rows (283.8 s for cS, 919.2 s for cP) it is about 0.15% and 0.05%. With the
  stacked README's formula (X added to both arms' E2E; `S` = E2E over the
  run's 29,314.2 ms per unit, rT770 step 316.66 ns x sqrt(r)), the
  every-phase figures become **R 3.2357** (was 3.2391) and **cold `S` 9.6950**
  (was 9.6805; gap to the tuned rho 94.56 against 94.42). These are
  illustrative: they add an Intel-host X to EPYC-host wall times (PROTOCOL:
  any R(X) built this way mixes two hosts). The K2 / K-N1 caveat (3.2391 an
  upper bound, 9.6805 a lower bound) is now quantified: the bound is within
  0.11% of R and 0.15% of `S` at the measured X. The ratio falls below 2
  only at X >= 351.6 s, about 820 times the measured value.
- **Not addressed.** The §5a 0 / 0.1 / 1 GAE band stays uncomputable: the
  frozen producer emits no group-operation counts, and this replay used the
  same producer. That needs a producer change under a new protocol (stacked
  README, follow-up 1).

## Files

| File | Role |
| --- | --- |
| `PROTOCOL.md`, `replay.py` | frozen protocol and driver (commit `863f6090`) |
| `run_github_39007026856/` | the workflow artifact, unzipped byte for byte; `ARTIFACT.json` provenance, `SHA256SUMS` |
| `make_figure.py`, `figures/replay.{tex,svg,pdf,png}` | the figure: TikZ source and SVG written from the archived JSON and records; PDF by pdflatex, PNG by pdftoppm |
| `RESULTS.pdf` | this report: `pandoc RESULTS.md -o RESULTS.pdf --pdf-engine=pdflatex -H ../koblitz-n83-stacked-20261016/report_header.tex --lua-filter ../koblitz-n83-stacked-20261016/report_filter.lua -V geometry:margin=2cm -V fontsize=10pt -V colorlinks=true` |
