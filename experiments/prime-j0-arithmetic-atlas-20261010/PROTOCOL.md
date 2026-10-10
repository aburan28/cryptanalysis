# Arithmetic orbit indexing for U14 fixed-base multiplication

The unit quotient of the U14 digit grid has `(m*m + 8)/6` orbits at
`m = 2^w`, `w in {9,10}`. The existing evaluator stores a four-byte code
for every residue pair. This candidate computes the code's orbit rank and
unit action from the six images of the input residue and keeps only the
canonical digit array. It retains the same affine point windows and the
grouped accumulator gauge of mode 127. The candidate is mode 128.

For canonical `(a,b)` in lexicographic order, write `m = 3q+r`, with
`r in {1,2}`. Row zero contains `b=0..m/2`. For rows `1..q`, the
canonical `b` values occur in the intervals

1. `0..q-a`,
2. `q+1..2q+r-1-a`,
3. `2q+r..m-1-a`,

with empty intervals omitted. Row `a` starts at
`m/2+1+(a-1)m-3(a-1)a/2`. Adding the offsets of the preceding
intervals gives the exact orbit ID used by the stored-code atlas. The
unit code is the smallest inverse action that maps the canonical pair
back to the input pair; this resolves fixed-point ties identically to
the original atlas.

Freeze the existing 129-case secp256k1 fixture and prior gauge panels.
Before examining a new panel, commit this protocol and the implementation.
Generate 4,096 new scalars from seed `20261010128`, disjoint from prior
panels after subgroup reduction. Compare modes 127 and 128 on the same
scalar in one executable. Require identical canonical representatives,
all fourteen orbit IDs and unit codes, point outputs, mixed-add counts,
gauge-product counts, and per-case expected points. Exhaustively compare
all `512^2 + 1024^2` residue pairs against the stored-code atlas in native
tests. Independently replay the first 128 new points with binary scalar
multiplication. Record source and input hashes, test exits, table bytes,
preparation, and process RSS.

The online timer starts after fixture loading, scalar decoding, table
preparation, field/unit setup, and binary-inverse correction setup. It
includes representative selection, recoding, arithmetic orbit indexing,
point lookup, grouped-gauge additions, final inversion and formatting,
and expected-point verification. Pair the two modes on one isolated Linux
host under the same executable, resources, and nine frozen fixture inputs,
using the repository benchmark service. Preserve failed and rejected
isolation rows. Local contended-host timings are diagnostic only.
