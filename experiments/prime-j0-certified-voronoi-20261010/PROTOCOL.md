# Certified Voronoi selection from reciprocal fractions

The secp256k1 U14 scalar path maps a reduced scalar to four corners of
an equilateral Eisenstein lattice cell and selects the smallest norm.
The candidate reads the high fractional limb of the two exact reciprocal
products, proves which corner has the smallest norm using four signed
128-bit score intervals, and constructs only that corner. An ambiguous
interval invokes the existing exact four-corner selector, preserving its
norm and tie-breaking rule. The point table and signed-word evaluator
remain unchanged.

## Geometry and certificate

Let `W=U-2V`, where `N(W)=N(V)=N(W+V)=n` and
`2<W,V>=-n`. For the reduced scalar `0<=k<n`, write

`k*v1/n = q_w+s` and `k*(-w1)/n = q_v+t`, with `0<=s,t<1`.

The base cell residual is `z=sW+tV`. Relative to `N(z)`, the four
corner norms differ by

| Corner `(dw,dv)` | Relative norm divided by `n` |
| --- | --- |
| `(0,0)` | `0` |
| `(1,0)` | `1-2s+t` |
| `(0,1)` | `1+s-2t` |
| `(1,1)` | `1-s-t` |

Use the exact reciprocal `R_c=floor(2^512*c/n)` from the parent
experiment. Its integer quotient is exact. For `X=k*R_c`, take
`h=((X mod 2^512) >> 448)`. The true fractional coordinate `s_c`
satisfies `h/2^64 <= s_c < (h+2)/2^64`: truncating the fractional
product loses less than `1/2^64`, and the reciprocal approximation
loses less than `n/2^512 < 1/2^64`.

With `B=2^64`, define `A10=B-2h_w+h_v`,
`A01=B+h_w-2h_v`, and `A11=B-h_w-h_v`. The true relative scores,
scaled by `B`, lie in the conservative intervals

| Corner | Lower | Upper |
| --- | --- | --- |
| `00` | `0` | `0` |
| `10` | `A10-4` | `A10+2` |
| `01` | `A01-4` | `A01+2` |
| `11` | `A11-4` | `A11` |

Certify corner `i` only if its upper bound is strictly below every
other corner's lower bound. This proves a unique nearest corner.
Otherwise use the parent's exact selector, including its
`(norm,max(|a|,|b|),a,b)` tie ordering. The certificate cannot return
a different scalar representative; a fallback can only cost time.

## Frozen evaluation

1. Implement a distinct opt-in native mode using the same U14 table,
   scalar reduction, signed-word recoder, point formulas, and output
   verifier as the parent. Record the certified corner, fallback count,
   selected representative, nonidentity additions, retained bytes, and
   final point. Keep the parent modes unchanged.
2. Use the 519 frozen and 4,096 reciprocal-panel scalars as inspected
   design inputs. Freeze a disjoint 4,096-scalar holdout from
   `random.Random(20261010217)` after this protocol and its generator
   are committed. Verify exact floors, all four score formulas, the
   certificate inequality, selected corner and representative, and
   complete point output. Independently replay at least 128 holdout
   points with binary double-and-add. Include boundary values `0`,
   `n-1`, `n`, and `2^256-1` through the normal scalar-reduction path.
3. Retain immutable source/input/binary hashes, full native release
   tests, raw fixture and case outputs, fallback rows, and failures.
   The operation screen reports the number of BigInt products and
   divisions on each path; it does not substitute for CPU wall time.
4. Pair the parent reciprocal mode and certified candidate on the
   same nine-case, five-repeat isolated panel. Charge scalar reduction,
   both reciprocal products, interval arithmetic, corner construction
   or exact fallback, recoding, lookup, point work, conversion, and
   correctness. A CPU speedup requires a qualifying host receipt under
   `docs/ISOLATED_BENCHMARKS.md`.

Fixed-point GLV splitting and nearest-lattice-point geometry have
prior art. This protocol tests their certified fractional-bit
combination in the exact U14 evaluator; priority needs separate review.
