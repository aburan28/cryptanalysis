# Degree-263 route passes the complete exceptional-input replay

The exact first descending route `IW1E263d1hadee4e69fa3d` now has a fresh
checked-Sage confirmation of its forward and oriented dual maps at every
geometric kernel point. All **262 nonzero forward** and **262 nonzero dual**
kernel points mapped to the corresponding identity, while infinity,
rational order-two torsion, the saved generator, and the public-point fixture
passed their map and dual-composition checks. The static verifier bound the
same map artifacts to catalog edge `e263d1_df508c4fc9a8` and curve IDs
`EC1N131Ckb1h136f03e58c98` and `EC1N131Cbinh833014327b07`.
The [semantic audit](runs/R1/audit.json) matched every non-timing field of
the new receipt to the archived receipt. This closes the catalog's stale
exceptional-input transport gate for this route; the next equal-useful-base
question is natural PDP relation yield and useful rank.

| Checked item | Fresh R1 result |
| --- | --- |
| Forward kernel roots / nonzero points | 131 / 262, all mapped to identity |
| Dual kernel roots / nonzero points | 131 / 262, all mapped to identity |
| Base-field lift of kernel points | None; each root's y equation has trace one |
| Infinity and rational order-two controls | Passed on source and target |
| Ordinary and quadratic-extension point-map agreement | Passed |
| Oriented dual composition on saved subgroup points | Passed |
| Archived semantic receipt comparison | `PASS_SEMANTIC_REPLAY` |
| Static route-manifest verification | Passed, exact edge and hashes |

The frozen protocol and source/input hashes were pushed at `15a838ef5`
before the successful replay. The run used the repository's checked Sage
10.10.rc0 launcher and saved [runtime information](runs/R1/runtime.stdout)
before arithmetic. The [status receipt](runs/R1/status.json) binds the
commands, source commit, exit codes, raw stdout/stderr hashes, and the new
[Sage receipt](runs/R1/sage_receipt.json). Every step exited zero. The
external Sage process took 58.855 seconds; the receipt's internal total was
56.941 seconds. These elapsed values are unisolated correctness-run costs,
not a CPU comparison. The source, map controls, route manifest, registry,
archived receipt, and verification scripts match the eight SHA-256 entries
in [FROZEN.json](FROZEN.json).

The raw Sage affine evaluator raised `ArithmeticError` on one point from
each kernel because the kernel denominator vanishes. The checked
`evaluate_with_kernel` wrapper returns the codomain identity at those
points; the replay checked the wrapper on all 524 nonzero kernel inputs.
The first launch attempt stopped before Sage at a mistyped frozen source
digest. Its [failure receipt](preflight_attempt1.json) is retained; the
corrected digest was committed and pushed before R1.

The verified route manifest still has `candidate_id: null`. The equal-size
W24 and normal4 policy inputs are already frozen, but their ordinary-query
PDP searches have bounded unknown outcomes. The next N131 measurement is a
relation-producing PDP on those held-out policies, followed by verified
novel rank and the full single-target accounting; this transport replay
supplies the exceptional map prerequisite for that comparison.

Reproduce the semantic audit without rerunning Sage:

```sh
python3 experiments/ecc2k130-263-exceptional-audit-20261010/audit.py
```
