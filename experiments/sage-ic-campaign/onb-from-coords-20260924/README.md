# Local ONB coordinate packing

This archive accompanies a direct change to the fork's tracked
`ecc2k130/codegen/field.py:Onb.fromCoords`. Sparse coordinate values now
visit their set bits; denser values use bytewise bit reversal to form the
mirrored half of the internal symmetric representation. High bits and negative
inputs retain the original low-`m`-bit meaning.

`baseline/field.py` is the source before this change. `field-v1.py` preserves
the held set-bit-only candidate. All intent files were frozen before their
corresponding source or timing revision. `point_build.py` measures the
containing `Curve.pointFromX(Onb.fromCoords(...))` stage on sparse coordinates
with the same inverse and trace algorithms on both sides.

Run the portable archive check from the repository root:

```sh
python3 experiments/sage-ic-campaign/onb-from-coords-20260924/verify_archive.py
```

Re-run `benchmark.py` or `point_build.py` for timings on another machine.
The archive check verifies exact outputs and the recorded stage gates.
