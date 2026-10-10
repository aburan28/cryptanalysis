# Exact target-bitplane replay over conditioned S3 boundaries

The frozen GF(2^9), seven-bit, four- and five-summand S3 chains are conditioned
on one high bit of each nonterminal middle summand. Their grouped static
layouts leave a 16-variable terminal boundary. At setup, build each exact
conditioned grouped layout and its static elimination witnesses. Enumerate
all 65,536 boundary assignments once per branch, retaining the static
feasibility bitset and one truth plane for each last-link coordinate at target
zero and each of the nine unit target values. Each target receives fresh
packed ANF coefficients for independent equation checking. Its native query
XORs the unit-target deltas selected by its nine target bits, intersects the
coordinate zero planes with static feasibility, and reconstructs a static
witness. The native kernel checks the original conditioned equations and
re-evaluates the target equations directly from the stored ANF templates.
Python checks the original unconditioned equations and curve sum again.

The last S3 equation is affine in the target bits over GF(2):
`S3(a,b,t) = a²b² + (a²+b²)t² + abt + curve_b`. Both squaring and
multiplication by a fixed field element are GF(2)-linear, so the zero-target
plane XOR the selected unit-target deltas is exactly the fresh target's truth
plane. Intersecting all zero planes decides precisely the boundary assignments
that satisfy the original equations. The cached static witness history then
reconstructs a full assignment. The proof is conditional on this affine target
law and the bounded separator; no target answer or complete witness is stored.

Freeze the seed-1 ell-7 cases, their two or four static branches, 24-variable
bag and 200,000,000-state caps. Accept only the exact 16-variable boundary,
nine affine target bits, 90 template rows, at most 2^22 plane words, and the
existing source-bound grouped library. Reject wider boundaries and template
monomials outside the boundary. Charge the 90 × 65,536 template evaluations
and grouped-layout construction to reusable setup. The query charge is nine
times the boundary state count, under the unchanged state cap.

For optimized and UBSan builds, compare both arms on all 512 target abscissae
for both summand counts, alternating arm order. Require all 4,096 complete
queries and 12,288 branch queries to match independently enumerated
branch-restricted curve reachability. Every satisfiable branch must pass the
original ANF, field S3, native direct-template, and independent old curve-point
replay checks. Preserve each branch status and every failure or cap. Witness
assignments may differ between exact solvers; check each independently.

For exploratory timing, run three target warmups per arm followed by three
alternating complete 512-target passes per case on the optimized build. The
6,144 timed complete queries include fresh packed coefficients, all native
branches, original equations, and curve replay; retain all 18,432 branch
records. Keep layout and plane setup outside target-dependent intervals and
report them separately. Resample targets as clusters for a paired interval.
CPU wall-time speedup remains unqualified until the isolated-host receipt
passes the repository's gate. A dense cross-link or non-affine target law is a
counterexample to this kernel's applicability; retain the original exact
message path for those systems.
