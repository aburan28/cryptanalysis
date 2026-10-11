# Parity-flattened XCNF for the N131 W18 eight-pair resultant

Inlining unshared linear IR nodes reduces the frozen public-target formula
from **479,809 to 303,658 variables** and from **287,038 to 112,459 native
XOR rows**, while preserving the exact W18 source BDD, three nondegenerate
two-link resultants, and public target. The constructed witness passes an
independent audit of all 470,235 CNF clauses and 112,597 XOR rows. The
ordinary and two witness-unpinned searches reached their declared wall caps;
each is `BOUNDED_UNKNOWN`.

The instance uses `GF(2)[t]/(t^131+t^13+t^2+t+1)`, curve
`y²+xy=x³+1`, and prime subgroup order
`680564733841876926932320129493409985129`. The fixed-seed W18 source has
33,191 admissible pair codes per slot, 1,062,112 usable factor-base points
before folding, and 66,318 folded columns. Eight slots use Frobenius
rotations `0,16,...,112`. The ordinary workload is the same one-target
public point `cc09e7eb202a`, with raw preimage index 0, as the
[source encoding](../n131_w18_two_link_resultant_20261010/RESULT.md).

The [emitter](flat_emit.py) represents an XOR expression as a set of variable
literals plus one parity bit. It substitutes an XOR node when that node has
one live consumer, cancels repeated terms, and materializes one native XOR
row at a shared node or nonlinear operand. It asserts root parities directly.
Nonlinear AND gates, the positive-polarity source BDD, nonzero resultant
denominators, and target inputs retain the prior semantics. The
[builder](build_flat_formula.py) hash-checks all comparison sources before
emission. An [exhaustive small-DAG check](flat_emit_check_result.json)
compares this emitter, the original Tseitin emitter, and direct IR evaluation
on 128 complete assignments across two graphs, including 42 satisfying
assignments; every result agrees. The [constructed model audit]
(constructed_audit_result.json) independently checks the entire XCNF and
recovers the eight pinned source pairs and three retained intermediates.

| Frozen ordinary formula | Three-resultant Tseitin | Parity-flattened |
| --- | ---: | ---: |
| Variables | 479,809 | **303,658** |
| CNF clauses | 470,230 | **468,658** |
| Native XOR rows | 287,038 | **112,459** |
| Serialized bytes | 16,116,753 | **12,739,250** |

The [ordinary build](flat_ordinary_build.json) records 181,364 inlined
unshared XOR nodes and a maximum emitted parity length of 38 terms. The
source and target hashes match the prior [ordinary build]
(../n131_w18_two_link_resultant_20261010/resultant_ordinary_build.json).
Formula size is an encoding measurement, not a solver or IC timing win.

| Search, one CryptoMiniSat5 worker | Wall cap | Recorded result | Peak child RSS |
| --- | ---: | --- | ---: |
| [Constructed pinned control](constructed_solver_result.json) | 75 s parent | SAT in 0.274 s; independently audited | 95,895,552 B |
| [Ordinary public target](ordinary_solver_result.json) | 615 s parent | `PARENT_TIMEOUT` at 615.074 s | 319,094,784 B |
| [Constructed target, 1,577 pins removed](unpinned_solver_result.json) | 135 s parent | `PARENT_TIMEOUT` at 135.045 s | 287,375,360 B |
| [Same unpinned target, medium XOR matrices](gauss_unpinned_solver_result.json) | 135 s parent | `PARENT_TIMEOUT` at 135.060 s | 601,538,560 B |

The [pin-removal receipt](unpinned_build_result.json) verifies that exactly
the 1,577 constructed witness unit clauses were removed and that the target
and every arithmetic row were retained. This formula is satisfiable by the
independently checked pinned witness. The ordinary solver's last logged
restart line has about 2.205 million conflicts; the default and medium-matrix
unpinned runs have about 329,000 and 644,000 respectively. These counters and
wall times are search diagnostics on an unisolated host.

The default solver discarded three 8,625-by-16,979 XOR components. The
[medium-matrix protocol](gauss_unpinned_solver_protocol.json) raised the
row/column limits to 10,000/20,000 and the matrix count to eight, while
retaining the one-worker, 4-GiB RSS, and 135-second parent envelope. Its
log confirms that the three components were admitted and the much larger
component was excluded. This bounded search did not clear the unpinned
constructed control. An [ordinary medium-matrix protocol]
(gauss_ordinary_solver_protocol.json) was frozen but not executed after this
control reached its cap. The prepared [ordinary model audit](audit_ordinary.py)
and [checked-Sage replay](replay_ordinary_model.py) apply if a future search
returns a model. The next method experiment should couple target handling
and source propagation, including all four public-target preimages, before
another long N131 search. Relation yield and useful rank are the immediate
pipeline measurements after an ordinary model is independently replayed.
