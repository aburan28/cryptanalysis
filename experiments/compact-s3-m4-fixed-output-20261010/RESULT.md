# Q1429: fixed-output S3 specialization cuts nonlinear gates threefold

The Q1428 outer root is a known constant before the right-pair SAT
formula is built. Q1429 substitutes that constant into the S3 link,
reducing N53 nonlinear AND gates from 8,427 to 2,809 and N83 gates
from 20,667 to 6,889. Both fixed-output encodings also remove about
65% of CNF clauses. Pinned true and false-output controls pass at both
degrees for every encoding. In the paired free-leaf grid, all twelve
known-output and ordinary-output calls returned `BOUNDED_UNKNOWN`
under the frozen caps.

## Exact inputs and formula shapes

Q1429 is an `ISO0` proposal with null candidate and run IDs. It reuses
Q1428's exact curves, bases, one-target workloads, known-solution
fixtures, and ordinary anchor-0 first outer-root output. N53 uses
`EC1N53Ckb1hf77aab617904`, Q1301 W≤3, B=24,062 usable subgroup
points, K=227 signed-Frobenius columns, workload `74f2979b3e68`.
N83 uses `EC1N83Ckb1h876c2921cb64`, Q1325 W≤5,
B=30,977,592/K=186,612, workload `bab50a1e5f66`. Exact source,
input, output-root, base, binary, and limit digests are in
[`freeze.json`](freeze.json), committed before the paired measurements.

| Degree | Encoding | Variables | CNF clauses | XOR rows | AND gates |
| --- | --- | ---: | ---: | ---: | ---: |
| N53 | variable output, factored | 9,111 | 26,006 | 265 | 8,427 |
| N53 | fixed output, factored | 3,440 | 9,152 | 265 | 2,809 |
| N53 | fixed output, direct | 3,440 | 9,152 | 265 | 2,809 |
| N83 | variable output, factored | 22,069 | 63,798 | 415 | 20,667 |
| N83 | fixed output, factored | 8,208 | 22,464 | 415 | 6,889 |
| N83 | fixed output, direct | 8,208 | 22,464 | 415 | 6,889 |

The two fixed forms have identical size but different XOR wiring. A
variable output uses SAT assumptions to select the same frozen value.
The fixed forms encode that value as Boolean constants, so the `xv`,
`yv`, and `(xy)v` products become linear while `xy` remains nonlinear.

## Paired solver work

Each cell used one CryptoMiniSat thread, one call, at most 10 CPU
seconds, 100,000 conflicts, and 30 target-dependent wall seconds.
The known-output control chooses the fixture's right-pair output but
leaves both right coordinates free during measurement. Ordinary rows
use the first deterministic outer-root branch of Q1428's anchor 0 on
the frozen public target. Each three-encoding row group has the same
curve, base, target, anchor, output value, and resource limits.

| Degree/input | Encoding | Target PDP wall s | Exact conflicts | Result |
| --- | --- | ---: | ---: | --- |
| N53 known output | variable factored | 30.837 | 46,598 | `BOUNDED_UNKNOWN` |
| N53 known output | fixed factored | 30.386 | 53,955 | `BOUNDED_UNKNOWN` |
| N53 known output | fixed direct | 30.382 | 19,455 | `BOUNDED_UNKNOWN` |
| N53 ordinary output | variable factored | 30.152 | 48,385 | `BOUNDED_UNKNOWN` |
| N53 ordinary output | fixed factored | 14.746 | 100,002 | `BOUNDED_UNKNOWN` |
| N53 ordinary output | fixed direct | 30.129 | 41,472 | `BOUNDED_UNKNOWN` |
| N83 known output | variable factored | 30.107 | 11,521 | `BOUNDED_UNKNOWN` |
| N83 known output | fixed factored | 30.636 | 14,595 | `BOUNDED_UNKNOWN` |
| N83 known output | fixed direct | 30.042 | 6,424 | `BOUNDED_UNKNOWN` |
| N83 ordinary output | variable factored | 30.114 | 34,528 | `BOUNDED_UNKNOWN` |
| N83 ordinary output | fixed factored | 14.662 | 44,800 | `BOUNDED_UNKNOWN` |
| N83 ordinary output | fixed direct | 22.739 | 22,530 | `BOUNDED_UNKNOWN` |

The fixed-factored N53 ordinary call exhausted its configured conflict
allowance. Other early stops may reflect the CPU limit; the solver API
does not expose the exact stop cause. Conflict counts and wall times
are stage diagnostics with differing stop conditions on an unisolated
host. The receipts retain exact native propagations and decisions,
anchor selection, outer-root field API counts, formula build/load,
SAT, relation-check clocks, and process peak RSS. The exclusive phase
clocks sum to the charged target-dependent PDP interval. The 12 cells
cover one output each, so they are bounded branch tests rather than
complete one-target queries.

[`test_formula.py`](test_formula.py) pinned known right coordinates and
verified every true output with a SAT model and exact four-point group
relation. It also checked a deliberately false output, including
root-level contradictions. [`verify.py`](verify.py) replayed all 12
source-bound receipts, their frozen input IDs and root joins, formula
shapes, native counters, phase sums, and trace hashes. The initial
control-loader failure and unused freeze are preserved in
[`pilot_v1`](pilot_v1/README.md); the version-2 freeze precedes all
measurements reported here.

## Complete-work distance and next gate

Q1429's complete N131 cold and one-target-online work exponents are
`null`. A threefold smaller nonlinear circuit has not yielded a
completed free-leaf solve at N53 or N83, so these cells cannot supply
ordinary relation probability, cost per novel rank row, final matrix
work, target descent, or scalar replay. The separate
[Q1422 explicit-index model](https://github.com/aburan28/cryptanalysis/pull/625)
has an exact-base floor of `2^88.356` logical actions, 27.356 bits
above `2^61`; its action unit and method family differ from this SAT
grid. Neither figure is a complete-work estimate for Q1429.

The next solver gate should use the exact S3 root oracle during
free-leaf search, or a bounded partial pair index, rather than only
after SAT returns a full model. On the same N53/N83 target/base pairs,
vary indexed state count and root batching under a fixed memory cap,
then record verified ordinary relations, novel rank rows, and all
failed probes in a common operation unit. The N83 ordinary relation
and rank result is the decisive gate before an N131 `2^x` fit.
