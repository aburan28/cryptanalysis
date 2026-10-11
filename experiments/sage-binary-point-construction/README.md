# Sage binary batch point construction

This step follows the accepted native-addition implementation. It avoids
repeating Sage's general point constructor for each internally computed,
normalized affine result. The native loop caches the point homset and allocator
once per batch and initializes the standard finite-field point's parent,
codomain, coordinate tuple and normalization flag directly.

[The measured result](RESULT.md) passes all frozen acceptance gates: another
1.56x on the primary suite and 1.82x on independent confirmation inputs,
compared directly with the previously accepted native addition binary.

The fast path applies only when `curve._point` is exactly
`EllipticCurvePoint_finite_field`. Custom classes retain their allocation and
initialization hooks. Returned points are the same Sage class and parent as
before. This does not change scalar point construction or the field arithmetic.

The implementation mirrors the constructor state in this pinned Sage fork:
`Element._parent`, `SchemeMorphism._codomain`, and projective point
`_coords`/`_normalized`. Tests compare against fresh ordinary constructors and
exercise serialization, copying, category/domain/codomain, hashing, comparison,
normalization and subsequent arithmetic. Re-run those tests when updating Sage.

## Rebuild and use

The existing `add_pairs` and `add_cartesian` APIs select this path automatically
when running the installed local fork. To rebuild from the repository root,
choose a new output directory:

```sh
experiments/sage-binary-arithmetic/run-sage.sh -python \
  experiments/sage-binary-native-addition/build_install.py \
  --out experiments/sage-binary-point-construction/install-new
experiments/sage-binary-arithmetic/run-sage.sh -python \
  experiments/sage-binary-point-construction/test_construction.py
```

The helper builds the extension through the existing Meson configuration and
retains prior installed files. This is an incremental extension build and
installation into the existing Sage runtime.

`point-construction.patch` applies on top of the preceding native-addition
implementation. `baseline/` preserves that implementation's exact Python source,
Cython source and compiled extension. Earlier experiment artifacts remain intact.

## Measurement protocol

`intent-v1.json` and its SHA file freeze the mechanism, invariants, criteria and
new confirmation work before implementation. Primary cases cover both APIs over
degrees 19, 67 and 131, with 1, 9, 64, 1,024 and 4,096 output points. Confirmation
uses new seeds and degrees 31 and 163, plus non-prime coefficients at degree 131.

Each cell runs in a fresh worker with 12 balanced paired rounds. Sample size is
`max(4, ceil(4096/output_count))` complete API calls, which reduces timer noise for
singleton and tiny batches. Both arms include point input preparation, output
construction, exact comparison to scalar Sage reference sums, and cleanup.
Common field, fixture and reference construction are recorded separately.

The incumbent wrapper is explicitly bound to its preserved native binary under
an isolated import name. Both old and new binary hashes are recorded. This avoids
accidentally letting the incumbent wrapper select the newly installed extension.
Fresh-worker maximum-size RSS checks cover both APIs.

```sh
experiments/sage-binary-arithmetic/run-sage.sh -python \
  experiments/sage-binary-point-construction/benchmark.py \
  --out experiments/sage-binary-point-construction/run-new
```

Results describe complete verified mathematical arithmetic APIs on this local
ARM64 host. Raw timings, setup costs, failures, source snapshots and profiles are
retained with each run. Speedups compare directly with the previous native batch
implementation; earlier speedups are not multiplied into a cumulative claim.
