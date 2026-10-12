# Gauge-aware reduction tree protocol

The fixed generator, secp256k1 subgroup, U14 sector digits, canonical Solinas
field representation, and 64,314,208-byte affine table and constants match
format 170. Format 171 changes the online evaluation of the selected 14 or
fewer affine points. Each point carries a gauge in `{0,1,2}` for the cheap
order-three endomorphism. At each tree join, rotate one child into the chosen
gauge, then add the two points. A score chooses the pair and output gauge
with the shortest nominal field-product dependency, breaking ties by work,
gauge, and node order. The first affine-affine join uses a specialized XYZZ
formula; later joins use mixed or projective XYZZ formulas. The tree uses a
fixed 14-node stack array. The evaluator is variable-time.

The frozen scalar panel is `../prime-j0-sector-digit-20261010/fresh-inputs.json`.
Compare every point and scalar selector field with format 170, and compare
the first 128 points with independent binary multiplication. Check ordinary,
doubling, and inverse affine pairs separately. Independently reconstruct the
tree schedule from the published sector recoder and verify native rotation,
field-product, and dependency totals. Rebuild the release CLI and check all
129 fixture rows against the independent fixed-base fixture. Check the Lean
tree theorems and `#print axioms` with the pinned toolchain.

The operation model counts field products and squares on the ordinary path:
six for affine-affine addition, ten for XYZZ mixed addition, fourteen for
XYZZ projective addition, and one for each nontrivial gauge rotation. It
excludes recoding, table lookup, control flow, exceptional group paths,
inversion, conversion, cache behavior, and instruction scheduling. Product
depth assumes independent subtrees can execute concurrently. A wall-time
comparison requires the repository's isolated CPU benchmark gate, including
the complete scalar call and matched resource envelope.
