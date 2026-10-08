# Reusable Macaulay layouts with fresh pivots

This opt-in prototype reuses a Boolean Macaulay matrix's monomial order and
scatter map while rebuilding every numeric row and choosing every pivot afresh.
An unchanged independent checker certifies the resulting basis, including both
ideal inclusions and Boolean-field critical pairs. Failed proposals fall back to
fresh packed F4 under the same remaining work and checker budgets.

The reusable object depends only on the ring size, equation count, input degree
bound and multiplier bound. It contains no training coefficients, pivots, proof
or answer. This makes the changed nonlinear pair-product controls work where
round91's fixed proof replay failed. A complete dense support envelope can also
be expensive; difficult MQ systems remain inconclusive under the frozen limits.
The implementation remains opt-in and does not change default dispatch.

Read [PROTOCOL.md](PROTOCOL.md) for mathematics, bounds and timing boundaries,
[RESULTS.md](RESULTS.md) for positive and negative results, and
[NEXT_STEPS.md](NEXT_STEPS.md) for the remaining performance experiments.

```sh
python3 experiments/groebner-perf-20260924/round92/run_validation.py \
  --output /tmp/macaulay-layout-validation
# Optional, separately labelled exploratory measurements:
python3 experiments/groebner-perf-20260924/round92/run_validation.py \
  --diagnostics --output /tmp/macaulay-layout-diagnostics
```

Use Python 3.13 and a C++17 compiler (`CXX=clang++` in CI). The driver requires a
clean Git snapshot of all bound sources, builds native libraries on the current
platform, and holds the shared heavy-work lock across validation. It does not
load archived native libraries. The tests use ordinary Python, not Sage.

`query.py` exposes `Query`, `Layout` and `DenseInput`. The fixture adapter's
packing happens before the algebra timing boundary. The native path consumes its
immutable packed coefficients directly; their owners must remain alive and
unchanged throughout the call. Call-local coefficients/pivots/proof storage are
fresh. The Python layout lock serializes simultaneous use/close of one layout.
No overlapping-native-call claim is made by those Python concurrency tests.

`results/development-evidence.tar.xz` is a lossless, content-addressed evidence
archive: read `MANIFEST.json`, then resolve each logical file's `member` under
`objects/`. Its receipt records every member's verified custody. It retains the
failed development test configuration, frozen sources, all eight local native
outputs, raw controls and diagnostics, independent audits and publication-gate
controls. Downloaded or archived native binaries are never executed by audits.

Linux/macOS CI must rebuild and validate the frozen implementation before its
PR is merged. Local CPU timing is exploratory: an isolation receipt is absent.
This experiment does not establish a general F4/F5 record, an asymptotic F6
improvement, GPU performance, or verified single-target IC/rho speedup.
