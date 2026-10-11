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

## Degree-131 work screen for two fixed leaves

For a target-independent choice of the first two base points and a uniform
nonidentity subgroup target, at most `C(B+1,2)` unordered pairs can complete
that choice. On the exact N131 W<=6 base, `B=6,559,634,788`,
`K=25,036,774`, and subgroup order
`r=680564733841876926932320129493409985129`. Thus the expected pair
representations per fixed-pair query are at most
`C(B+1,2)/(r-1) = 3.16126e-20`. Even if every match is found and every
relation adds rank, reaching expected rank `K` needs at least
`ceil(K(r-1)/C(B+1,2)) = 791987786991768740772708352` such queries,
or `2^89.36` queries. This is **28.36 exponent bits** above `2^61`
before any pair lookup, factor-base construction, matrix work, or target
descent. It is a necessary query-count screen for this target-independent
fixed-pair law, not a complete-solve work estimate. Target-guided first-pair
selection is outside the bound and requires its own measured input law.

The proposal retains `candidate_id: null`, `run_id: null`, and
`isogeny: "none"` (`ISO0`). The freeze SHA-256 is
`f04d45966ba2a2574bf90998dcc8c909fa5791e4c1fba2f33016adb20e9177fa`.
The saved `audit.json` records both PASS rows. Move it aside before
rerunning `python3 audit.py`, which refuses to overwrite its output.

The next search should test target-guided first-pair selection on frozen
ordinary N53/N83 queries, with the exact pair lookup and the matched
Q1400/Q1416 pair-index model as controls. Measure verified relation yield
and novel rank, including zero-yield cells, before extrapolating. Charge
index construction, probes, relation verification, final matrix solving,
and target descent before assigning a complete-solve exponent.
