# Degree-seven bucket point replay

The low-cost cover screen identifies `rho0` and `rho0_bar0` as the two
formats with no norm-seven tau sub-buckets. Before selecting a new
held-out scalar panel, replay the first 256 scalars of the already
frozen direct-index design panel through each cover and check every
output against independent binary multiplication on secp256k1.

For each window, accumulate the point-table seed after its six-unit
action into a bucket labelled by norm-seven branch and tau exponent.
Within each branch, apply tau after bucket accumulation; then apply
the branch map once to its aggregate. Use `rho(P)=P+tau(P)` and
`rho_bar(P)=4P-tau(P)` as independent affine reference formulas.
Combine branches, including the exact terminal contribution, and
compare the final affine point with binary multiplication of the
same scalar. Record the number of seed points constructed, map calls,
bucket additions, branch additions, and exact output digest.

This point replay tests the algebra and the one-map-per-branch
scheduling. It is a design control on an existing panel. A promoted
native format must use a new disjoint panel and a source-pinned
correctness replay; controlled timing still requires the host
isolation gate.
