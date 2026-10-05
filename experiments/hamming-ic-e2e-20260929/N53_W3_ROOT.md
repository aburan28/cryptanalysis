# N53 weight-three root-index IC: three one-target pairs

This is a mathematical end-to-end index-calculus DLP control on the N53
Koblitz subgroup, with exploratory process-internal timing diagnostics.
It uses a four-summand S3 root index over the normal-basis Hamming-weight-three
factor base. It is a separate candidate from the five-summand FC-Hamming SAT
probe in this directory. The latter still has no successful unpinned N53 PDP
model under its tested bounds. `N53` names the field size; this subgroup has
prime order `21044858204113`, about 44.26 bits.

## Frozen method

- Curve: `EC1N53Ckb1hb75cbed53fce`, polynomial-basis `GF(2^53)` with
  modulus `u^53+u^6+u^2+u+1`, `y^2+xy=x^3+1`, prime subgroup order
  `r=21044858204113`, cofactor 428, and generator
  `(198217578752339,7929897206038174)`.
- Candidate: `IC1N53Ckb1fb23426PDP4rootRCguidedLAgaussTDdirectISO0hd89d75bbe48f`.
  The full [candidate manifest](runs/n53_w3_root_pair_v3/candidate.json) binds
  the method and binary digest. The [base export](runs/n53_w3_base_export_v1/representatives.json)
  contains all 221 sorted signed-Frobenius representatives. Its exact
  reconstruction has 23,426 usable subgroup points before folding.
- The reusable root index is built before the target online interval. The
  supplied target is decomposed directly. Fresh known-scalar ordinary
  relation queries are then collected until the target row lies in the
  verified relation span. Every one of those queries, including unsuccessful
  attempts, is charged to that target. No relation table is shared between
  targets. The final relation solve is incremental Gaussian elimination
  modulo `r`.
- The paired rho solver accepts only the same public point and a walk seed.
  It runs one signed-Frobenius worker and uses no cross-target table. Its
  clock includes target validation, jump generation, walk, collision solve,
  and recovered-scalar replay. Fixture generation and process launch are
  outside both online clocks. Each solver had a 120-second external wall
  limit and no imposed memory limit on macOS ARM64.

## Replayed one-target DLPs and exploratory timings

Each row is a separate workload containing exactly one previously unseen
public target. The target scalar is retained only for fixture validation;
neither solver receives it. Independent checked Sage replay reconstructed the
base, verified every retained relation as a curve-group equality, recomputed
the relation rank and target-span log, and replayed both recovered scalars.
That Sage replay ran **after** each Rust process's online clock and its cost
was not measured. The Rust IC clock ends after an in-process scalar replay.
No host-level CPU isolation or noise-gate receipt was recorded on this Mac.
The values below are therefore exploratory internal intervals, and the
controlled single-target online speedup is **unknown**.

| Run | Workload | IC internal interval | Rho internal interval | Observed rho / IC | Ordinary queries / verified / novel rank |
| --- | --- | ---: | ---: | ---: | ---: |
| `v3` | `bd9c9a1dff79` | 3,202.635 ms | 1,023.159 ms | 0.319× | 219 / 219 / 219 |
| `v4` | `247f33e06393` | 4,572.414 ms | 1,460.097 ms | 0.319× | 286 / 286 / 221 |
| `v5` | `c6f52be49d30` | 3,146.958 ms | 804.337 ms | 0.256× | 216 / 216 / 216 |

The observed ratios range from **0.256 to 0.319**; no controlled speedup or
confidence interval is available. Across these three adaptive relation
streams, 721/721 ordinary queries produced group-verified relations and 656
added rank. This is a count of successful searches over a large precomputed
index, not a cheap per-query success probability. The base has
`C(23426+3,4) = 12,551,410,757,022,501` four-point multisets, about 596 per
subgroup element on average. This makes high coverage plausible **if** sums
are well distributed, but the average alone does not prove coverage. The
three selected target seeds and rank-stopped query streams do not provide a
general natural-query yield or a valid binomial interval.

## Frozen ordinary-query holdouts

These secondary stage runs test root-index point decomposition without a
relation-rank stop. Each executable receives only public points and the same
221 representatives. The SHA-256-derived fixture scalars remain outside its
input. Every point is processed, and misses, invalid inputs, timeouts, and
incomplete rows would remain in the raw JSONL and receipt. None occurred.
The panels have no point in common with each other or with the three primary
one-target benchmark points. They are multi-query *stage diagnostics*, not
multi-target DLP benchmarks or replacements for the single-target metric.

| Panel and workload | Public points | Root-index completions | Independent Sage group-sum replays | Freeze status |
| --- | ---: | ---: | ---: | --- |
| [Initial](runs/n53_w3_root_holdout_v3/receipt.json), `ac55eb9ebb6a` | 256 | 256 | 256 | Seed selected before local execution; exact points not precommitted |
| [Commit-derived](runs/n53_w3_root_holdout_commitseed_v1/receipt.json), `ae4151006286` | 512 | 512 | 512 | Source commit fixed; exact derivation rule not precommitted |
| [Prospective](runs/n53_w3_root_holdout_precommitted_v1/receipt.json), `e837254308c6` | 512 | 512 | 512 | Exact point list committed and pushed before execution |

The [prospective manifest](n53_w3_root_precommitted_panel_v1.json) was
published in commit `b979dccf4d1df0d0308a67a71ed417cdea92d99a` before
the final panel ran. Its 512 public points and input SHA-256 match the bytes
read by the executable. [Independent replay](runs/n53_w3_root_holdout_precommitted_v1/sage_replay.json)
checked that Git commit, the seed derivation, all 512 public-point fixtures,
the exact 23,426-point base, and every four-point group-sum witness. The
first two panels also have independent Sage replays and remain visible as
earlier exploratory attempts; they are not pooled into a confidence bound.

The fixed executable samples one target-seeded Frobenius orientation per
quotient state and would scan all 2,588,573 states on a miss. Completion is
therefore an operational observation for this search rule, not proof that
every subgroup point decomposes. On the prospective 512-point panel, a
descriptive Wilson interval is 99.26–100% *if* the deterministic hash-derived
points behave as independent uniform subgroup draws. It is not a theorem or
a guarantee about all N53 points. The prospective run's unisolated Mac median
query interval was 11.148 ms; its 512 query intervals summed to 8.422 s.
Reusable index setup took 0.964 s outside those intervals, and peak solver
RSS was 341.6 MB. These stage timings carry no controlled speedup claim.
Each run directory retains the raw JSONL, frozen workload, source and binary
hashes, exact executed binary, Sage runtime identity, and replay.

The [measurement rows](runs/n53_w3_root_pair_summary/rows.csv) retain each
target point, exact online phases, base and index construction, rank yield,
matrix construction, incremental linear algebra, target descent and replay,
operation counts in the solver records, and per-child peak resident memory.
Root-index construction took 908–952 ms; IC peak RSS was about 405 MB.
Rho peak RSS was 50–93 MB. The IC online phase sum is checked against its
clock in each [Sage replay](runs/n53_w3_root_pair_v3/sage_replay.json).
The [summary JSON](runs/n53_w3_root_pair_summary/summary.json) carries the
observed ranges and claim boundary.
The [schema-v2 rows](runs/n53_w3_root_pair_summary/contract_v2.jsonl) pass
`experiments/ic-candidate-catalog/analyze_v2.py`. That analyzer checks the
measurement schema but does not establish CPU isolation or include the later
Sage replay in the Rust interval. The derived summary keeps controlled
speedup and its confidence interval `null`; operations and complete cold
phase costs also remain `null` because they were not fully calibrated.

The first fresh-target attempt (`v1`, run `R1` on workload `32611ba1c3e1`)
is retained as `HARNESS_FAILURE` in the rows. Its `/usr/bin/time -l` wrapper
returned exit code 1 because sandboxed `sysctl kern.clockrate` was denied;
the child solver outputs were retained, but this row has no verified speedup.
The direct `wait4` accounting in `v2` reran the same frozen point as `R2` and
passed independent Sage replay. Because the point was already seen by the
`v1` solvers, `v2` is a `VERIFIED_REUSE_CONTROL` and is excluded from the
primary one-target table and schema-v2 complete-DLP rows. Three new seeds
produced the `v3`–`v5` primary workloads. An earlier published target was
used only for a root-index smoke control and has its own independent Sage
replay.

This is a synthetic N53 correctness and ordinary-query stage control only.
N51 remains unmeasured. The separate [N83 weight-three geometry gate](N83_W3_GEOMETRY.md)
measures the exact four-sum support ceiling and rules out a direct ordinary-
target transfer of this base; it does not solve an N83 DLP. These results do
not support an IC speedup claim.
Setup-inclusive cost and a normalized
operation count `S` are not headline metrics here; no operation-count
boundary was frozen for a comparable `S` across the Rust IC and rho solvers.

## Reproduce

The checked Sage launcher must be used for all Sage jobs. Build the two
snapshotted Rust examples in the sibling `crypto` repository, then use fresh
output directories for new one-target workloads:

```sh
cp /Volumes/SSD990/cryptanalysis/experiments/hamming-ic-e2e-20260929/koblitz_w3_root_index.rs /Volumes/SSD990/crypto/examples/koblitz_w3_root_index.rs
cp /Volumes/SSD990/cryptanalysis/experiments/hamming-ic-e2e-20260929/koblitz_rho_point.rs /Volumes/SSD990/crypto/examples/koblitz_rho_point.rs
cd /Volumes/SSD990/crypto
cargo build --release --example koblitz_w3_root_index --example koblitz_rho_point
cd /Volumes/SSD990/cryptanalysis
python3 experiments/hamming-ic-e2e-20260929/run_n53_w3_root_pair.py --out /private/tmp/new-n53-w3-pair --run-number 1 --fixture-seed 20261004 --ic-seed 53020 --rho-seed 53021
/Volumes/SSD990/cryptanalysis/sage -python experiments/hamming-ic-e2e-20260929/sage_replay_n53_w3_root_pair.py --run /private/tmp/new-n53-w3-pair
python3 experiments/hamming-ic-e2e-20260929/summarize_n53_w3_root_pairs.py
python3 experiments/ic-candidate-catalog/analyze_v2.py experiments/hamming-ic-e2e-20260929/runs/n53_w3_root_pair_summary/contract_v2.jsonl
```

The run writes `sage_runtime_info.json` before either measured solver starts.
The `candidate.json`, `workload.json`, raw solver records, receipt, and replay
are immutable evidence. For the archived runs, source snapshots and binary
hashes are in each run directory and receipt. The actual Rust build used a
dirty sibling checkout, so the captured source and binary hashes are the
reproducibility boundary; a clean-checkout build has not been established.

To reproduce the separate holdout from a checkout containing this change,
copy its Rust example into the sibling `crypto` repository, build it, then
use a fresh output directory:

```sh
cp /Volumes/SSD990/cryptanalysis/experiments/hamming-ic-e2e-20260929/koblitz_w3_root_holdout.rs /Volumes/SSD990/crypto/examples/koblitz_w3_root_holdout.rs
cd /Volumes/SSD990/crypto
cargo build --release --example koblitz_w3_root_holdout
cd /Volumes/SSD990/cryptanalysis
python3 experiments/hamming-ic-e2e-20260929/run_n53_w3_root_holdout.py --out /private/tmp/new-n53-w3-holdout --count 256 --seed 20261004 --wall-seconds 300
/Volumes/SSD990/cryptanalysis/sage -python experiments/hamming-ic-e2e-20260929/sage_replay_n53_w3_root_holdout.py /private/tmp/new-n53-w3-holdout
```

The runner saves checked Sage runtime identity before executing the panel;
the replay requires a byte-identical executable snapshot and all source and
input hashes to match its receipt. Run output is immutable.
