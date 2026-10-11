# Native atlas for the 6,094-class scalar cover

The compressed radix-1024 cover has a **1,667,480-byte DR20 atlas** with
SHA-256 `121177d1e448239401dac069a6dc0dac52a78b2851acf542f612e497fea48f6d`.
It retains 67,338 seeds and 817,344 affine entries. The
[independent atlas verifier](native-atlas-check.json) checked every class
record and the inverse unit action on all **1,048,576 residues**.

The [native materializer](materialize_native.py) binds this atlas and the
fresh 4,096-scalar panel to the direct-XYZZ evaluator. The targeted Rust test
compares every result with the adic path and certified digits, and the first
128 points with independent binary multiplication. The
[Linux workflow](../../.github/workflows/prime-j0-cycle-compression-native.yml)
also runs the full native suite and ten boundary fixtures. Terminal native
replay evidence will be recorded here. Any CPU wall-time comparison requires
the host-level isolation gate in `docs/ISOLATED_BENCHMARKS.md`.
