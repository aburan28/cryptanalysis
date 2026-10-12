# Q1529: exact N83 W≤5 quotient pair search and Bloom sweep

The native four-summand quotient search now runs on the **exact N83 W≤5
factor base** used by the compact S3 experiments: curve
`EC1N83Ckb1h876c2921cb64`, `B=30,977,592` distinct subgroup-usable points,
`K=186,612` signed/Frobenius columns, and enumerated base SHA-256
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
The 21-byte loader reconstructs and checks every orbit representative. A
four-point group control formed from the first two base points returns an
exact table/query match. The selected and holdout public points are the
existing one-target workloads `2eb250a29072` and `394256b9f901`.

The thirteen frozen cells each complete. For ordinary points, the table has
`2^18` quotient pair descriptors. Each target searches either `2^17` or
`2^20` query representatives. Every representative creates one pair sum and
166 target complements; every Bloom positive triggers a full exact table
replay. The recorded group control has five equivalent lifted matches. The
ordinary cells have zero exact matches, including the `2^20`-representative
prefix on **each** public target. Hyperparameter cells reuse those prefixes;
their counts are not independent relation trials.

| Target | Query representatives | Workers | Bloom bits/key, hashes | Positives | Target query + exact replay, exploratory s | Peak RSS, MiB | Charged pair additions |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| selected | 2^17 | 1 | 8, 3 | 381,787 | 2.532 | 1,219 | 22,413,312 |
| selected | 2^17 | 1 | 16, 4 | 35,210 | 2.631 | 1,187 | 22,413,312 |
| selected | 2^17 | 1 | 32, 6 | 423 | 2.789 | 1,185 | 22,413,312 |
| selected | 2^20 | 1 | 8, 3 | 3,053,452 | 22.769 | 1,451 | 175,636,480 |
| selected | 2^20 | 4 | 8, 3 | 3,053,452 | 8.352 | 1,464 | 175,636,480 |
| selected | 2^20 | 4 | 16, 4 | 281,552 | 6.670 | 1,190 | 175,636,480 |
| holdout | 2^20 | 4 | 8, 3 | 3,055,548 | 6.919 | 1,464 | 175,636,480 |

The six additional short cells and exact receipt values are in
[`analysis.json`](analysis.json). Within this unisolated host sweep, 16 bits
per key with four workers gave the lowest observed selected-target time at
`2^20` representatives and used 274 MiB less peak RSS than the matching
8-bit cell. The 8-bit setting was faster in the short single-worker selected
cell. These are exploration settings for a future isolated paired run; no
controlled CPU speedup ratio is assigned here.

The charged pair-addition count is exact at this code boundary:
`table_descriptors + 167*query_representatives + table_descriptors` when
there is at least one Bloom positive, otherwise omit the final replay term.
The `2^20` ordinary cells therefore execute **175,636,480 = 2^27.388**
pair-addition attempts each, including failed attempts and the exact replay.
Their target-dependent native interval is query plus exact replay; table
allocation/build is recorded separately as reusable preparation. Process
launch and base loading are excluded from that interval but included in each
receipt's exploratory wrapper wall time. This is a PDP stage result, so the
complete N131 solve-work field and one-target IC/rho comparison stay null.

The separate [Q1526 conditional N131 W7 pair-index screen](../q20261012_q1526_pair_hyperparams/RESULT.md)
remains **2^86.184702 pair-add attempts**, **25.184702 bits above 2^61**,
under its sampled W7 base and optimistic independent-query/rank assumptions.
Q1529 does not transfer N83 W≤5 relation yield to that sampled N131 base.
Its measured throughput and memory now allow a resource-sized N83 table
fraction to be selected before the next exact-base relation trial. A larger
table fraction, followed by independent group replay of every exact hit and
rank-novelty measurement, is the next experiment that can change the
relation-supply estimate.

## Reproduction

On this ARM64 host, build with `env PYTHONDONTWRITEBYTECODE=1 python3
experiments/compact-s3-m4-20261003/q20261012_q1529_n83_w5_pair_table/build.py`.
Then run `run.py`, `validate.py`, and `analyze.py` in that directory with
`PYTHONDONTWRITEBYTECODE=1`. The [build receipt](build_receipt.json) pins
Apple clang 17, source digests, and the binary SHA-256. The [protocol](protocol.json)
pins both public targets, workloads, the exact base, and output source. Each
cell preserves stdout, stderr, status, phase timings, memory, and hashes.
Q1529 makes no new mathematical theorem; its counting formula is checked
against the native loop bounds in `validate.py` and `analyze.py`.
