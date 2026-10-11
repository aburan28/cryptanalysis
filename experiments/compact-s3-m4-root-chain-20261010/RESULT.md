# Exact root-chain completion at N53 and N83

Q20261010172500 completes the balanced four-summand S3 chain from three
fixed leaf x coordinates and one fixed raw target-preimage x using seven
quadratic root calls. Each degree produced eight algebraic fourth-leaf
candidates. Exact factor-base and signed curve checks selected one verified
four-point relation per degree. The independent replay audit passes for both
run receipts.

| Curve | Base `B` | Folded `K` | Raw root paths | Exact-base hits | Verified relations | Root calls | Counted `inv/mul/sqr/frob/trace` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `EC1N53Ckb1hf77aab617904` | 24,062 | 227 | 8 | 1 | 1 | 7 | `7/56/14/189/7` |
| `EC1N83Ckb1h876c2921cb64` | 30,977,592 | 186,612 | 8 | 1 | 1 | 7 | `7/56/14/294/7` |

| Degree | Root chain seconds | Base loading seconds | Candidate checks seconds |
| ---: | ---: | ---: | ---: |
| 53 | 0.00331 | 0.00053 | 0.15481 |
| 83 | 0.00262 | 0.28961 | 0.54775 |

Times are exploratory on a contended host. The root-call counts include
only operations routed through the counted oracle. The timed root-chain
interval also includes S3 equation replay and field conversions; candidate
checks include rational-point, subgroup, exact-base, and signed group-law
verification. Base loading is a separate reusable stage. The SAT comparison
is a completion-status comparison: Q20261010171000's matched three-fixed-
leaf XCNFs reached a 60-second cap under default and Gaussian settings at
both degrees, while the explicit root chain finished these conditional
instances. It is not an isolated CPU speedup measurement.

The fixed three leaves come from archived witnesses. This proves exact
conditional completion of the S3 constraints and verifies the returned
relations; ordinary-query relation yield, novel rank, and degree-131
collection cost require separate measurements. A random three-leaf search
would still need the fourth leaf to land in the exact base, so this result
does not by itself supply the free-leaf pair search required by the IC
pipeline.

The proposal retains `candidate_id: null`, `run_id: null`, and
`isogeny: "none"` (`ISO0`). The freeze SHA-256 is
`f04d45966ba2a2574bf90998dcc8c909fa5791e4c1fba2f33016adb20e9177fa`.
The saved `audit.json` records both PASS rows. Move it aside before
rerunning `python3 audit.py`, which refuses to overwrite its output.

Next, use the two-root first-pair enumeration with two free leaves and an
exact pair lookup, then compare that target-local search with the matched
Q1400/Q1416 pair-index work model on identical curve, base, and target
records. Charge pair-index construction, probes, relation verification,
rank novelty, matrix solving, and target descent before assigning any
complete-solve exponent.
