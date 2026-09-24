# Native batched addition for Sage binary elliptic curves

This package supplies a standalone patch against Sage commit
`671dfa344f4cc4a6d54f343cbfd1272ee81698c9` (10.10.rc0), runnable correctness
tests, and the preserved measurements from two accepted optimization steps.
It adds opt-in batch APIs; existing scalar arithmetic is unchanged.

For ordinary binary curves `y^2 + x*y = x^3 + a*x^2 + b`, `add_pairs` batches
independent additions with one inversion of their nonzero denominators.
`add_cartesian` validates each input once and processes the output grid in
bounded blocks. Infinity, inverse pairs, doubling and order-two points retain
their positions and behavior. Outputs are ordinary Sage points.

NTL-backed fields use a compiled Cython loop with reusable native field
temporaries. The final implementation also shares point-construction setup
across a batch. It initializes the standard finite-field point class directly
for internally computed normalized outputs and retains ordinary constructors
for custom subclasses. Other field representations use the Python fallback.
The module includes the pure-Python `frobenius_points` helper for Koblitz curves.
These APIs use variable-time arithmetic for public mathematical computations.

## Measured results

Each step was measured directly against its preceding implementation. The
ratios below are separate comparisons and must not be multiplied into a claim
about cumulative speed relative to stock Sage.

| Step | Control | Primary suite | Independent confirmation |
|---|---|---:|---:|
| Native field arithmetic | Previous Python batch implementation | 1.61x | 1.53x |
| Shared point-construction setup | Previous native binary | 1.56x | 1.82x |

The [native arithmetic report](../sage-binary-native-addition/RESULT.md) contains
26 timing cases. The [point-construction report](../sage-binary-point-construction/RESULT.md)
contains 40 cases, including singletons, tiny batches, and confirmation with
general coefficients. Both passed their frozen wall-time, CPU and peak-RSS
criteria. Timings charge complete API calls, exact verification against scalar
Sage sums, and output cleanup. Common fixture/reference setup is recorded
separately. These are local ARM64 results on a shared host.

## Apply and build

`sage-binary-batch.patch` contains only the two arithmetic modules, optional NTL
Meson registration and the arithmetic manual entry. It does not require the
earlier hardware-backend or local build-environment changes.

For a separate Sage source checkout at the pinned revision:

```sh
git -C /path/to/sage apply --check /path/to/cryptanalysis/experiments/sage-binary-batch/sage-binary-batch.patch
git -C /path/to/sage apply /path/to/cryptanalysis/experiments/sage-binary-batch/sage-binary-batch.patch
```

Configure and build that Sage checkout using its platform-specific source-build
instructions. For a checkout already configured with the required dependencies,
run `make -j6` from its root. The native extension requires NTL. The complete
Python and Cython files are also provided in `source/`, byte-for-byte identical
to the measured final implementation.

In the resulting Sage session:

```python
from sage.schemes.elliptic_curves.binary_batch import add_pairs, add_cartesian

F = GF(2**131, 'z')
E = EllipticCurve(F, [1, 1, 0, 0, 1])
# left and right are valid Sage points on E.
paired_sums = add_pairs(E, zip(left, right))
grid = add_cartesian(E, left, right, block_size=1024)
```

## Run correctness checks

Run the packaged suite using the patched Sage interpreter with its NTL
extension built:

```sh
/path/to/sage/sage -python /path/to/cryptanalysis/experiments/sage-binary-batch/tests/test_construction.py
/path/to/sage/sage -t --short /path/to/sage/src/sage/schemes/elliptic_curves/binary_batch.py
```

The 19 test groups cover exhaustive small fields, alternate moduli, general
coefficients, field-context switching, large fields through degree 257, output
state, custom constructors, cache isolation, copying, pickling, hashing and
subsequent arithmetic. `packaged-tests.log` records the packaged suite run
against the installed local extension. The historical API doctest receipts
record 15 passing examples.

## Audit the historical measurements

From the cryptanalysis repository root, without installing Sage:

```sh
python3 experiments/sage-binary-batch/verify_archive.py
```

This checks that the standalone patch applies to the preserved upstream base
files and reconstructs the exact distributed modules. It also verifies archived
hashes, balanced trial orders, output counts, timing summaries, binary identities
as recorded, and acceptance decisions for all 66 cases. The dedicated CI workflow
runs this audit. It does not rerun elliptic-curve arithmetic or establish a new
performance result.

The two adjacent experiment directories are historical archives: their scripts,
reports and receipts retain the original local paths. They are not portable
launchers for a fresh checkout. Replaying their timing campaigns requires
rebuilding the recorded baseline and candidate native sources for the selected
Sage ABI and configuring their runtime paths. Use the packaged tests above to
check a new build's mathematical behavior.

Machine-specific `.so` files are omitted from Git. `archive-layout.json`
explicitly lists every omitted binary referenced by the original evidence
manifests; their original hashes remain in the receipts. All manifest-listed
text sources and measurement records are preserved unchanged.

The source files retain their SPDX license declarations. `COPYING.txt` is the
upstream Sage copyright and licensing notice; the small `upstream-base/` fixture
files retain their original contents for patch-application validation.
