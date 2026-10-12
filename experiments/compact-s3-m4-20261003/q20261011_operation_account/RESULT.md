# Q1436: exact field API work vector for bounded S3 searches

Q1436 counts every executed public `Onb` field method entry during compact
four-summand SAT search. It covers pair-root queries, target-coset support,
final-link checks, rationality tests, conversions, and the field operations
performed by their executed assertions. On the frozen ordinary N53 public
point, the solver consumed **712,014 field API method entries
(\(2^{19.44}\))** before its 5,000-conflict cap. The matching N83
`allpos` row consumed **810,656 entries (\(2^{19.63}\))** at that cap.
Both have recorded status `BOUNDED_UNKNOWN`.

The N83 `pair1spread` row shows why pair-root queries cannot stand in for
work: it made only 933 pair-root queries but consumed **687,304 API entries
(\(2^{19.39}\))** before its 30-second wall cap. Its 25 early target
support states and 3,674 final-link checks contributed work outside the
pair-root counter.

## Count boundary

`CountedOnb` subclasses the accepted repository `field.Onb` and counts
entries into `fromCoords`, `toCoords`, `add`, `mul`, `sqr`, `frob`, `inv`,
`trace`, `one`, `zero`, and `pow`. An inherited method calling another
public method through `self` records **both method entries**. For example,
one call to `sqr` enters `sqr` and its nested `frob`; the sum is a count
of software API events, not a field-multiplication equivalent. Low-level
bit operations inside a method are outside this vector. The count starts
after the field object is constructed and immediately before
`solver.solve()`; startup counts are reset. It stops when that solve
returns. The measured code includes executed root-oracle assertions.

CNF loading, construction of the raw target x-coordinate coset,
factor-base/index preparation, final relation-matrix construction and
solve, target descent, and scalar replay are outside this stage counter.
Keep the separate method vector and conversion count when calibrating to
another arithmetic implementation or rho. `api_method_entry_events` is
therefore a named, exact diagnostic unit; it is not an end-to-end cost.

## Ordinary measurements

All rows use the exact Q1410 N53 or Q1408 N83 ordinary public point,
actual factor base and target coset, `satpivot`, Q1435 symmetric target
support, `eager` leaf mode, a 5,000-conflict cap, and a 30-second wall
cap. N53 is `EC1N53Ckb1hf77aab617904` with B=24,062 and K=227;
N83 is `EC1N83Ckb1h876c2921cb64` with B=30,977,592 and K=186,612.
Both use `isogeny: "none"`. The complete per-method vectors and raw
logs are in `measurements.json`.

| Field / policy | Status and stopping cap | Pair-root queries | Early / final checks | API events | Conversion entries | Add | Mul | Sqr | Frob | Inv | Trace |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 allpos | BOUNDED_UNKNOWN; 5,000 conflicts | 5,001 | 1 / 0 | 712,014 | 133,489 | 222,077 | 70,563 | 42,980 | 189,509 | 21,270 | 15,841 |
| N83 allpos | BOUNDED_UNKNOWN; 5,000 conflicts | 5,001 | 1 / 0 | 810,656 | 125,149 | 280,190 | 65,051 | 40,040 | 250,166 | 20,026 | 15,021 |
| N83 pair1spread | BOUNDED_UNKNOWN; wall 30 s | 933 | 25 / 3,674 | 687,304 | 80,060 | 256,069 | 61,191 | 30,133 | 227,827 | 11,305 | 6,598 |

The N53 ordinary workload has a verified four-point relation in its
matched pair-table receipt. Thus \(2^{19.44}\) API events are work spent
by this solver on a known-satisfiable query **before** its cap; they are
not a cost per successful decomposition. The N83 ordinary query's
decomposition status is unresolved under these bounds. CPU wall ratios
are exploratory on the unisolated host.

## Validation and challenge accounting

`validate.py` compares `CountedOnb` with the ordinary field object for
12 deterministic element pairs at each of degrees 11, 53, and 83,
including multiplication, inverse, trace, and exact S3 roots. It checks
that a square records its nested Frobenius call. Locked N53/N83 controls
produce independently replayed S3 models. Twenty-four archived
nonrational-leaf samples pass an independent trace calculation. The N53
ordinary row matches Q1435's uninstrumented solver **exactly** on
conflicts, propagations, decisions, pair-root queries, rationality checks,
rejections, and external clauses at the same 5,000-conflict cap. The
validation status is `PASS`.

The exact N131 W<=6 uniform-query supply bound leaves less than
\(2^{33.36}\) abstract work units per ordinary query under a
\(2^{61}\) total cap with every other cost set to zero. The Q1436 API
entry unit has not been calibrated to those work units, and none of its
ordinary searches completed a decomposition. Successful-query work,
natural relation yield, novel rank, final matrix cost, target descent,
and the fully charged N131 \(2^x\) projection therefore remain null.
The challenge gate is not met by these stage counters.

The next experiment should use the exact operation vector to benchmark a
query-level restart or guided first-pair search that reaches more than one
first-middle state, then attempt the known-satisfiable N53 ordinary
target. Preserve failed attempts and all API/phase costs. A verified N83
ordinary relation and measured novel-row rate are still needed before
fitting a degree-131 completion exponent.

## Reproduction

From the repository root, regenerate Q1430's frozen CNF/maps and Q1432's
target files as documented in their directories. Then run:

```sh
sh experiments/compact-s3-m4-20261003/q20261011_operation_account/build.sh /private/tmp/q1436_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_operation_account/run_measurements.py --binary /private/tmp/q1436_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_operation_account/validate.py --binary /private/tmp/q1436_insearch
```

`measurements.json` binds the C++ solver, counting subclass, underlying
field and S3 sources, executable, exact curve/workload/B/K/digest, CNF,
target coset, raw logs, caps, and status. `candidate_id` and `run_id`
remain null for this Q1436 PDP-stage proposal. The measured source is
isolated in this experiment directory and does not change the accepted
Sage or field implementation.
