# ONB scalar multiplication with a signed window

This change applies the same `Curve.mul` implementation to both
`ecc2k130/codegen/curves.py` and its tracked IC runner copy at
`ecc2k130/runner/codegen/curves.py`. Scalars below 32 bits retain binary
double-and-add. Larger nonnegative scalars use a width-4 signed window with
odd-multiple precomputation, reducing the number of affine additions and
their field inversions. Negative scalars return the negation of the
corresponding positive multiple.

`baseline/` and `source/` freeze the exact source files. Both intents were
frozen before the measured runs and bind the local/runner curve and field
sources plus the benchmark scripts. Each of sixteen cases ran in a fresh
Python process with twelve alternating complete scalar calls per arm. Every
result was checked against the original implementation and curve equation.
`test_window.py` also covers infinity, order-two points, exhaustive small
fields, threshold boundaries, long scalars, and negative scalars. The
portable verifier checks source identity, tests, exact outputs, phase sums,
resource bounds, and the independent seed split:

```sh
python3 experiments/sage-ic-campaign/onb-scalar-window-20260924/verify_archive.py
```

The targeted IC arithmetic tests passed. The broader local runner test
attempt recorded three environment failures: `pysat` is absent for two SAT
tests, and a fixed-parameter JSON fixture is absent in this checkout for a
third. Its other 27 tests passed. See `RESULT.md` for timing and scope.
