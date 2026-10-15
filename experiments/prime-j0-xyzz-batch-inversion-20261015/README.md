# Batched affine recovery for radix-14 scalar multiplication

The fixed `371−τ` fourteen-position evaluator computes a batch of 128 independent secp256k1 scalar outputs in XYZZ coordinates, multiplies their nonzero `ZZZ` values into a prefix chain, performs one field inversion, and recovers all 128 affine points with reverse products. The ordinary evaluator inverts once per point. In a frozen same-point Tier 1 panel, this measured **2.2091× sustained 128-output batch throughput**, with repeat-bootstrap 95% interval **[2.1926,2.2123]**. All 96 arms and 48 pairs verified, every adjacent A/A control passed [0.90,1.11], and the native path passed a 128-point independent binary holdout and identity-point boundary check.

| Evidence | Artifact |
| --- | --- |
| Hash-guarded two-file native overlay and tests | [`native_batch_inverse_overlay.py`](native_batch_inverse_overlay.py), [`linux-test.log`](linux-test.log), [`linux-build.log`](linux-build.log) |
| Frozen 128-output batch comparison | [`linux-preflight.stdout`](linux-preflight.stdout), [`tier1-batch-rules.json`](tier1-batch-rules.json), [`tier1-batch-manifest.json`](tier1-batch-manifest.json) |
| Prefix/reverse batch-inversion proof and axiom audit | [`BatchInverse.lean`](BatchInverse.lean), [`check_lean.sh`](check_lean.sh), [`lean-check.log`](lean-check.log) |
| Complete 128-output Tier 1 panel and independent A/A audit | [`174c6ea48bab420a9f19f745c9381f16`](174c6ea48bab420a9f19f745c9381f16), [`xyzz-batch-panel.tar.gz`](xyzz-batch-panel.tar.gz), [`analyze_batch_tier1.py`](analyze_batch_tier1.py), [`tier1-batch-analysis.json`](tier1-batch-analysis.json) |

The overlay requires window source SHA-256 `b45a8c0034ee9b2bae9f29fd27b39b864d7cf1e153efead92f854e85825276da` and front-door source SHA-256 `906b58087bec06fbb12ec5d1954ecdace2af3c44b8bb78c6589954554f450015`. It produces hashes `7272a3a818dac0fd38e028f91ba4bb75630a40849fc2375bdd0d14b20483ce62` and `65cd774f8916721340ddec872dfa76522f496a5547c088acb3668016f3aa3c36`; the release binary is `a9443b87cd6faed0c02b1b7be75cdc1984f3bd7f983eeb8ef467e1bc3eb9a5e6`.

The batch operation shares an inversion across 128 **independent outputs** in each pass; no inversion is shared across the 96 passes. All table preparation and input parsing precede the timed interval; point accumulation, prefix/reverse products, the shared inversion, and affine encoding are included. Output verification follows the interval and is recorded for every output. The complete raw archive SHA-256 is `bc2e434820d6866176a367c2a63c008699357e8aec97fac86e1adc7e1fbbb274`.

| Frozen Tier 1 result, 12,288 outputs per arm | Shared inversion per 128 outputs | Individual inversions |
| --- | ---: | ---: |
| Mean online interval per arm | 61.706 ms | 136.820 ms |
| Mean online time per scalar in the batch | 5.022 μs | 11.134 μs |
| Mean table preparation | 3,963.869 ms | 3,954.631 ms |
| Retained native table bytes | 26,035,988 | 26,035,988 |

The paired median individual/shared online ratio is **2.209114**. This is a 128-output batch-throughput result; it does not describe one-call latency. The declared cloud-instance Tier 1 gate passed on one RunPod allocation, while physical-host Tier 0 isolation was not established.

Lean 4.34.1 checks `BatchInverse.prefix_reverse_identity`: for an associative, commutative multiplication, exact forward prefix products, one final inverse witness, and the reverse recurrence used by the native path, every emitted factor-wise inverse witness multiplies its factor to the unit. The theorem is quantified over every batch length and every factor sequence, with the final inverse property stated explicitly. `#print axioms` reports only `propext` and `Quot.sound`. The concrete Montgomery-field bridge and point-output checks are supplied by the native 128-case and identity replay; a full Lean model of the native field remains open.
