# Q1420 selector component is selectable, with no verified Q0 relation in the capped panel

An 8,000-row/12,000-column, one-matrix CryptoMiniSat policy selected the
**7,380 × 7,524** native-XOR component containing all 144 W24 selector bits
on both the source and oriented degree-263 descendant Q0 circuits. The
matched default, selector-window, largest-only, and five-matrix policies all
entered search and reached 2,001–2,003 conflicts with `BOUNDED_UNKNOWN`.
These eight attempts emitted zero verified Q0 relation rows. The experiment
establishes exact component selection and its resource cost at a common
conflict budget; the capped statuses do not establish ordinary-query yield.

The [protocol](PROTOCOL.md), source pins, component analyzer, runner, and
auditor were committed as `bf61caea2` before input generation. A signed
named-literal parsing correction was committed as `f5379b0cc` before the
two [component inventories](runs/R1/source.components.json) and eight
input/policy records were frozen in `92d79d10f`. The original protocol's
preliminary label for the largest raw components was incorrect; the
[erratum](ERRATUM.md) records why and preserves the original preregistration.
A post-run auditor change in `d6db8d59b` adds SHA-256s for the printed
restart rows. The [prior audit](runs/R1/audit_before_trace_hash.json) is
retained, and a fieldwise comparison confirms that only the auditor hash and
those new trace hashes changed. The [final independent audit](runs/R1/audit.json)
rechecks both archived XCNFs, every source/input/solver hash, the exact flags,
matrix dimensions, conflict/status/guard evidence, and complete raw
stdout/stderr. No SAT assignment was emitted for clause/XOR and group replay.
The [runtime receipt](runs/R1/runtime-info.json) records the host
architecture, binary hash, launch command, and solver timing boundary.

The inputs are the exact first public target of workload `eee7f6ee5f6b` on
`EC1N131Ckb1h136f03e58c98` and its degree-263 descendant
`EC1N131Cbinh833014327b07` along `IW1E263d1hadee4e69fa3d`. Both W24
factor bases have `B=16,772,828` distinct subgroup-usable points before
sign folding. Q1420 is a design proposal (`candidate_id: null`). The raw
XCNF graph has 842 nontrivial native-XOR components on each curve. Its
selector component has 7,524 variables and 7,380 native-XOR lines, ranking
23rd by raw size. The largest raw components have 27,604 source or 27,759
descendant variables and **no named inputs**. Raw graph sizes are measured
before CryptoMiniSat preprocessing; the exact selector-size matrix match is
confirmed separately by the solver transcripts.

All cells used one thread, CryptoMiniSat 5.14.7, a 2,000-conflict limit,
120-second internal and 180-second external wall limits, and a sampled 4-GiB
RSS guard. Each cell ran once. The table records the audited matrix selection
and complete capped solver interval; all statuses are `BOUNDED_UNKNOWN` with
no external wall or RSS guard firing.

| Curve | Matrix policy | Selected matrices | Final conflicts | Restart rows | Solver wall s | Process CPU s | Peak RSS MiB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Source | default | five, largest 730 × 733 | 2,001 | 11 | 15.640 | 2.238 | 177.94 |
| Source | selector window | one 7,380 × 7,524 | 2,003 | 11 | 13.475 | 2.168 | 233.52 |
| Source | largest only | one 17,665 × 27,342 | 2,002 | 11 | 147.364 | 19.902 | 656.77 |
| Source | all five | one 17,665 × 27,342 plus four 9,061 × 13,883 | 2,002 | 11 | 157.502 | 21.472 | 1,103.31 |
| Descendant | default | five, largest 875 × 931 | 2,002 | 11 | 11.013 | 1.599 | 186.69 |
| Descendant | selector window | one 7,380 × 7,524 | 2,001 | 11 | 15.984 | 2.380 | 237.42 |
| Descendant | largest only | one 17,754 × 27,561 | 2,002 | 11 | 166.089 | 20.810 | 621.78 |
| Descendant | all five | one 17,754 × 27,561 plus four 9,061 × 13,883 | 2,002 | 11 | 151.578 | 23.814 | 1,091.16 |

On the source, largest-only and all-five have byte-identical printed restart
rows through the common cap, while all-five used **1.680×** the sampled peak
RSS. On the descendant, all-five used **1.755×** the largest-only peak RSS,
and their printed restart rows first diverged at row five. This is evidence
about the printed search trajectory and memory in one run, not identical
internal execution or an efficacy advantage. Selector-window and default
printed different restart rows on both curves, yet neither produced a model
within the cap. The host lacks an isolated-benchmark receipt, so wall and
process-CPU numbers are exploratory solver-stage measurements without a
controlled timing ratio or uncertainty interval. Formula construction and
factor-base preparation are outside these solver intervals; no final matrix
rank, target descent, or one-target IC/rho interval was measured here.

The selector component can be targeted reproducibly, but matrix selection
alone did not meet the gate for held-out promotion. The next implementation
should propagate exact leaf coordinates **when a selector becomes assigned**:
for W24 mask `s`, derive `w(s)`, `u(s)=halftrace(w(s))`,
`z=w(s)^(-1)`, and `x=alpha+alpha/u(s)`, then apply the resulting x/z units
inside a bounded branch or custom propagation policy. Begin with the four
archived full-x controls without supplying archived x values, and then use
frozen ordinary queries with all branch preparation, failed attempts,
verified relations, and novel rank charged. A simple fixed-mask scan needs
its own support and cost bound before scaling. Keep the `selector_window`
setting as a reproducible comparison arm, not a selected IC candidate.

Replay the complete archive audit with:

```sh
python3 -B experiments/ecc2k130-263-gauss-components-20261010/audit.py --write
```
