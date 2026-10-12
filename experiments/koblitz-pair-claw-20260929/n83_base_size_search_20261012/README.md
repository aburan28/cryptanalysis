# N83 minimum-capacity known-log factor base for the M32/R29 pair-claw layout

The exact seeded base with **23,859 signed-Frobenius orbits** contains
**3,960,594 distinct usable subgroup points before folding**. It is the
smallest orbit count whose cross-orbit pair-rank domain can hold one
\(2^{32}\)-descriptor table and all 80 planned \(2^{29}\)-representative
query ranges without reusing a pair rank. Its 47,245,925,826 ranks leave
1,285,570 unused. The [base receipt](minimal_base.json) and
[key/log file](minimal_base_keys_and_logs.bin) retain the exact point set,
canonical logs, and source hashes. This is a capacity result for the fixed
pair-table layout; relation yield and complete one-target cost require a new
frozen target run.

## Schedule capacity

The native domain is \(D(K)=166\binom K2=83K(K-1)\). The frozen
[Q1090](../n83_q1090_holdout_m32_wave_plan.json) and
[Q1091](../n83_q1091_holdout_m32_continuation_plan.json) plans cover 80
contiguous query ranges totaling 42,949,672,960 representatives. One
table prefix contains 4,294,967,296 descriptors. The
[capacity audit](capacity.json) binds both plans, their public point, the
[terminal reconciliation](../n83_q1091_terminal_reconciliation.json),
base receipts, and key/log files by SHA-256.

| Base | Orbit count \(K\) | Actual points \(B\) | Pair-rank domain | Spare after table and 80 queries |
| --- | ---: | ---: | ---: | ---: |
| Minimum-capacity seeded prefix | 23,859 | 3,960,594 | 47,245,925,826 | 1,285,570 |
| Existing Q1043 base | 24,097 | 4,000,102 | 48,193,228,896 | 948,588,640 |
| Q1091 base | 48,194 | 8,000,204 | 192,776,915,686 | 145,532,275,430 |

The count below 23,859 fails the inequality:
\(D(23,858)<2^{32}+80\cdot2^{29}\le D(23,859)\). Capacity alone does
not establish that the first collision will occur within those ranges.

The Q1091 affine query offset cannot be copied to the smaller base. At
\(K=24,097\), it makes all 4,294,967,296 table pair ranks recur within the
80 planned query prefixes. For each smaller base, the audit defines the
query offset as `table_offset + table_step * 2^32 (mod D(K))`; its affine
position shift is exactly \(2^{32}\), placing all query ranks immediately
after the table prefix. The resulting offsets are 29,819,999,030 for
\(K=24,097\) and 17,335,236,140 for \(K=23,859\). The table step is
coprime to both domains, so each prefix
contains distinct pair ranks.

## Base derivation and stage replay

[derive_minimal_base.py](derive_minimal_base.py) replayed the first 23,859
distinct orbits of `random.Random(831043).randrange(1,r)`. For every draw,
it recomputed the curve point, canonical signed-Frobenius key, and log, and
matched both against the independently verified 24,097-orbit parent file.
It reloaded the saved file and checked selected group-law log certificates.
The derivation took 116.85 s on the local ARM host; this is target-independent
preparation, outside a single-target online interval.

The [first protocol](protocol.json) and [stage receipt](stage_runs.json)
compare the 24,097- and 48,194-orbit bases. The
[minimum-base protocol](minimal_protocol.json) and
[stage receipt](minimal_stage.json) compare 23,859 and 24,097 orbits. Both
panels use the same public point, frozen native source generator and field
header, M20 table, R18 query range, 20-bit/10-hash filter, four workers,
and ABBA order. Each of the eight cells completed exact replay with zero
exact hits. Their peak RSS ranges were 163.7-163.8 MB at 23,859 orbits,
165.2-165.3 MB at 24,097, and 325.2-325.3 MB at 48,194. Build, query,
replay, subprocess wall, filter positives, and failures are retained per
cell. These are local unisolated stage diagnostics: elapsed times varied
substantially between repeats and are not a controlled timing ranking.

## Next one-target experiment

Freeze a new unseen public point and a complete candidate manifest for the
23,859-orbit base, including its distinct query offset and exact source
hashes. Run all target-dependent attempts under a declared memory and worker
envelope, retain cancellations and failures, verify a recovered scalar with
the checked Sage launcher, and pair its one-target online wall with rho on
that same point. The published Q1091 M32 jobs reached 11.06 GB peak RSS on
the larger base, so a strict 8 GiB envelope also requires a measured filter
and spill configuration before dispatch. Use a Tier 0 host receipt or a
qualified Tier 1 RunPod receipt for promoted CPU timing comparisons.

## Reproduce local artifacts

```sh
python3 experiments/koblitz-pair-claw-20260929/n83_base_size_search_20261012/run.py
python3 experiments/koblitz-pair-claw-20260929/n83_base_size_search_20261012/derive_minimal_base.py
python3 experiments/koblitz-pair-claw-20260929/n83_base_size_search_20261012/run.py --stage
python3 experiments/koblitz-pair-claw-20260929/n83_base_size_search_20261012/run_minimal_stage.py
```

These scripts use the repository's pure-Python curve code and native C++
runner; they do not start a Sage job. A future Sage verification job must
use `/Volumes/SSD990/cryptanalysis/sage` and save `--runtime-info`.
