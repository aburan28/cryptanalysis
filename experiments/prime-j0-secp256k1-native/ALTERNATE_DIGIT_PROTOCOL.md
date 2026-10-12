# Alternate width-four τ digit atlas screen

The existing width-four table has nine sign/ω seed orbits covering 54
residue classes modulo `τ⁴`.  This screen changes **one nonbase orbit at
a time** while preserving its six residue classes, the other eight
orbits, the 64 saved scalar representatives, and the source-count model.
Enumerate all replacement coefficient orbits with Eisenstein norm at
most 400.  Hold the affine base orbit fixed.  Each replacement table
must still have exactly 54 unique nonzero residue entries.

For each table, prove recoder termination on all integer coefficient
states, not only the 64 saved scalars.  If `D` is the largest digit
norm, the quotient norm after subtracting a digit satisfies
`N((z−d)/τ) ≤ (√N(z)+√D)²/3`.  For `N(z)>2D`, this is strictly below
`N(z)`; the finite region `N(z)≤2D` is closed under the quotient.
Exhaustively follow its deterministic transition graph and reject any
cycle not reaching zero.  Preserve failed candidates and one cycle
witness.  For every accepted table, recode and exactly reconstruct all
64 previously frozen short scalar representatives.

Score the current native evaluation expressions: 10 `M+S` per paired
τ stride, 6 per single τ, 11 per mixed base addition, 14 per cached
projective seed addition, and 2 for each used seed's cached `Z²,Z³`.
Do not charge the existing 83 units of point-table and unit-orbit
preparation to this comparison because the **new seed point's
construction cost is unknown**.  The saved score is a threshold: its
saving must exceed any extra seed preparation, scalar recoding, and
memory cost before a one-use scalar gain is possible.  These are
retrospective design-data operation counts, not CPU timings or a
speedup claim.  The initial representative table must reproduce the
frozen native per-case operation counts and 88,656-unit aggregate.

Run with ordinary Python (no Sage job):

```sh
python3 experiments/prime-j0-secp256k1-native/alternate_digit_atlas.py
```
