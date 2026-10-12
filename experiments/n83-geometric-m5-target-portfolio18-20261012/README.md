# Fixed raw-target portfolio on the width-18 N83 base

The Q55 portfolio tested twelve frozen raw cofactor-preimage/Frobenius
slices of one public target against the complete shifted width-18 factor
base. All twelve attempts reached their individual time limits; the
600.655-second target-dependent PDP interval has stage status
`bounded_unknown`. The experiment preserves every native-XOR formula,
solver output, timeout and phase cost in
[portfolio_ordinary.json](portfolio_ordinary.json).

The [protocol](protocol.json) fixes the same curve, public point and
`df4396f4d8fc` workload used by Q54; the exact base has
**B = 21,714,958 usable subgroup points before folding** and
**K = 130,813 signed-Frobenius columns**. It retains Q54's power-basis
Karatsuba S₃ circuit, one CryptoMiniSat thread, 4 GiB sampled solver RSS
stop and five-million-conflict per-solver cap. The sole variable is the
fixed raw-target slice. The target-generation scalar is represented only
by its SHA-256 commitment and is not read by the portfolio.

| Frozen choice sequence | Per-choice limit | Native status | Model |
| --- | ---: | --- | --- |
| 1, 2, 3, 4, 5, 7, 11, 19, 37, 73, 147 | 50 seconds each | `external_timeout` for each | none |
| 267 | 36.7 seconds, remaining total budget | `external_timeout` | none |

The online interval starts before target-dependent raw preimage
construction and includes every formula build, XCNF write, solver
attempt, result check and per-attempt archival. Its exclusive phase
totals are 0.132 seconds for target preimages, 2.266 for formula builds,
0.917 for XCNF writes, 586.911 for solver calls, less than 0.001 for
relation checks, and 10.429 for other target-dependent work. Archival
and process handoff cause the measured interval to exceed the nominal
600-second dispatch deadline by 0.655 seconds; the final solver interval
was shortened to 36.727 seconds. Local CPU timings are exploratory.

The formula shape is 12,174 AND gates and 105,251 CNF clauses for every
slice. The width-18 base and canonical-x cache are hash-bound to the
[Q54 experiment](../n83-geometric-m5-karatsuba18-20261012/README.md).
Q54's locked five-point control returned SAT and passes
[independent Sage group replay](sage_relation_replay.json); Q55's receipt
verifier checks the frozen source and solver, the public workload, all
twelve compressed formulas and stdout/stderr digests, and complete phase
accounting.

Run the read-only receipt check from the repository root:

```sh
python3 experiments/n83-geometric-m5-target-portfolio18-20261012/verify.py
```

The checked Sage launcher saved [runtime identity](sage_runtime_info.json)
before the portfolio run. Reproduce a new run in a fresh output directory;
the producer refuses to overwrite this terminal result.
