# Local ONB curve squares

This archive accompanies a direct change to the tracked
`ecc2k130/codegen/curves.py:Curve` class. Exact square terms in `onCurve`,
`dbl`, `add`, and `pointFromX` now use the existing `Onb.sqr`, which routes
through the verified Frobenius permutation. The polynomial-basis `CurvePb`
class is unchanged.

`baseline/curves.py` is the original curve source. `baseline-v3/field.py` is
the final Python 3.9-compatible field source used on **both** sides of the
accepted comparison. `field-v1.py` and `curves-v1.py` preserve a held candidate
that also removed a redundant field normalization; that field edit failed its
frozen gate and is absent from the accepted source. Earlier source snapshots
and raw timings remain in the archive.

Run from the repository root:

```sh
python3 experiments/sage-ic-campaign/onb-curve-squaring-20260924/verify_archive.py
```

The verifier checks source hashes, exact outputs, recorded warm gates, and the
cold first-doubling receipt. Re-run `benchmark.py` or `measure_cold.py` for
machine-specific timings. See `RESULT.md` for the cold/warm tradeoff and limits.
