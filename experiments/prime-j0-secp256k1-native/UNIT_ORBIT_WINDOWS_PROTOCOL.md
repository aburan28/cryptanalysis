# Fixed-base Eisenstein unit-orbit windows: frozen protocol

## Construction

For the standard secp256k1 generator, decompose the public scalar as
`k = a + b*lambda_tau (mod n)` using the nearest Eisenstein-lattice
representative in the existing equilateral basis `W,V`. Its norm is at
most `n/3`. Write `z_0=(a,b)` and use three radix-1024 windows followed
by eleven radix-512 windows. The widths total 129 bits. At window `i`,
take the two coefficient residues modulo `B_i=2^width_i`. The six units
`{+/-1,+/-omega,+/-omega^2}` act on the pair and its residue. Choose the
lexicographically least residue in that orbit, then its minimum-norm
Eisenstein digit `d_i^0`. The residue map supplies the unit `u_i` taking
that canonical residue to the actual residue. Set

`d_i = u_i*d_i^0`, `z_(i+1) = (z_i-d_i)/B_i`.

For each window, retain one affine point per residue orbit:
`[2^(sum of prior widths) * d_i^0]G`. Apply the unit to the looked-up
point and sum the nonidentity points. The point loop uses no doublings
or tau steps and at most 13 mixed additions. This is a variable-time
method for a public scalar and one fixed generator. Table generation is
target independent and separately accounted for.

In the `(a,b)` basis, the norm is `a^2+3ab+3b^2`; multiplying by `omega`
maps `(a,b)` to `(a+3b,-a-2b)`. The equilateral coordinates
`(a+b,-b)` show that each residue class modulo `B` has a digit with
norm at most `B^2/3`: its nearest lattice point is among the four
floor/ceiling corners. The update obeys
`||z_(i+1)|| <= ||z_i||/B_i + 1/sqrt(3)`.
Since `n < 2^256`, `||z_0|| <= sqrt(n/3)`, every `B_i >= 512`, and the
radix product is `2^129`, after 14 windows

`||z_14|| < 1/(2*sqrt(3)) + 512/(511*sqrt(3)) < 1`.

The norm of a nonzero Eisenstein integer is at least one, so `z_14=0`.
This gives exact integer reconstruction before reducing modulo the
group order; the scalar congruence then gives `[k]G`.

Burnside's lemma gives `(B^2+8)/6` residue orbits for these even
radices: the identity fixes `B^2` residues, `-1` fixes four, and each
other unit fixes only zero. This is 174,764 orbits for radix 1024 and
43,692 for radix 512. Fourteen tables retain 1,004,904 slots, including
one identity slot per window. At the current 72-byte affine slot size,
the table is 72,353,088 bytes. Two reusable four-byte residue maps take
5,242,880 bytes, for 77,595,968 bytes before small metadata, below the
90 MiB cap. The native build must report actual allocated and mapped
bytes, rather than assume this layout.

## Frozen comparison

Compare with `--scalar-w6-comb13-hex9-graphaware33-fixed` from the parent
graph-aware branch. Its frozen release binary SHA-256 is
`fbd46d82b7b7867b4bf71dedc46b8ef8a43dd552a94b3779158b347ee1e40b80`.
Use independent uniform scalar panels from `[0,n)`: 2,048 design cases
from `random.Random(20261009511)` and 4,096 holdout cases from
`random.Random(20261009512)`. The seed is used only for scalar fixture
generation, outside the online interval. Preserve scalar-input hashes,
source hashes, every proxy delta, zero and regression counts, allocation
size, recoding status, and exact reconstruction checks. The holdout may
be run only after this protocol and checker are committed and the PR is
open.

The screening point proxy is `5*tau_steps + 11*mixed_additions` for the
parent and `11*max(nonidentity_windows-1,0)` for this candidate. It
excludes scalar decomposition, residue lookup, unit maps, cache traffic,
table loading, exceptional point paths, and final affine conversion.
The holdout gate is at least 20% lower point proxy with no failed exact
reconstruction and retained bytes below 90 MiB. Passing it authorizes
native implementation, not a CPU speedup claim. Preserve a stopped
candidate if it fails.

The native gate independently verifies at least 256 fresh `[k]G` points,
the existing edge and fixture corpus, all panel outputs, every orbit
table against direct group sums, and exceptional identity/equal/inverse
paths. Compare the same public scalar and source snapshot against the
parent. A CPU wall-time claim requires a paired online receipt from the
isolated benchmark service; its interval includes scalar decomposition,
all residue lookups and unit maps, point work, and final verification.
Current RunPod container preflight rejects controlled CPU timing.

The six-unit digit-set idea and GLV fixed-base multiplication have
prior art. The contribution under test is this 129-bit, 14-window,
unit-orbit positional table configuration and its measured behavior
under the declared 90 MiB limit. Academic priority is unresolved.
