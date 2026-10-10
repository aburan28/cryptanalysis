# Mixed-width two-bucket tau scalar format

This experiment compresses the existing mode-132 sixteen-window
fixed-generator secp256k1 table. The windows have widths
`[8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,9]`. Each width has an exact atlas
of six-unit residue classes, with a seed also allowed to cover its
degree-three endomorphism image. Online evaluation forms exponent-zero
and exponent-one projective buckets and folds them as `B0+tau(B1)`.

## Frozen construction

- Use the existing certified Eisenstein scalar representative, norm
  `N(a,b)=a²+3ab+3b²`, unit order and four-corner nearest-digit rule.
  For widths 8 and 9, use radices 256 and 512 respectively. The
  endomorphism acts as `tau(a,b)=(-3b,a+3b)`.
- Set digit length limits `D8=256` and `D9=363`. For every six-unit
  class `s`, let `d_s` be its nearest direct digit. A directed successor
  is the class of `tau(d_s)`; it can share a seed when
  `3*N(d_s) <= Dw²`. Because `gcd(3,2^w)=1`, this successor action is a
  permutation of the finite class set.
- Decompose each permutation into cycles. Cover each cycle by segments
  of length one or two, where a length-two segment starts only at an
  eligible class. Find the minimum number of segments by exact dynamic
  programming, checking the cut at class zero of the cycle and the cut
  at its predecessor. Choose the minimum `(cost, cut)` and prefer length
  two on equal DP scores. Sort cycles by their least class ID, and put
  the zero seed first in each atlas.
- Encode each residue as a 32-bit seed index, exponent `0` or `1`, and
  six-unit image code. Exhaustively check congruence, unique assignment,
  digit norm, and every residue. Store signed 16-bit seed coordinates.
  Precompute one 64-byte affine point per seed per window.

## Proof and validation gates

Let `P=256^15*512` and `S=256*(256^15-1)/255 + 363*256^15`.
Require the exact integer inequality `n < 3*(P-S)^2` for the
secp256k1 order `n`; it proves all sixteen quotients terminate from
the certified representative. Check that raising `D9` to 364 fails
this sufficient bound with `D8=256`.

Commit the construction, atlas, proof, native mode, and input generator
before drawing a new panel. Use seed `20261010137` for 4,096 unique
full-range reduced scalars disjoint from all preceding scalar panels.
Check every new scalar against mode 132 and mode 135, the first 128
against independent binary multiplication, all 129 fixed fixture
points, every stored table point against an independently formed group
sum, and the complete release suite. Retain raw outputs, failures,
source and input hashes, compiler/binary identity, and memory bytes.

Pair modes 132, 135, and this mode on identical public scalars in a
qualifying isolated CPU environment. Charge scalar selection, recoding,
all table reads, unit gauges, bucket additions, endomorphism fold,
projective merge, inversion, and verification. A CPU speedup requires
the host receipt specified by `docs/ISOLATED_BENCHMARKS.md`.
