# Exact unit-orbit quotient lookup for radix-1024 digits

Let `R=1024`, `S=R^2`, and write a residue pair as `(a,b)` in
`(Z/RZ)^2`. The six unit actions on Eisenstein pairs are
`u_(k,s)=(-1)^s omega^k`, for `k in {0,1,2}` and `s in {0,1}`.
They commute with the tau endomorphism and preserve the Eisenstein norm
`N(a,b)=a^2+3ab+3b^2`. The canonical index of a residue is the
smallest packed residue among its six unit images:

`c(a,b)=min_u index(u(a,b))`, where `index(a,b)=R*(a mod R)+(b mod R)`.

The full residue space has `1,048,576` indices and exactly `174,764`
distinct canonical indices. The atlas stores a bit at precisely those
indices. A `u64` mask word covers 64 indices; a `u32` prefix entry gives
the population count before each word. For canonical `c=64w+t`, its
dense zero-based class index is

`rank(c)=prefix[w]+popcount(mask[w] & ((1<<t)-1))`.

The independent verifier checks the bitset against the canonical action
for every residue, every prefix increment, and every resulting rank.

For each canonical class, the three-byte code records a seed index
`i`, a tau exponent `e in {0,1,2}`, and a unit index `j` such that

`c = index(u_j(tau^e d_i))`.

For a query residue `r`, choose the first unit `u_k` in the fixed six-unit
order with `index(u_k(r))=c(r)`. Decode the stored seed and use the unit
`u_k^(-1)u_j`. In pair notation, if `j=(p_j,s_j)` and `k=(p_k,s_k)`,
the output unit is

`((p_j-p_k) mod 3, s_j xor s_k)`.

The resulting digit is congruent to `r` modulo `R`, even if a residue
has a nontrivial stabilizer and several unit indices give the same
canonical value. It has the same norm as `tau^e d_i`, hence norm at most
`R^2`. Subtracting it and dividing both coefficients by `R` preserves
the scalar representation exactly. The independent atlas verifier
checks these properties for all `1,048,576` full residues. The exact
terminal residual atlas is byte-identical to the previously verified
one and is replayed on all `80,521` terminal pairs.

## Expanded tau cover

The minimum three-image atlas has 7,586 disjoint adjacent pairs of
length-three tau segments. Replacing every such pair by three
length-two segments preserves the six covered classes, uses one extra
seed, and removes two exponent-two classes per replacement. Then the
first 2,048 remaining length-three segments are split into one
length-two segment and one singleton. Every length-two segment is
admissible because `3N(d)<=R^2` for every class's minimum-norm seed.

The deterministic cover has segment counts
`(n1,n2,n3)=(2,117,70,155,10,779)`. Thus it stores
`S=n1+n2+n3=83,051` full seeds and covers
`C=n1+2n2+3n3=174,764` classes. The identity
`n3=C-2S+n1` gives the lower bound `n3>=C-2S=8,662` under this
three-image policy. The remaining 2,117-class gap is exactly the
singleton count. The independent plan verifier rederives every cycle,
segment, admissibility condition, and the exact `64,674` full-residue
exponent-two count.

## Representation budget

The full quotient atlas has a 20-byte header, 16,384 `u64` mask words,
16,385 `u32` rank entries, 174,764 three-byte class codes, and 83,051
four-byte seed pairs. These total **1,053,128 bytes**. The terminal
atlas adds 362,016 bytes. Twelve full windows plus one terminal window
use 1,005,900 affine slots, or 64,377,600 point bytes. Using the
previously observed 424-byte native container and constant overhead
gives a **65,793,168-byte projected retained size**, 1,315,696 bytes
below the reported 64 MiB capacity. Native `size_of` accounting must
verify the final byte count after its decoder is implemented.
