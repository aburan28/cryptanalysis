# Local ONB coordinate extraction

This archive accompanies a direct change to the fork's tracked
`ecc2k130/codegen/field.py:Onb.toCoords`. The original method inspected each
of the `m` coordinate bits in Python. After the same normalization, the
candidate extracts those contiguous bits with one shift and one mask.

`baseline/field.py` is the source before this change. `intent-v1.json` was
frozen before source edits or timing. `benchmark.py` measures extraction and
the audit runner's `toCoords(...).bit_count() & 1` trace pattern.
`point_recovery.py` uses the same curve, inverse, and seeded abscissae on both
sides to show the effect on a containing point operation.

Run the portable archive check from the repository root:

```sh
python3 experiments/sage-ic-campaign/onb-to-coords-20260924/verify_archive.py
```

The verifier checks exact outputs and the recorded stage gates. Re-run
`benchmark.py` and `point_recovery.py` for timings on another machine.
