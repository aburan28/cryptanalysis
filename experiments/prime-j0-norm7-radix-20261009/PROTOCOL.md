# Norm-seven endomorphism radix screen for secp256k1

The experiment tests `alpha = 2 - omega = 1 + tau` as the radix of a
variable-base scalar expansion on `y^2 = x^3 + 7`. Its Eisenstein norm is
seven, so it consumes more scalar norm per map than the norm-three `tau`
radix. The candidate succeeds as a performance direction only if the cost
of its degree-seven map, recoding, nonzero additions, and one-use digit
preparation beats a matched norm-three method. Source operation counts are
diagnostics until complete isolated timing exists.

## Frozen map and proof gates

Let `omega(P) = (beta*x, y)`, with `beta^2 + beta + 1 = 0`, and set
`A = 2 - beta`, `c = 8 + 12*beta`. For affine `t = x^3`, define

```
D = t - c
N = t^2 + (28*c + 84)*t + 7*c^2 + 168*c
H = t^3 - (63*c + 168)*t^2 - (147*c^2 + 1176*c)*t
    - 7*c^3 - 168*c^2
```

The proposed map is `x' = A^-2*x*N/D^2` and
`y' = A^-3*y*H/D^3`. For Jacobian `(X:Y:Z)`, homogenize these polynomials
with `T=X^3`, `U=Z^6`, and output `(X*N(T,U), Y*H(T,U), A*Z*D(T,U))`.
Handle the identity separately. The screen must prove, by exact polynomial
arithmetic in `Z[beta]/(beta^2+beta+1)`, both

```
H = N*D + 3*t*(N'*D - 2*N)
(t+7)*H^2 - t*N^3 = 7*A^6*D^6.
```

It must independently compare the map with `2P - omega(P)` on the frozen
129-point fixture and at four nonzero Jacobian scales for selected points.
The secp256k1 subgroup order is prime to seven, so `D=0` cannot occur on a
nonidentity subgroup point. Record any exception or mismatch rather than
discarding it.

## Radix and resource screen

In the coefficient basis `a+b*tau`, multiplication by `alpha=1+tau` is
`(a-3b, a+4b)`, with determinant seven. The quotient by `alpha^w` has
`7^w` residues. Compute the Hensel root `lambda_w` of
`lambda^2-3*lambda+3=0` modulo `7^w`, starting at `lambda_1=-1 mod 7`.
Then `a+b*tau` has residue `a+b*lambda_w mod 7^w`. For each width
`w in {1,2,3,4,5}`, choose the minimum-norm representative for every
residue not divisible by seven, with a fixed `(norm,a,b)` tie rule. Build
its six-unit orbits, require complete quotient coverage, and record the
actual seed count and maximum digit norm. Do not infer seed count from
orbit size without checking unit stabilizers.

For each scalar in the frozen 519-input record, use the existing
endomorphism-lattice nearest representative and recode by repeatedly
subtracting its selected digit and dividing exactly by `alpha`. Require
termination and exact integer-pair reconstruction, not just agreement
modulo the subgroup order. Include failed recodings as rows. On at least
128 frozen scalars, replay the expansion as a group Horner chain and
compare its point with independent binary multiplication.

Count map steps, nonzero additions, unit rotations, and the exact number
of distinct nonidentity prepared seed points. Keep map and digit-table
preparation costs separate. The projective map schedule, including its
constant multiplications, must be stated explicitly; an optimistic
`M+S` count alone is not an online CPU result. Compare only paired scalar
inputs and the same preparation boundary. Do not launch timing on the
contended local host. Native integration follows only if the complete
source-cost screen identifies a plausible advantage worth measuring.

The supplied Xu et al. paper establishes the norm-three `tau` method and
unit-invariant digit preparation; complex-base and isogeny methods have
substantial prior art. This screen makes no academic priority assignment.
