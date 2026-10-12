# Field and table correspondence for the four-limb U14 backend

The point backend preserves the existing U14 scalar decomposition and digit
sequence. Its new work is a representation map for the precomputed affine
points and a four-limb Jacobian evaluator for their sum.

Let `p=2^256-2^32-977`, `R128=2^128`, `R256=2^256`, and let `beta` be the
fixed nontrivial cube root of one in the source. The constants satisfy
`beta^2+beta+1=0 (mod p)` and
`PI_A-PI_B_MAG*beta=0 (mod p)`. The exact norm
`PI_A^2+PI_A*PI_B_MAG+PI_B_MAG^2` is `p`. These equalities were checked
by integer arithmetic. Thus the map from an Eisenstein pair to the
field, `a+b*omega -> a+b*beta (mod p)`, respects addition and
multiplication and kills the source kernel generator `pi`.

The existing pair kernel stores a field element `z` as coefficients with
`a+b*beta=z*R128 (mod p)`. Its four-limb conversion uses
`C0=Mont(R128)` and `C1=Mont(beta*R128)`. A Montgomery product of an
ordinary limb magnitude with either constant removes one factor of
`R256`, yielding its signed contribution times `R128` or `beta*R128`.
Adding the two signed contributions gives
`(a+b*beta)*R128=z*R256 (mod p)`. This is exactly the four-limb
Montgomery encoding of `z`. The conversion is applied to both coordinates
of every nonidentity affine table slot in `U256Tables::new`. The identity
slot is a sentinel and never enters a mixed addition.

The six source units act on an affine point by an `omega` power followed
by optional negation. Under the field map, `omega` sends `(x,y)` to
`(beta*x,y)`, and negation sends it to `(x,-y)`. The candidate's unit
operation uses the Montgomery encodings of `1`, `beta`, and `beta^2` for
the `x` multiplication and modular negation for `y`. Consequently every
decoded orbit/unit code names the same affine group point in both backends.

For a Jacobian accumulator `(X,Y,Z)` and affine addend `(x,y)`, both
backends compute `Z2=Z^2`, `U=x*Z2`, `S=y*Z*Z2`, `H=U-X`, and `V=S-Y`.
When `H` is nonzero they return

```
X' = V^2 - H^3 - 2*X*H^2
Y' = V*(X*H^2-X') - Y*H^3
Z' = Z*H.
```

When `H=0`, `V=0` selects doubling and `V!=0` selects the identity.
Doubling uses the same `a=0` Jacobian polynomial in both backends.
Because the representation map is a field homomorphism, each addition
and doubling commutes with it. Induction over the fourteen selected
windows gives equal projective group elements. The four-limb finalizer
inverts `Z` and exports `X/Z^2,Y/Z^3`; its binary-GCD Montgomery
correction is shared with the preceding mode.

The implementation checks the curve equation for every converted
nonidentity table slot, exact coordinates and all six unit images for
512 deterministic slots, and the group law on identity, equal/inverse,
and 512 nontrivial mixed-add cases. Complete scalar and fixture replay
checks the composed evaluator on the frozen panels.
