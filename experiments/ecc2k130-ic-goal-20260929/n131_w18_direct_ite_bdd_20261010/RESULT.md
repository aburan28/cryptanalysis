# Direct-CNF source decisions for the N131 W18 eight-pair circuit

Replacing the source BDD's XOR/AND mux with a direct Tseitin if-then-else
decision reduces the ordinary N131 W18 four-product formula by 203,840
variables and 203,888 native XOR rows. The exact source and arithmetic IR
are unchanged. The constructed formula is satisfiable, and an independent
stream audit checks every CNF clause and native XOR row in its model. The
same public target reaches `PARENT_TIMEOUT` under the frozen ordinary cap.

The field is `GF(2^131)` with modulus `t^131+t^13+t^2+t+1`, the curve is
`y^2+xy=x^3+1`, and the prime subgroup order is
`680564733841876926932320129493409985129`. The source is the fixed seed
212 in the W18 span, with eight Frobenius rotations `0,16,...,112`, 33,191
valid unordered source pairs per slot, 1,062,112 actual usable base points
before folding, and 66,318 folded columns. The [W18 source preflight](../n131_fixed_seed_eight_pair_circuit_20261010/pair_preflight_result.json)
exhaustively checks the original 17-bit source BDD against all 131,072 codes;
its geometry and source support are recorded in the corresponding prior
experiment. The [new gate](ite_bdd.py) implements each nonconstant BDD
decision with four implication clauses and folds terminal branches to a
literal or a two-input AND/OR. Its nonconstant four-clause truth table is
checked over every switch, low, high, and output bit combination before each
[formula build](build_formula.py).

| Ordinary formula | Original XOR/AND BDD | Direct-CNF ITE BDD | Change |
| --- | ---: | ---: | ---: |
| Variables | 811,425 | 607,585 | -25.12% |
| CNF clauses | 688,202 | 789,378 | +14.70% |
| Native XOR rows | 580,716 | 376,828 | -35.11% |
| Serialized bytes | 26,716,090 | 24,778,904 | -7.25% |

The table compares the [prior frozen W18 formula](../n131_reciprocal_s3_fourmul_20261010/fourmul_ordinary_build.json)
with the [new frozen formula](ite_ordinary_build.json). Both use the same
517,242-operation eight-pair four-product arithmetic IR, source seed, public
target preimage, and decoder; only the BDD gate changed. The constructed
formula's [solver receipt](constructed_solver_result.json) records a SAT
model, and the [independent audit](constructed_audit_result.json) checked all
791,348 clauses and 377,322 XOR rows and recovered the eight pinned source
pairs and intermediate reciprocal coordinates. The constructed solve timing
is an exploratory correctness diagnostic on this host.

The [ordinary protocol](ordinary_solver_protocol.json) freezes one
CryptoMiniSat5 worker, a 600-second solver cap, a 615-second parent cap, and
4 GiB peak RSS for the same public target workload `cc09e7eb202a`. The
[ordinary result receipt](ordinary_solver_result.json) and
[search log](ordinary_solver.stdout.txt) record `PARENT_TIMEOUT` at
615.087 seconds, 393,297,920 bytes peak child RSS, and about 569,000 logged
conflicts. The solver did not emit a terminal status before the parent cap;
the mathematical result is `BOUNDED_UNKNOWN`. A source-valid ordinary model
would require the prepared independent XCNF auditor and checked-Sage curve
replay. Candidate identity and downstream relation yield, rank, factor-log,
and same-point rho fields remain open. A polarity-aware source BDD encoding
is the next exact gate to compare on this workload.
