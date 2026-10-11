# Q20261010172500: exact S3 root-chain completion

For each of Q1419's archived `three_leaves` N53 and N83 controls, hold the
first three raw leaf x coordinates and the selected cofactor-preimage target
x fixed. Compute the two roots `z0` of `S3(x0,x1,z0)`. For each `z0`, compute
the roots `z1` of `S3(z0,target_x,z1)`. For each `z1`, compute the roots
`x3` of `S3(x2,z1,x3)`. Test each resulting fourth x coordinate against
the exact normal-basis weight bound, rational point condition, cofactor
projection, enumerated factor base, and signed public-target group sum.

The balanced S3 polynomial is symmetric in its three arguments. The root
chain enumerates every fourth x satisfying those three links for the fixed
three leaves and fixed target-preimage x. The factor-base and point checks
filter algebraic candidates to usable curve relations. No S5 expansion or
SAT search is required for this conditional completion.

Freeze source and exact Q1419 protocol/fixture hashes before running.
Record separate root-chain arithmetic, base loading, and candidate-check
times, primitive field calls, raw candidates, exact-base hits, and full
signed group-law checks. The controls condition on archived witnesses and
therefore do not estimate ordinary-query relation yield. Keep proposal
`Q20261010172500` with `candidate_id: null`, `run_id: null`, `ISO0`.
