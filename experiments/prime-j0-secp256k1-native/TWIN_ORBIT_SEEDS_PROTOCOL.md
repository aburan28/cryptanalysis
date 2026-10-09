# Two-output linked-orbit seed construction

The linked width-four τ atlas needs both `A = 2P - ωP` and
`B = ω(2P) - P`. Its current preparation computes the two mixed
Jacobian additions separately. Both additions start from the same
projective `2P = (X,Y,Z)` up to the `ω` rotation of `X`; their affine
addends are `(βx,-y)` and `(x,-y)` for `P=(x,y)`. Compute once
`Z²`, `Z³`, `s=-yZ³`, `v=s-Y`, `v²`, and `u=xZ²`. The two addition
numerators then use

`h_A = βu-X`, `h_B = u-βX`.

For each `h`, calculate `hh=h²`, `hhh=h*hh`, `xh=X_input*hh`,
`X_out=v²-hhh-2*xh`, `Y_out=v*(xh-X_out)-Y*hhh`, and `Z_out=Z*h`.
The second `X_input` is `βX`. This yields both exact Jacobian points
with shared work. A zero `h` aborts; on the declared nonidentity
secp256k1 prime-order subgroup it is impossible: it would imply
`2P=±ωP` or `2ωP=±P`, so the subgroup order would divide the norm
`3` or `7` of the corresponding Eisenstein integer.

Count the two ordinary mixed additions and two `β` rotations as
`16M+6S+2M = 24 M+S`. The shared two-output formula is `15M+4S = 19
M+S`, saving five field operations in seed preparation. Six point
doublings and nine orbit-image multiplications remain, giving
`6*7 + 19 + 9 = 70 M+S` versus 75 for the linked atlas. This is an
exact source-expression count for this coordinate representation;
field addition, constant behavior, memory traffic, and CPU time are
not included.

The digit atlas and ordered scalar stream stay identical to the
existing linked mode. Before a performance claim, compare all nine
prepared seeds with the independent Sage linked-seed fixture, recover
all frozen scalar outputs, retain raw failures, and run the complete
linked-versus-twin operations on a host passing the isolated CPU
preflight. Both arms must include scalar reduction, recoding,
preparation, evaluation, final affine inversion, and output checking.

Co-Z and shared-input addition formulas have prior art, including
[Co-Z Addition Formulae and Binary Ladders on Elliptic Curves](https://eprint.iacr.org/2010/309).
The academic novelty of this specific orbit-pair specialization is
unproved. This research path is variable-time and not ready for
secret scalars.
