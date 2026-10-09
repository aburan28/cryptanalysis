# Full affine span of exact N131 d13 same-rotation pair outputs

The phi coordinates of valid same-rotation d13 pair sums span the **entire
131-bit affine space** on the exact ECC2K-130 curve. A certificate of 132
pair outputs has linearly independent augmented rows `[1, phi(P+Q)]` over
GF(2). Consequently, no nonzero affine equation in the pair-output phi
bits holds for every valid pair. Frobenius is an invertible binary linear
map, so the same conclusion applies to each of the six rotations in the
[d13 six-pair proposal](../n131_d13_same_rotation_pairs_20261009/RESULT.md).

The [frozen protocol](protocol.json) binds the earlier audited d13 base,
checked Sage runtime, code sources, deterministic sampling seed, 4,096-pair
attempt cap, 600-second wall cap, and 4-GiB process-RSS cap. The
[producer](result.json) reached rank 132 after 135 sampled distinct-code
pairs; it saved every independent pair witness and its exact output phi
mask. All 132 rows came from usable factor-base leaf selectors. The
exploratory producer stage took 0.189 seconds and peaked at 25,657,344
bytes of process RSS. These are structural-stage timings on a host without
an isolation receipt.

The [first audit](audit.json) reconstructed all saved leaf points and pair
sums and independently computed the 132-by-132 binary rank in Sage. The
[separate Sage elliptic-curve audit](sage_group_audit.json) embedded the
declared normal-basis field in Sage's polynomial-basis field, checked all
132 pair additions with Sage's own `EllipticCurve` arithmetic, checked the
257 distinct leaf selectors project nontrivially under cofactor four, and
recomputed rank 132. The producer and audits bind their inputs and source
hashes. A rank-132 witness subset is a proof about the entire pair-output
set: an affine equation valid on every output would vanish on these 132
independent rows and therefore have all coefficients zero.

This eliminates output-only affine bit constraints as a universal pair-domain
filter for this exact d13 policy. It leaves seed-sum-conditioned equations,
nonlinear output constraints, and target-conditioned cross-pair elimination
available. The existing N41 same-rotation ordinary rows provide positive
controls; the next solver must use the target to reject partial states while
multiple pair domains still contain unchosen leaves, then find and
independently replay an unpinned row without a quadratic pair-sum index.
Only a source-bound work and memory projection that fits the N131 600-second,
4-GiB envelope warrants a public-Q run. This structural proposal has
`candidate_id: null` and `run_id: null` until the complete target-query
algorithm is specified and measured.
