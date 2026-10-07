# X-only τ and differential addition: primitive feasibility

The protocol and script were frozen in commit `6b38df48` before this
retrospective screen ran on the already-frozen 64-base native fixture.
The fixture SHA-256 is
`2e8da438343ecf650c9d8d9b2a593f5d603027c4c1f81485f2456c38028491d4`;
the script SHA-256 is
`2d7d35be6865dfdb84d7b040df6290931b601cb85100b103746bf86328e2ab36`.
The [raw result](xz-tau-feasibility-result.json) retains these hashes,
all check counts, and null CPU and novelty claims.

Every tested input point was valid on secp256k1.  The script compared
the x-only τ map against independent affine `P−ω(P)` on each base and
its double, checked x-only doubling against affine `2P`, and checked
differential addition of `P` and `2P` (known difference `P`) against
affine `3P`.  Repeating at homogeneous scales 1, 2, 3, and 7 gave **512
τ**, **256 double**, and **256 differential-add** checks with no mismatch.

| Source primitive | Count with small constant 7 handled by additions |
| --- | ---: |
| XZ τ map | `4M+2S` |
| Current Jacobian τ map | `4M+2S` |
| XZ double | `4M+3S` |
| Current Jacobian double | `2M+5S` |
| XZ differential add, general known difference | `7M+2S` |
| XZ differential add, affine known difference | `6M+2S` |
| Current Jacobian mixed add | `8M+3S` |

The differential-add count explicitly reuses the products `X₂X₃`,
`Z₂Z₃`, `X₂Z₃`, and `X₃Z₂` in the
[Izu–Takagi formula cataloged by EFD](https://www.hyperelliptic.org/EFD/g1p/auto-shortw-xz.html).
It is a count of this source expression, with no memory traffic,
constant-multiplication cost, or exception handling charged.  The
`6M+2S` variant assumes the **known difference** has affine `Z=1`.

This is an attractive **8-unit addition primitive**, but ordinary
scalar multiplication cannot replace each Jacobian add with it: a
differential addition needs `x(R−Q)` as well as `x(R)` and `x(Q)`, and
the result is only an x-coordinate.  Maintaining the differences and
recovering the final y-coordinate may exceed the three-unit saving per
addition.  The direct XZ τ substitution itself has no operation-count
gain.  A full x-only τ/differential chain, exact edge handling, complete
online arithmetic count, and isolated CPU benchmark remain open.
Existing x-only Weierstrass differential arithmetic has prior art; this
screen makes no academic novelty or CPU speedup claim.
[Costello, Hisil, and Smith](https://eprint.iacr.org/2013/692.pdf)
already develop endomorphism-driven two-dimensional x-only differential
chains, and [Chung et al.](https://eprint.iacr.org/2015/983.pdf)
describe recovering full group outputs from x-only pseudomultiplication.
Any future claim would need to identify a specific secp256k1 chain and
prove how it differs from those methods.

Chung et al.'s published generic two-dimensional short-Weierstrass
algorithm uses `(14β+12)M+(9β+3)S+2I` plus constant multiplications
for two `β`-bit coefficients (Theorem 3).  At `β=128`, its field-operation
expression is **2,959 `M+S` plus two inversions** before constants.  The
frozen width-four τ source count is **88,656/64 = 1,385.25 `M+S` per
case**, excluding its common final inversion.  The workloads and setup
boundaries differ, so this is only a coarse feasibility screen; it
does rule out simply substituting that generic chain as an obvious win.
The remaining x-only opportunity would require a τ-specific differential
state transition that maintains its known differences cheaply.
