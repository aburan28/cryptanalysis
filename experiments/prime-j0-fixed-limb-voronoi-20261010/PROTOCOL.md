# Fixed-limb reconstruction of a certified Voronoi representative

The candidate takes the two exact 512-bit reciprocal products from the
certified U14 scalar selector, uses their quotient limbs and high fractional
limbs to choose the nearest lattice corner, and constructs its signed
Eisenstein coordinates with fixed-width arithmetic. The U14 table,
signed-word recoder, point formulas, and verification boundary are shared
with the parent. The new mode is opt-in.

For a reduced scalar `0 <= k < n`, let `q_w=floor(k*v1/n)` and
`q_v=floor(k*(-w1)/n)`, and let the certified corner be `(d_w,d_v)`.
With `W=(w0,w1)=U-2V`, `V=(-u1,v1)`, and `w1<0`, the representative is

`a = k + (q_v+d_v)*u1 - (q_w+d_w)*w0`,

`b = (q_w+d_w)*(-w1) - (q_v+d_v)*v1`.

The quotient limbs, basis magnitudes, and products fit three, three, and
six 64-bit limbs respectively; the final signed coordinates fit three
limbs. Use full 3-by-3 limb products and six-limb modular add/subtract,
then interpret the result as a signed two's-complement integer. Assert
that every discarded high limb is a valid sign extension before entering
the existing `Signed192` recoder. On an ambiguous corner certificate,
use the parent's exact selector and convert its coordinates.

The fixed basis satisfies `u1,v1<2^128` and `w0,-w1<2^129`.
For `k<n`, each quotient plus its corner bit is at most its positive
numerator constant. Thus each 3-by-3 product is below `2^258`, and
the largest positive intermediate, `k+(q_v+d_v)u1`, is below
`2^256+2^257<2^258`. Six 64-bit limbs cover the intermediate with
ample headroom. The nearest hexagonal cell has norm at most `n/3`;
minimizing `a²+3ab+3b²` over the other coordinate gives
`|a|<=2*sqrt(n/3)<2^129` and `|b|<=2*sqrt(n)/3<2^128`.
Three limbs therefore cover both signed outputs. The implementation
also checks every discarded limb before recoding.

## Evaluation gates

1. Freeze this protocol before generating a disjoint 4,096-scalar holdout.
   Compare exact quotient limbs, chosen corner, signed coordinates,
   reconstruction modulo `n`, complete point outputs, addition counts,
   and table size against the committed certified mode. Include `0`,
   `n-1`, `n`, and `2^256-1` through scalar reduction.
2. Independently replay at least 128 holdout points with binary scalar
   multiplication, run the complete native release suite, and verify
   both modes on all 129 fixture points. Preserve source, input, binary,
   output, and failure hashes.
3. Pair the modes on frozen inputs and resources under the repository's
   host-isolation gate before claiming a CPU wall-time improvement.
   Count quotient products, coordinate partial products, reductions,
   table lookups, point operations, and verification in both modes.

This experiment tests a direct fixed-limb implementation of the certified
Voronoi split. A priority claim for the underlying GLV geometry requires
separate prior-art review.
