# W18 cutoff-one circuit lowers nonlinear gate count on the N131 control

Changing the polynomial-basis Karatsuba leaf cutoff from three to one
reduces the eight-pair W18 arithmetic circuit's live **AND gates from
94,851 to 64,272**, a 32.24% reduction. The XOR count rises from
295,002 to 404,731. The full constructed formula solved, and an
independent auditor checked every CNF clause and native-XOR row of its
model. The known-satisfiable witness-unpinned search reached its frozen
135-second parent cap after 200 logged restarts. This is a concrete
lower-nonlinearity encoding and a bounded solver result; the ordinary
degree-131 relation gate remains open.

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. The source is the
same seed-212 W18 pair set, eight Frobenius rotations `0,16,...,112`,
33,191 admissible pair codes per slot, and four raw lifts of the same
constructed subgroup point as the prior
[four-preimage control](../n131_w18_four_preimage_20261010/RESULT.md).
Every arithmetic equation, source-membership BDD, and target selector is
unchanged; only the Karatsuba recursion's terminal leaf size changes.

| Exact circuit/formula measure | Cutoff three | Cutoff one |
| --- | ---: | ---: |
| Live arithmetic AND gates | 94,851 | **64,272** |
| Live arithmetic XOR gates | 295,002 | 404,731 |
| Total live arithmetic gates | 389,853 | 469,003 |
| Constructed XCNF variables | 309,232 | 346,595 |
| Constructed CNF clauses | 483,983 | 395,954 |
| Constructed native-XOR rows | 113,449 | 180,155 |

The [source-bound gate census](ir_result.json) rebuilt both full circuits,
verified all 1,572 constructed arithmetic roots for each, and checked 128
bit-parallel field products per cutoff against a separate polynomial-field
multiplier. Its [protocol](ir_protocol.json) freezes the circuit and field
sources. The [cutoff-one formula builder](build_formula.py) forces leaf
cutoff one at every polynomial multiplication, with its
[frozen source/input protocol](formula_protocol.json). Both serialized
formulas are retained as checked [constructed](four_constructed.xcnf.gz)
and [witness-unpinned](four_unpinned_constructed.xcnf.gz) gzip artifacts;
decompression hashes match their respective build receipts. Large
temporary solver inputs were decompressed to `/private/tmp` outside the
charged solver interval.

The pinned constructed formula solved in **1.629 s** under a one-worker,
30-second solver and 45-second parent cap. The
[independent model audit](constructed_audit_result.json) checked all 395,954 clauses and
180,155 XOR rows, reconstructed the eight archived source-mask pairs and
three retained intermediate coordinates, and matched the four checked
raw-target lifts. The earlier checked-Sage fixture independently verifies
the corresponding signed curve-point sum and cofactor-four projection.
The [pin-removal audit](unpinned_audit_result.json) confirms that the
witness-unpinned XCNF removes exactly 1,579 unit clauses and preserves all
394,375 remaining CNF clauses and 180,155 XOR rows byte-for-byte. The
audited pinned assignment therefore proves this unpinned control is
satisfiable.

| One-worker known-satisfiable control | Recorded outcome |
| --- | ---: |
| Solver / parent limits | 120 s / 135 s |
| Peak child RSS limit | 4,294,967,296 B |
| Parent wall | 135.094 s |
| Sampled peak child RSS | 150,896,640 B |
| Last logged restart | 200, near 56,000 conflicts |
| Search status | `PARENT_TIMEOUT`; no model or proof |

The [solver protocol](solver_protocol.json),
[run receipt](unpinned_constructed_solver_result.json), and
[raw log](unpinned_constructed_solver.stdout.txt) preserve the cap and search
activity. The [terminal audit](terminal_result.json) checks both compressed
formula digests, the constructed model audit, exact pin removal, solver
receipts, and restart evidence. These wall and memory observations come
from an unisolated host and are not a controlled timing comparison with
cutoff three. `PARENT_TIMEOUT` is censored search evidence, not an
unsatisfiability result.

The cutoff-one encoding changes the nonlinear/linear balance but does not
make a known-satisfiable unpinned N131 formula solve inside the short gate.
The ordinary public-point query was not launched for this variant. The
next algorithm should generate or eliminate target-compatible outputs
across multiple still-free pair domains, first recovering an unpinned N41
ordinary relation with independent group replay, then showing a complete
N131 work and RSS projection within one worker, 600 seconds, and 4 GiB.
Measure ordinary relation yield and novel matrix rank before factor-log
recovery and the paired single-target rho comparison. The complete
candidate and run IDs remain null at this stage.
