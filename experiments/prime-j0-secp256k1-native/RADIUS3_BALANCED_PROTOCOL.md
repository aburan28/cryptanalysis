# Balanced pair slots and a 33-edge matching atlas: frozen protocol

## Mathematical and storage candidate

The parent radius-two tau comb stores 21 pair tables of 39,366 points
each in 104-byte affine slots. Every stored coordinate is returned by
`Pair::mul`, which Montgomery-reduces and balances the result in
Z[omega]/(pi). The established nearest-lattice bound is
`|a|, |b| < R = 2^128` for each balanced field element. Pack each of the
four signed coefficients of affine `x` and `y` in two 64-bit magnitude
limbs and one shared sign byte. On this 64-bit build the struct should
occupy 72 bytes. Reject construction if *any* coefficient has a nonzero
limb above limb 1. Decode the exact signed coefficients before the
existing unit map and mixed addition. Keep the same Montgomery residue;
do not perform a square-root decompression.

The 90 MiB retained-slot cap then admits 33 complete edge tables:
`33 * 81 * 81 * 6 * 72 = 93,533,616` bytes. Start with all 30 edges
`(i,j)` among ordinary rows `0 <= i < j < 12` having `j-i <= 3`.
Use the design panel below to add three distinct edges. At each step,
evaluate every unused edge by rebuilding the deterministic maximum-
matching atlas for the current graph plus that edge. Select the edge
with the largest total matched-edge count on the design panel; break
ties by lexicographic `(i,j)` order. This exact greedy rule, its seeds,
and the three-edge budget are fixed before screening. The selected
graph is fixed for native implementation; the online evaluator only
looks up a 12-bit active-row mask in its 4,096-entry matching atlas.
Matchings maximize cardinality, with lexicographically smallest sorted
edge sequence for ties. The sparse top row and its repair stay intact.
This is a variable-time public-scalar method.

## Screen and acceptance gates

Draw two disjoint panels of 4,096 scalars uniformly from `[0,n)` using
`random.Random(20261009331)` for design and
`random.Random(20261009332)` for holdout. Use the frozen parent
radius-two binary with SHA-256
`b9c194c9105ef41daf95cef229d72434d5421e72ffd714dc32ed8ee7bb41f6ad`
to obtain selected representatives. Independently reconstruct each
width-six digit stream and all 13 active-row masks. The reconstructed
radius-two fusion count must equal the binary's count for every case.
Screen `G2` (21 edges), `G3` (30 distance-at-most-three edges), and
the fixed greedy 33-edge graph. Record each panel's exact fusion,
mixed-addition, tau, and `5*tau_steps + 11*mixed_additions` proxy
totals, all three selected edges, per-case deltas, atlas digest, and
table bytes. Keep every case, including zero-gain masks.

Implement the 33-edge graph only if the holdout proxy decreases at
least 3% versus `G2`, each scalar has at least as many fusions as
`G2`, and the checked 72-byte slots fit 90 MiB. For native
verification, require exact affine points, selected representatives,
tau counts, terminal repairs, and independently predicted fusions
versus the parent on five boundary inputs, 214 frozen inputs, all 129
expected-point fixtures, and the two new panels. Independently replay
at least 256 fresh points and every fixture. The release suite must
check direct sums for each new edge and atlas disjointness for every
mask. Preserve source, binary, script, input, and receipt hashes.

Generate a 129-case, seven-repeat isolated-host manifest with the
same scalar and point fixtures and a verified timer boundary. The
online interval includes nine representative recodings, matching
lookup, compact point decoding, all point work, affine output, and
correctness assertion; table construction and process launch are
recorded separately. CPU speedup requires a host satisfying
`docs/ISOLATED_BENCHMARKS.md`, with paired case order and retained
failures. Local timings are diagnostics only.
