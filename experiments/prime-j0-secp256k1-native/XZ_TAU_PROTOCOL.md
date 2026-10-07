# Retrospective x-only τ feasibility screen

The `x` coordinate is unchanged by point negation.  On `y²=x³+7`,
`τ=1−ω` has the rational x-map

`x(τP) = (x(P)³+28) / ((1−β)² x(P)²)`, where `ω(P)=(βx(P),y(P))`.

For homogeneous x-coordinates `x=X/Z`, the source uses

`X' = X³+28Z³`, `Z'=(1−β)²X²Z`.

The script checks this map against independent affine `P−ω(P)`, a
standard x-only doubling formula against `2P`, and the Izu–Takagi
differential-addition formula against `P+2P=3P`.  The inputs are the
existing 64-base native fixture, with four arbitrary XZ scales per base.
This is retrospective design-data correctness, not a frozen speed panel.
Run with ordinary Python (no Sage job):

```sh
python3 experiments/prime-j0-secp256k1-native/xz_tau_feasibility.py
```

Count source field operations for the complete primitive formulas,
treating small-constant multiplication by `b=7` as additions.  Reuse the
four products `X₂X₃`, `Z₂Z₃`, `X₂Z₃`, `X₃Z₂` in differential addition; this
gives `7M+2S` with general known difference, or `6M+2S` when its `Z=1`.
Compare the x-only τ and doubling costs with the native Jacobian formulas
in `src/main.rs`; compare differential addition with the project's mixed
addition.  The x-only route requires a maintained known difference and
a final y-coordinate recovery.  A cheaper differential-add primitive is
not a complete scalar speedup.  An actual chain would need its own frozen
input panel, total operation accounting, and isolated CPU receipt.

The differential formulas and their costs are from the
[Explicit-Formulas Database's short-Weierstrass XZ catalog](https://www.hyperelliptic.org/EFD/g1p/auto-shortw-xz.html),
which attributes them to Brier–Joye and Izu–Takagi.  This experiment
makes no novelty claim for x-only arithmetic or differential chains.
