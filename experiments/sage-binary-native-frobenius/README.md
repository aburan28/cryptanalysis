# Local Sage binary Frobenius optimization

This step extends the existing opt-in
`sage.schemes.elliptic_curves.binary_batch.frobenius_points` API in the local
Sage fork. It selects the native path only for NTL-backed binary fields and
positive powers after reduction modulo the field degree. The previous Python
implementation remains the fallback. The patch applies after the accepted
native batch-addition and point-construction steps.

The source changes are in
`third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_batch.py` and
`binary_batch_ntl.pyx`. The installed local runtime already contains them.

From the cryptanalysis repository root, rebuild and test with a fresh output
directory:

```sh
experiments/sage-binary-arithmetic/run-sage.sh -python \
  experiments/sage-binary-native-addition/build_install.py \
  --out experiments/sage-binary-native-frobenius/install-new
experiments/sage-binary-arithmetic/run-sage.sh -python \
  experiments/sage-binary-native-frobenius/test_native_frobenius.py
experiments/sage-binary-arithmetic/run-sage.sh -python \
  experiments/sage-binary-point-construction/test_construction.py
```

Use `benchmark.py --suite primary` or `--suite confirmation` with a new `--out`
directory to repeat the paired complete-call timings. `intent-v1.json` froze
the comparison cases and criteria before implementation. The baseline Python
source, native source and compiled binary are preserved in `baseline/`.

[Measured result](RESULT.md) documents exact output checks, timings, resource
use and scope.
