# One W18 resultant formula for all four raw preimages of the N131 public point

The four raw preimages of the same ECC2K-130 public point admit an exact
two-bit affine reciprocal-coordinate selector. This allows one
target-conditioned W18 eight-pair formula to search all four lifts instead
of fixing raw preimage 0. The constructed control solved and passed an
independent full-formula audit. The ordinary public-target search and a
known-satisfiable witness-unpinned control both reached their declared caps.

The field is `GF(2)[t]/(t^131+t^13+t^2+t+1)`, the curve is
`y²+xy=x³+1`, and the prime subgroup order is
`680564733841876926932320129493409985129`. The source is the same
fixed-seed W18 policy and eight Frobenius rotations `0,16,...,112` as the
[parity-flattened single-preimage experiment]
(../n131_w18_parity_flatten_20261010/RESULT.md): 33,191 admissible pair
codes per slot, 1,062,112 usable base points before folding, and 66,318
folded columns. The ordinary target and workload `cc09e7eb202a` are unchanged.

For ordered reciprocal coordinates `z₀,z₁,z₂,z₃` of the four raw lifts,
the [checked-Sage target receipt]
(../n131_fixed_seed_eight_pair_circuit_20261010/target_preimages.json)
gives `z₁=z₀+1` and `z₃=z₂+1`. With `Δ=z₀+z₂`, choice bits
`a,b∈GF(2)` select `z(a,b)=z₀+a+bΔ`; index `a+2b` ranges over every
preimage. The [builder](build_four_formula.py) asserts this four-entry truth
table against both the ordinary and constructed target receipts before
emitting constraints. The ordinary target's four-preimage computation took
5.934 ms in its original receipt; a future complete online interval must
charge that target-dependent work.

The [constructed target preparation](planted_preimages_result.json), run
through the checked repository Sage launcher with its saved
[runtime receipt](sage_runtime_info.json), independently rebuilt the curve,
added all four order-four torsion offsets to the audited raw eight-pair sum,
and checked that every lift projects to the same public point. The
[choice circuit control](choice_circuit_result.json) evaluates the frozen
eight-pair witness against the four selected reciprocal targets: its failed
root-bit counts are `0,1,71,70`. The pinned constructed formula solved, and
its [independent model audit](constructed_audit_result.json) checked all
483,983 CNF clauses and 113,449 native XOR rows, including the two choice
bits, eight exact source pairs, and three retained intermediates.

| Ordinary formula | Fixed preimage 0 | Four-preimage selector |
| --- | ---: | ---: |
| Variables | 303,658 | **309,146** |
| CNF clauses | 468,658 | **482,260** |
| Native XOR rows | 112,459 | **113,411** |
| Serialized bytes | 12,739,250 | **13,033,080** |

The [four-preimage ordinary build](four_ordinary_build.json) and
[single-preimage comparison](../n131_w18_parity_flatten_20261010/flat_ordinary_build.json)
bind the exact source and target hashes. The
[ordinary solver protocol](ordinary_solver_protocol.json) fixes one
CryptoMiniSat5 worker, 600 seconds solver time, 615 seconds parent wall, and
4 GiB RSS. The [ordinary search receipt](ordinary_solver_result.json) records
`PARENT_TIMEOUT` after 615.022 seconds, with 271,564,800 bytes peak child
RSS and about 772,000 conflicts on the last logged restart line. Its status
is `BOUNDED_UNKNOWN`; the cap supplies neither a model nor an
unsatisfiability certificate. A returned model must pass the prepared
[full XCNF audit]
(audit_ordinary.py) and [checked-Sage group replay]
(replay_ordinary_model.py), including its selected raw lift and projection
to the public target.

The [witness-pin removal](unpinned_build_result.json) removes exactly 1,579
unit clauses: two preimage-choice pins and 1,577 source/intermediate witness
pins. It retains all four target choices and every arithmetic constraint.
Its separately frozen [known-satisfiable solver control]
(unpinned_solver_protocol.json) ran after the ordinary search so the two jobs
did not contend for the host. Its [receipt](unpinned_solver_result.json)
records `PARENT_TIMEOUT` after 135.086 seconds, with 377,339,904 bytes peak
child RSS and about 211,000 conflicts on the last logged restart line. The
independently audited pinned assignment proves this unpinned formula is
satisfiable. The two bounded searches show that adding the exact four-lift
choice has not cleared the N131 search gate with this solver and budget.
Relation yield, rank novelty, factor logs, and a one-target IC/rho comparison
remain subsequent pipeline stages; a target-coupled decomposition method is
the next algorithmic gate.
