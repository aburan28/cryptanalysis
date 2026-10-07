# Fresh one-target quotient-restart rho result

The quotient-valued scalar evaluator, rho wiring, unit tests,
independent affine fixture generator, checker, strict isolation
manifest generator, and protocol were frozen in `d1105ed5`. A new
public point `(2247774444, 1906310386)` and rho seed
`10479554034346068415` were generated and frozen in `de5cc6e9`
before any candidate solve. Each invocation began with an empty
distinguished-point table.

Both serial Release and UBSan panels pass. Generic rho, regular
unit-steered batch rho, and quotient-restart batch rho each recovered
scalar `7099595` and independently replayed it to the same public
point. All three share 6,014 equivalent group operations, 261 table
entries, eight table evaluations, and five restarts. The regular and
quotient modes share 1,104 prepared bytes, τ and mixed-add counts,
batch and restart inversions, recoding counts, and the same rho walk.

| One-target startup measure | Regular steered | Quotient restart |
| --- | ---: | ---: |
| Evaluation rotations | 19 | 18 |
| Restarts | 5 | 5 |
| Restarts with nonzero returned gauge | 0 | 1 |
| Additional coefficient multiplications | 0 | 0 |

The quotient evaluator returns `psi^(4g)(aG+bQ)` and a gauge tag
`g`. The rho class reducer applies `psi^k`, and the coefficients
receive one factor `lambda^((k+4g) mod 6)`. This is the same one
coefficient update the regular canonicalization needs. The batch
table remains exact; the final gauge correction is omitted only for
restart outputs that are canonicalized immediately. Unit tests check
this relation against generic group arithmetic on both curves,
including batched outputs and cancellation cases.

Release `online_ms` values in frozen order were
`0.672, 0.673, 0.610, 0.652, 0.605, 0.654` for generic, regular,
quotient, quotient, regular, generic. UBSan gave
`5.698, 5.477, 5.603, 5.611, 5.574, 5.452`. These short runs
lack host-wide CPU and NUMA isolation. Both raw panels preserve
`cpu_speedup_claim: null` and `isolation_receipt: null`; the
one-rotation saving is not a controlled CPU speedup. Separate
post-solve replay timing is retained in every raw row.

Release with `CA_WERROR=ON` passed all 16 CTest tests. UBSan
`curve` and `joint_tau` passed. The mode remains opt-in. The
quotient-output format is only useful when the consumer accepts an
automorphism representative and the gauge tag. Academic novelty and
automatic routing remain open.
