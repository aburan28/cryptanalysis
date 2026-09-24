# Local ONB multiplication window

This archive accompanies a direct change to `ecc2k130/codegen/field.py:Onb.mul`.
It is stacked after the ONB Frobenius change in PR #81. The candidate uses
set-bit iteration for multipliers with at most 12 bits, and a four-bit
rotation window for denser multipliers. Inputs with bits above the field's
`2m+1`-bit representation retain the original path, including its exact
noncanonical behavior.

`baseline/field.py` is the tracked source before this change. `field-v1.py`
is the held window-only candidate. Intent files were frozen before each
candidate or measurement revision. The accepted source is the tracked field
file in this branch. `point_ops.py` measures curve construction, addition,
doubling, scalar multiplication, and an unchanged Frobenius control with the
same Euclid inverse on both sides.

Run the portable archive check from the repository root:

```sh
python3 experiments/sage-ic-campaign/onb-mul-window-20260924/verify_archive.py
```

Re-run `benchmark.py` or `point_ops.py` to obtain machine-specific timings.
The archive check verifies the recorded measurements and recomputes exact
field and point outputs. See `RESULT.md` for the measured scope.
