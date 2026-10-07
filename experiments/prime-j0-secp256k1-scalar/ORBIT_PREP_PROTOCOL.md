# Prepared-unit-orbit control for width-four scalar evaluation

The published width-four method prepares the unit orbit of its nine
seed points. Our preceding 256-bit control rotated seed X coordinates
on demand. This experiment corrects that comparison boundary by
materializing each seed's three `ω` images before evaluating scalars.
For affine `(x,y)`, compute `(βx,y)` with one field multiplication and
`(β²x,y)=(-βx-x,y)` with additions only. This costs exactly nine
additional field multiplications per base after the nine affine seed
points are available. The seed-point preparation cost itself remains
unknown in this prototype.

The on-demand and orbit-prepared arms share the same width-four digit
stream, nine seed points, τ positions, and mixed additions. The
orbit-prepared arm looks up any unit rotation without a per-digit
multiplication. If its pair schedule has `q` pairs, it starts with
carried gauge `-2q mod 3`, advances the gauge by two at every paired
stride, and keeps it on ordinary strides. Thus each paired Z scale is
a negation and the final gauge is zero. The evaluator checks this
invariant and compares both results with Sage's independent `kP`.

The frozen generic-path boundary is `4M+2S` per ordinary τ,
`6M+4S` per cheap paired stride, `8M+3S` per mixed addition after
initialization, and `1M` per nontrivial on-demand digit/final rotation.
The first mixed-add call from infinity is free. Report the evaluator
count separately from the nine multiplication orbit preparation cost
per base and from the unknown nine-seed construction/normalization
cost. In particular, a sixteen-scalar shared-base panel cannot be
used as a single-use variable-base speedup. No CPU timing is recorded.

Freeze this protocol and `compare_orbit_prepared.py` before deriving
eight new bases and sixteen new scalars per base. Save the checked Sage
runtime receipt, then run:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/prime-j0-secp256k1-scalar/orbit-prep-runtime-info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/prime-j0-secp256k1-scalar/compare_orbit_prepared.py
```

This is a faithful control for the published unit-orbit strategy,
not a novelty or CPU speedup claim. Exceptional paths, recoding,
normalization, table access, and runtime overhead remain outside the
generic-path count.
