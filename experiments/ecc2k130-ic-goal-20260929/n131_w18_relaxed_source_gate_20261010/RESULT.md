# W18 eight-pair arithmetic search with source membership relaxed

Removing the exact source-membership gates while retaining the same N131
eight-pair reciprocal S3 arithmetic and public target produces an ordinary
XCNF with 502,889 variables, 374,250 CNF clauses, and 376,828 native XOR
rows. Relative to the source-bound positive-polarity formula, it removes
104,696 variables and 209,152 clauses; the XOR rows and 517,242-operation
arithmetic IR are identical. The constructed witness satisfies this relaxed
formula under an independent full-formula audit. The public-target search
reaches its parent cap.

The exact field is `GF(2^131)` under modulus `t^131+t^13+t^2+t+1`, the curve
is `y^2+xy=x^3+1`, and the prime subgroup order is
`680564733841876926932320129493409985129`. The target is preimage index 0
of one public workload `cc09e7eb202a`. Each of eight slots retains the 17
selector bits, 131-bit pair output, fixed seed 212 pair equation, and its
Frobenius rotation; all six intermediate reciprocal coordinates and seven
S3 links remain. The [builder](build_formula.py) omits only the source BDD
membership clauses. The [frozen build](relaxed_ordinary_build.json) asserts
the same target coordinate and arithmetic IR count as the
[source-bound comparator](../n131_w18_positive_bdd_20261010/positive_ordinary_build.json),
and exactly the same number of native XOR rows.

| Ordinary XCNF | Source-bound positive BDD | Relaxed source |
| --- | ---: | ---: |
| Variables | 607,585 | 502,889 |
| CNF clauses | 583,402 | 374,250 |
| Native XOR rows | 376,828 | 376,828 |
| Serialized bytes | 20,553,865 | 16,270,237 |

The constructed formula has a [SAT receipt](constructed_solver_result.json),
and its [independent audit](constructed_audit_result.json) checked all
376,220 clauses and 377,322 native XOR rows while recovering the eight
source pairs and six intermediate coordinates. Any ordinary SAT model will
first receive a full clause/XOR audit and a separate classification of its
eight selector codes against the frozen W18 source table. A source-valid
model then requires checked-Sage group replay on the public point.

The [ordinary protocol](ordinary_solver_protocol.json) freezes one
CryptoMiniSat5 worker, a 600-second solver cap, a 615-second parent cap, and
4 GiB peak RSS. The [ordinary receipt](ordinary_solver_result.json) and
[search log](ordinary_solver.stdout.txt) record `PARENT_TIMEOUT` after
615.059 seconds, 388,775,936 bytes peak child RSS, and about 969,000 logged
conflicts. The solver emitted no terminal status before the parent cap, so
the result is `BOUNDED_UNKNOWN`. This relaxation bounds the tested
formulation and solver under its resources; it does not attribute search
difficulty to one constraint family by itself. The next gate replaces pairs
of upper S3 links with nondegenerate resultants while restoring exact source
membership.
