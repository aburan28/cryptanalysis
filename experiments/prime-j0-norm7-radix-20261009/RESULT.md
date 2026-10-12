# Degree-seven endomorphism radix: exact map and matched source-cost screen

The endomorphism `alpha = 2 - omega = 1 + tau` has a compact degree-seven
Jacobian map on secp256k1. The [map receipt](map-result.json) proves its
polynomial curve identity over `Z[beta]/(beta^2+beta+1)` and matches
`2P - omega(P)` in **225 projective point checks**. A direct evaluation
schedule uses **7 general field products and 5 squarings**, with all
constant actions recorded separately. This supplies a concrete radix-seven
alternative to the supplied paper's norm-three `tau` map.

For `E: y^2=x^3+7`, write `omega(x,y)=(beta*x,y)` and
`beta^2+beta+1=0`. Set `A=2-beta`, `c=8+12*beta`, `T=X^3`, and `U=Z^6`.
The homogeneous polynomials `D,N,H` are specified in the frozen
[protocol](PROTOCOL.md). The complete Jacobian map is

`(X:Y:Z) -> (X*N(T,U) : Y*H(T,U) : A*Z*D(T,U))`.

For the 7-product, 5-square schedule, compute `U` from `Z^2,Z^4,Z^6`
and obtain `T=Y^2-7U` from the curve equation. Then form `T^2`, `TU`,
`U^2`, and `N=T^2+(28c+84)TU+(7c^2+168c)U^2`. With
`D=T-cU`, evaluate

`H=ND-3TU*((28c+84+2c)T+((28c+84)c+2(7c^2+168c))U)`.

The three output-coordinate products complete the schedule. The count
is a source-field-operation count: multiplications by `A`, `c`, and other
fixed Eisenstein constants, reductions, branches, inversion for output,
and memory traffic require separate implementation accounting.

The map derivation identifies the nonidentity kernel of `2-omega` by
`2Q=omega(Q)`, whose three pairwise x-coordinate classes satisfy
`x^3=c`. Vélu's normalized x-map is `x*N/D^2`; its y-map is
`y*H/D^3`. Scaling by `A^-2,A^-3` gives the tangent action of
`2-omega`. The exact polynomial verifier checks
`H=ND+3t(N'D-2N)` and
`(t+7)H^2-tN^3=7A^6D^6` coefficient by coefficient. Since the
secp256k1 subgroup order is prime to seven, the kernel denominator
does not vanish on a nonidentity subgroup input. Identity is handled
separately.

## Radix coverage and point replay

The [radix receipt](radix-result.json) enumerates the quotient by
`alpha^w` for widths one through five. A Hensel lift of the root
`tau=-1 mod 7` represents each residue by `a+b*lambda_w mod 7^w`.
The six units form one orbit of each nonzero class modulo seven. Every
residue not divisible by seven received a minimum-norm digit, with
unit images assigned consistently; the retained seed-orbit count is
exactly `7^(w-1)`.

| Width | Seed orbits | Maximum digit norm | Audited closed-ball states | Map steps, 519 scalars | Nonzero adds, 519 scalars |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 1 | 7 | 46,200 | 39,592 |
| 2 | 7 | 13 | 55 | 45,969 | 21,149 |
| 3 | 49 | 108 | 385 | 45,694 | 14,408 |
| 4 | 343 | 777 | 2,839 | 45,466 | 10,895 |
| 5 | 2,401 | 5,524 | 20,029 | 45,108 | 8,719 |

For each width, **all 519** frozen scalar representatives recoded and
reconstructed as exact integer pairs. The first 128 scalar outputs per
width, **640 complete Horner point replays**, matched independent binary
multiplication. The radius bound proves that a step from outside the
maximum-digit-norm ball strictly decreases norm: by the triangle
inequality its length is at most
`(|z|+sqrt(D))/sqrt(7) < 2|z|/sqrt(7) < |z|`.
The ball is forward invariant under the same bound. Exhaustive traversal
of every integer pair in each listed ball found no nonzero cycle, giving
global termination for the frozen digit sets.

## Matched width-four tau control

The existing [128-case width-four control](../prime-j0-secp256k1-scalar/WIDTH4_RESULT.md)
supplies the same scalar representatives and base points. The table below
compares evaluation-only source counts under `S=M`; each alpha row charges
`12` units per map and `11` per noninitial mixed add. It gives alpha
free digit-table construction, free unit actions, and a free first add.
The control's paired tau count includes its recorded rotations. These
boundaries favor alpha and remain stage diagnostics, not CPU timing.

| Alpha width | Maps, 128 cases | Adds, 128 cases | Alpha lower bound `M+S` | Tau paired `M+S` | Alpha cases below tau |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 11,545 | 9,902 | 247,462 | 154,746 | 0 |
| 2 | 11,485 | 5,305 | 196,175 | 154,746 | 0 |
| 3 | 11,414 | 3,592 | 176,480 | 154,746 | 0 |
| 4 | 11,367 | 2,720 | 166,324 | 154,746 | 0 |
| 5 | 11,285 | 2,183 | 159,433 | 154,746 | 5 |

At width five, the candidate's lower-bound composition is **96,459 M
and 62,974 S**, while the control records **100,564 M and 54,182 S**.
Thus the source-count ordering depends on the real squaring-to-product
cost ratio. With the listed formulas and free candidate preparation, the
aggregate break-even ratio is `S/M = 4,105/8,792`, about **0.467**.
Under `S=M`, width five exceeds the control by **4,687** units, or
about **3.0%** of the control. The candidate also needs a one-use
digit-preparation strategy for variable-base use; its 2,401 seed
orbits cannot be treated as free in a complete scalar comparison.

The next proof and implementation step is a degree-seven map schedule
or paired-map chain that reduces the full charged cost, followed by a
source-bound one-use native comparison. An isolated CPU receipt is
required for a wall-time result. The explicit degree-seven map follows
standard Vélu theory, and complex-base digits and unit symmetries have
prior art. The specific performance direction remains an experimental
candidate pending that cost and priority review.
