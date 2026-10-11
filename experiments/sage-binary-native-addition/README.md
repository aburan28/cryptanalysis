# Native Sage binary-curve addition

The installed fork also includes the subsequent
[point-construction optimization](../sage-binary-point-construction/RESULT.md),
measured directly against this step's preserved native binary. The receipts in
this directory remain the historical evidence for the initial native addition.

This follow-up moves the existing `binary_batch` addition arithmetic into a
Cython/NTL loop. It reuses native finite-field temporaries and prefix products,
and still constructs ordinary Sage points. Both `add_pairs` and `add_cartesian`
automatically select it when the extension is installed and the field uses
Sage's NTL representation. Other field representations retain the Python path.

[The measured result](RESULT.md) passes the frozen local acceptance gates:
1.61x across the primary suite and 1.53x on independent confirmation inputs,
relative to the preceding optimized batch implementation.

The supported model remains `y^2 + x*y = x^3 + a*x^2 + b` over a finite binary
field. Scalar `P + Q`, scalar multiplication, and Frobenius APIs are unchanged.
The implementation is variable-time mathematical arithmetic. It supports
general coefficients in this model, including both Koblitz curves.

```python
from sage.schemes.elliptic_curves.binary_batch import add_pairs, add_cartesian

F = GF(2**131, 'z')
E = EllipticCurve(F, [1, 1, 0, 0, 1])
# left and right contain valid Sage points on E.
sums = add_cartesian(E, left, right, block_size=1024)
paired_sums = add_pairs(E, zip(left, right))
```

`intent-v1.json` and its SHA file freeze the mechanism, cases, budgets and gates
before implementation. `baseline/` preserves the previous implementation.
`native-addition.patch` is an incremental patch against that existing fork;
it does not replace the earlier full-fork patches.

The local extension was compiled through Sage's Meson build and installed into
the existing local Sage runtime. This is an incremental extension build, not a
new full Sage distribution build. Initial build attempts used an absent venv
Ninja path and then an environment lacking GAP; both failed logs are retained.
The build succeeds when run inside the configured Sage shell.

To rebuild, install and validate from the repository root (choose a new output
directory for each run):

```sh
experiments/sage-binary-arithmetic/run-sage.sh -python \
  experiments/sage-binary-native-addition/build_install.py \
  --out experiments/sage-binary-native-addition/install-new
experiments/sage-binary-arithmetic/run-sage.sh -python \
  experiments/sage-binary-native-addition/test_native.py
experiments/sage-binary-arithmetic/run-sage.sh -python \
  experiments/sage-binary-native-addition/benchmark.py \
  --out experiments/sage-binary-native-addition/run-new
```

The test suite includes the nine existing binary-arithmetic tests and five
native-specific groups: backend selection, forced-NTL exhaustive small fields
and alternate moduli, generators that change the NTL context, word-boundary
degrees through 257, and agreement with the preserved Python implementation.

Benchmark workers use the installed module and native extension, not a prototype
loader. Each cell has 12 balanced paired rounds and four complete calls per
sample. Pair creation, validation, allocation, Sage output construction, exact
comparison to independently computed scalar Sage sums, and output destruction
are charged. Common field/fixture/reference setup is recorded separately.
Fresh-worker peak RSS comparisons cover both APIs at the maximum measured size.
Cold interpreter startup and compilation are outside the arithmetic timing.
Results apply to this local ARM64 host and frozen arithmetic workload.
