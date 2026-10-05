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

This is a synthetic N53 correctness control only. N51 and N83 remain
unmeasured, and these results do not support an IC speedup claim.
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
