# Succinct orbit-quotient scalar multiplication experiment

This candidate replaces the million-entry radix-1024 residue-code
array with one three-byte code per six-unit orbit, a canonical-class
bitset, and a rank directory. The saved atlas storage funds a larger
three-image tau cover with a projected complete native table below the
reported 64 MiB design budget. The [proof](PROOF.md) specifies lookup,
digit correctness, cover admissibility, and byte accounting.

The prime-field endomorphism `tau=1-omega` and six-unit precomputation
symmetry come from Xu, Yu, Han, and Lu, *On Efficient Computations of
y²=x³+b/Fp for Primes p ≡ 1 (mod 3)*. This candidate adds a succinct
rank-indexed residue lookup and an expanded fixed-generator tau cover.

Construction is independent of scalar targets and timing. The plan
first replaces every disjoint adjacent pair of length-three segments
in the minimum cover, then splits the first 2,048 remaining triples.
The ordered tau cycles, cover plan, bitset, rank array, class codes,
seeds, terminal data, and SHA-256 receipts are frozen before any new
scalar panel is drawn. The independent verifiers recompute the cycle
partition and decode every full residue and terminal pair.

Next, draw 4,096 full-range scalars disjoint modulo the subgroup order
from every earlier panel. Pair this quotient format against the
minimum-memory and cache-budgeted three-image formats on those same
scalars. Record integer reconstruction, independently checked point
outputs, mixed additions, grouped unit rotations, nonidentity outer
tau images, native retained bytes, and all correctness failures.

The native implementation must expose the quotient lookup as a
separate source-pinned format, retain the existing direct residue-code
format as a correctness control, and measure canonicalization and rank
operations as part of the full scalar evaluation. CPU wall-time ratios
require host-level isolation receipts under
`docs/ISOLATED_BENCHMARKS.md`; ordinary-host measurements remain
diagnostic.
