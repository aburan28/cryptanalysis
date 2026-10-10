# Q1426: ordinary target-lift slices for the four-leaf S3 root hybrid

Q1425's two-pair external-root formula did not return a first SAT model on
its ordinary N53 or N83 queries under the frozen cap. Q1426 tests whether
the SAT-selected public-target preimage is the immediate bottleneck. It
reuses Q1425's exact four-variable-leaf formula and exact S3 root oracle,
but builds one formula per fixed raw target lift. A one-choice selector is
forced to zero by the existing encoder; no known decomposition is supplied.

The N53 public point has 428 raw target lifts. Four lift indices are chosen
without replacement by a frozen SHA-256 stream keyed by proposal ID, curve
ID, and workload ID, independently of the archived known representation.
Those four cells are an ordinary-target diagnostic, not a complete query
over all 428 lifts. The N83 ordinary public point has four lifts; all four
are run. Each lift has four variable leaves and both pair intermediates
free. The two pair S3 links are deferred to Q1425's exact incremental
root lemmas; the outer S3 link remains a factored native-XOR SAT formula.

Q1426 is a point-decomposition proposal: `candidate_id: null`,
`run_id: null`, `isogeny: "none"` (`ISO0`). N53 uses
`EC1N53Ckb1hf77aab617904`, Q1301 W≤3, B=24,062 exact usable subgroup
points before folding, K=227 columns, workload `74f2979b3e68`. N83 uses
`EC1N83Ckb1h876c2921cb64`, Q1325 W≤5, B=30,977,592, K=186,612,
workload `bab50a1e5f66`. Source, input, library, target-lift x values,
and limits are hashed in `freeze.json` before measured calls.

One SAT thread and at most 90 seconds of target-dependent wall time are
allowed per lift, with at most 17 incremental solve calls, 16 root
refinements, 100,000 conflicts and 25 CPU seconds per call. A returned
`BOUNDED_UNKNOWN` is censored search evidence. The C API does not provide
the exact conflict count or identify which limit ended a call. Any SAT
model is checked against all original CNF/XOR rows and added root lemmas.
Accepted relations additionally require exact base membership, four
distinct folded columns, group-sum verification, and an independent Sage
replay before being used as ordinary-yield evidence. Each receipt records
exclusive phase clocks, root-field API calls, memory, and SHA-256 traces.

The comparison to Q1425 is same target/base/hardware, but target lift is
now fixed per cell. A claim about a complete ordinary query must charge all
queried lifts and cannot divide by the number of lifts. No N131 full-work
exponent is fitted from capped cells or a selected subset of lifts.
