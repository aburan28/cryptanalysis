# Standalone symmetric Boolean transform kernels

This experiment targets the coefficient-specialization work that remains after round45's independently checked branch symmetry. It adds optional exact kernels for `C = Z A Z^T` when the original coefficient matrix `A` is symmetric. Nothing here is wired into a producer, independent certificate checker, GPU backend, or automatic dispatch.

The recursive method specializes two symmetric diagonal blocks and one general off-diagonal block. It combines their results using `E`, `E+D`, `(E+D)^T`, and `F+E+D+D^T`. Characteristic-two diagonal cancellation saves additional work. The implementation stays in place and has logarithmic call depth. See [PROTOCOL.md](PROTOCOL.md) for the derivation, limits and test contract, and [RESEARCH.md](RESEARCH.md) for primary-source context and a separate degree-pruning hypothesis.

| Kernel | XORs for one 512×512 coefficient slice | Mirror stores |
| --- | ---: | ---: |
| Accepted full transform | 2,359,296 | 0 |
| Triangular second axis | 1,705,216 | 130,816 |
| Pure recursive symmetric transform | 1,243,904 | 195,072 |

These are derived operation counts, not measured speedups. The screen also includes an axis-separated full transform, a tiled triangular mirror, and recursive variants with full-transform leaves of size8,16,32. Leaf16 is the timing primary declared before native execution. All methods remain `O(N² log N)`; no algorithmic novelty or asymptotic improvement is claimed.

The standalone wrapper checks exact matrix symmetry before choosing a symmetric kernel. Asymmetric matrices execute the accepted full transform. Its explicitly unguarded mode exists only for a conditional kernel timing boundary after validation; it must never substitute for the checker's fresh original-ANF symmetry guard. Future integration must preserve all proof, root, degree, workspace and work-budget checks.

Run with Python3.12 or newer and a C++17 compiler:

```sh
python3 experiments/groebner-perf-20260924/round46/build.py
python3 experiments/groebner-perf-20260924/round46/reference.py
python3 experiments/groebner-perf-20260924/round46/validate.py
```

These are standalone Python/C++ programs and do not use Sage. Validation covers every symmetric binary matrix of orders two and four, seeded dense/sparse/diagonal/zero matrices through order1024, deliberately asymmetric controls, equation-word boundaries, operation counts and malformed ABI extents. It compares every coefficient against a separately written full transform, with direct subset-incidence checks for small cases. Optimized and UBSan binaries are both exercised with32- and64-bit words. Reports bind actual sources and native binaries. CI rebuilds and runs the suite on hosted Linux and macOS CPUs; it makes no physical-device speed claim.

After correctness passes, an optional, separately gated kernel-only timing screen is:

```sh
python3 experiments/groebner-perf-20260924/round46/measure_kernels.py
python3 experiments/groebner-perf-20260924/round46/analyze_kernels.py
```

The frozen [kernel-plan.json](kernel-plan.json) includes mirroring and native call overhead, preserves rejected admissions and noisy trials, and reports all methods. Input reset, symmetry proof and output comparison are outside that kernel interval. It cannot establish complete-query, verification, F4/F5, GPU or IC performance. Output paths are exclusive: existing evidence is not overwritten or silently resumed. Do not run the screen concurrently with another local build, audit or benchmark.

Full checker integration and matched complete-query measurement are subsequent gates. In particular, this experiment does not increase the checker's supported variable count or its coefficient workspace cap.
