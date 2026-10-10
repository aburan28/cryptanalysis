# Correctness and termination of the binary-GCD finalizer

**Theorem.** For every nonidentity projective point produced by the U14
Eisenstein path with its balanced Pair representation invariant, the
opt-in binary-GCD finalizer emits the same canonical affine secp256k1
point as the parent four-limb Fermat-chain finalizer.
The inverse loop terminates before its 2,048-step guard for every
nonzero field input.

Let `p=2^256-2^32-977`, `R=2^128`, `R'=2^256`, and let `beta` satisfy
`beta^2+beta+1=0 (mod p)`. The Eisenstein pair `(a,b)` for a field
element `w` satisfies `a+b*beta=wR (mod p)`. Multiplication by
`R'/R=R` gives

`wR' = aR + b*beta*R (mod p)`.

The field setup stores `C0=R*R'` and `C1=beta*R*R'` in four-limb
Montgomery form. A Montgomery product of the magnitude of `a` or `b`
with its constant gives the corresponding summand above. Negation for
negative coefficients and modular addition therefore convert each
projective coordinate exactly to `wR' (mod p)`. Balanced coefficients
have magnitude below `2^128<p`, as required by the four-limb product;
the implementation asserts their high limbs are zero.

Now let `m=zR' (mod p)` for the nonzero projective `Z` coordinate.
Since `p` is prime, `gcd(m,p)=1`.
The binary loop starts with

`(u,v,x_u,x_v)=(m,p,1,0)`

and maintains these invariants:

1. `u` and `v` are positive and `gcd(u,v)=1`.
2. `x_u*m=u (mod p)` and `x_v*m=v (mod p)`.
3. `0<=x_u,x_v<p`.

When an operand and its coefficient are even, both are halved. When the
operand is even but its coefficient is odd, `x+p` is even and represents
the same residue as `x`, so `(x+p)/2` is the correct modular half. The
implementation retains the carry out of its four-limb `x+p` addition
as bit 256 before the right shift. Since `0<=x<p`, the 257-bit sum is
below `2p` and the resulting half is again below `p`. When both operands
are odd, subtracting the smaller operand and its coefficient from the
larger preserves both congruences. Modular subtraction preserves the
coefficient range. Each step thus preserves all three invariants.

If `u=v>1`, their gcd would exceed one, contrary to invariant 1. Hence
an odd subtraction remains positive. Once `u=1` or `v=1`, its
coefficient `q` satisfies `q*m=1 (mod p)` and is the canonical inverse
of the stored Montgomery residue.

For termination, define `L=bitlen(u)+bitlen(v)`. Initially `L<=512`.
An even halving lowers `L` by exactly one. An odd subtraction cannot
raise it and leaves an even positive difference. Before any further odd
subtraction, that difference must be halved at least once. The loop
therefore performs no more than 510 halvings before reaching an operand
of one and no more subtractions than halvings. Its total number of
halving and subtraction steps is at most 1,020, below the implemented
2,048-step guard.

Finally, `q=(zR')^-1=z^-1(R')^-1 (mod p)`. Setup computes
`C3=(R')^3 (mod p)` by converting the context's `(R')^2` constant to
Montgomery form. One Montgomery product returns

`q*C3*(R')^-1 = q*(R')^2 = z^-1 R' (mod p)`.

This is the correct Montgomery representation of `z^-1`. Subsequent
Montgomery squares and products compute `X/z^2` and `Y/z^3`; exporting
the two coordinates therefore gives the same affine point.

The [native tests](../prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs)
check modular halves at the carry boundary, 512 deterministic field
elements against the Fermat chain, 21,004 complete scalar outputs, and
128 independent fresh-point replays. The binary loop has
input-dependent branches and remains opt-in for public-scalar research.
