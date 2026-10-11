# Degree-seven endomorphism in XYZZ form

The direct map lets the radix-1024 fixed-base evaluator keep its compact
67,338-seed cover while combining the norm-seven bucket in one final point
merge. Proposition 3.2 of [Xu, Yu, Han, and Lu's paper](https://eprint.iacr.org/2024/1906)
gives the Jacobian polynomial for `rho=2-omega=1+tau`; this note transports
that polynomial into the XYZZ state used by the native evaluator.

For secp256k1, let `beta` be the cube root selected by the existing native
endomorphism constants. An XYZZ point `(X,Y,ZZ,ZZZ)` represents
`(x,y)=(X/ZZ,Y/ZZZ)`, with `ZZ^3=ZZZ^2`. Define

```text
A = 3 X^3                 B = 4 Y^2
C = beta A                D = beta B
E = 2 A - B + C - D
F = -3 A^2 - (B + 3 D)(2 A - B + C)
H = 3 A^2(A - 4 C + 7 D) + B^2(B - 3 A - 9 C).
```

The direct XYZZ output is

```text
rho(X,Y,ZZ,ZZZ) = (X F, Y H, ZZ E^2, ZZZ E^3).
```

To verify the transfer, choose any projective `Z` with `ZZ=Z^2` and
`ZZZ=Z^3`. Proposition 3.2 gives Jacobian output `(X F,Y H,Z E)`.
Its two scale powers are exactly `ZZ E^2` and `ZZZ E^3`, so the XYZZ
output represents the same affine point. The scale invariant follows from
`(ZZ E^2)^3=(ZZZ E^3)^2`. The identity is returned directly, and a zero
output scale is represented by `ZZ=ZZZ=0`.

The priority-cover evaluator currently combines buckets as
`(B0+B3)+tau((B1+B3)+tau(B2))`. The direct variant computes
`B0+tau(B1+tau(B2))+rho(B3)`. These are equal by additivity of `tau`
and `rho=1+tau`. Both use the same recoding, atlas, seed table, and mixed
window additions.

The frozen source-call model counts `add_xyzz` as 12 general field
multiplications and 2 squarings on its ordinary nonidentity path. The
direct `rho` method has 9 general multiplications, 5 squarings, and 2
fixed-constant Solinas products. The final combination trades one ordinary
point merge for one direct `rho` call. The nominal change is therefore
`-3M + 3S + 2C`, where `C` is the native fixed-constant Solinas product.
These call counts exclude field additions, exceptional branches, and
hardware effects; an isolated paired run is needed to decide wall time.
