# Free-selector Q1420 bilinear-leaf gate

This experiment tests whether exact selector-weighted W24 leaf products improve
an **ordinary public-target** six-summand decomposition, after the fixed-leaf
z-coordinate releases in the parent experiment became satisfiable. The frozen
query is index zero of one-target workload `eee7f6ee5f6b`. All six selectors,
leaf x and inverse variables, four projective S3 intermediates, and the
four-lift target choice are free. The two factor bases each have
`B=16,772,828` usable points before sign folding. The source and oriented
degree-263 descendant use their own native W24 bases.

The comparator is the archived projective S3 XCNF on this exact workload.
Before building each variant, reproduce the comparator byte for byte through
the named-input encoder and match its archived raw SHA-256. Then build
`wz_only` and `both_products`, preserving the comparator's sorting, cutoff,
target mux, S3 tree, and clauses. The sole algorithmic change is the proven
leaf-product rewrite in the parent bilinear experiment. Formula construction
and all four solver inputs, their source hashes, named-input maps, and XCNF
statistics are committed **before** any new solver launch.

Run one CryptoMiniSat 5.14.7 native-XOR attempt per curve and variant in this
fixed order: source/`wz_only`, descendant/`wz_only`, source/`both_products`,
descendant/`both_products`. Use one thread, `--maxtime=120`, a 150-second
external wall guard, and a 4-GiB sampled RSS guard. Keep raw stdout and
stderr, exit/terminal state, restart evidence, exact solver binary digest,
formula hashes, build costs, and guard status. A bounded attempt is
`BOUNDED_UNKNOWN`, and a failed producer stays a distinct row. Previous
comparator runs remain archived; their wall values are exploratory because
host-wide CPU isolation was not established.

For any SAT model, independently check every ordinary clause and native XOR,
decode all six W24 masks, rational leaves and S3 nodes, enumerate signed
group sums, and verify the selected raw target lift and fourfold projection
to the public subgroup target. A solver SAT line alone is not a relation.
The result is a target-decomposition diagnostic: factor-base logarithms,
relation matrix rank, final linear algebra, and online target recovery are
separate gates. `candidate_id` stays `null` until a complete pipeline is
specified and measured. Preserve all zero-yield and capped cells.

The next promotion gate is a held-out ordinary query stream with frozen
input law and repeated, charged attempts. A verified decomposition must be
inserted into a declared relation/target-descent row space before reporting
novel rank. No wall-time speedup is promoted from this unisolated host.
