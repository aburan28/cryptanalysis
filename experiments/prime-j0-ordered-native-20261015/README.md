# Native ordered prime-norm fourteen-position evaluator

The ordered `394−τ, 380−τ, 380−τ, (371−τ)×11` scalar format has a native secp256k1 evaluator and a qualified same-point Tier 1 comparison. Three digit atlases are shared across fourteen position-specific point windows. The implementation passed exhaustive residue/congruence/norm checks for norms 154,057, 143,263, and 136,531, plus an independent 128-point binary scalar holdout. Across all 96 verified arms and 48 valid pairs, the ordered evaluator measured **0.98555× the fixed `371−τ` format's sustained hot-table throughput**, with repeat-bootstrap 95% interval **[0.97984,0.98842]**. Every adjacent A/A control passed [0.90,1.11].

| Evidence | Artifact |
| --- | --- |
| Hash-guarded native overlay and test/build receipts | [`native_ordered14_overlay.py`](native_ordered14_overlay.py), [`linux-test.log`](linux-test.log), [`linux-build.log`](linux-build.log) |
| Frozen scalar preflight and same-point panel | [`linux-preflight.stdout`](linux-preflight.stdout), [`tier1-ordered-rules.json`](tier1-ordered-rules.json), [`tier1-ordered-manifest.json`](tier1-ordered-manifest.json) |
| Complete raw panel and independent A/A audit | [`895830fdb95347f5873a7f35656e5a1c`](895830fdb95347f5873a7f35656e5a1c), [`radixordered14-panel.tar.gz`](radixordered14-panel.tar.gz), [`analyze_ordered_tier1.py`](analyze_ordered_tier1.py), [`tier1-ordered-analysis.json`](tier1-ordered-analysis.json) |

The overlay requires source SHA-256 `aff42df465e44e2f3fe1d10c524b6a336a76c5091791894cac5cba618cc441ee`, produces source SHA-256 `a35a0532cd190d5d7aa830d74fc0c5793bbaffe2be2226d2d569893c9e3be0ad`, and the release binary SHA-256 is `756ea3b99af4deed650934b8d404d5e8ecda8b60063f9933878bed6a212eb4dc`. The complete raw archive SHA-256 is `0312476c8848f76733ed23d7b756fe71ee708bf4b8c3f23c2964ed3e73d4d9be`. The direct point payload is 22,267,136 bytes versus 22,313,920 bytes for fixed radix 14; retaining three digit atlases and terminal-code metadata raises total native memory by 520,720 bytes.

| Frozen Tier 1 result, 12,288 scalars per arm | Ordered 14 positions | Fixed `371−τ` reference |
| --- | ---: | ---: |
| Mean online interval per arm | 137.806 ms | 135.634 ms |
| Mean online time per scalar | 11.215 μs | 11.038 μs |
| Mean preparation | 3,971.307 ms | 3,956.667 ms |
| Retained native bytes | 26,556,708 | 26,035,988 |

The paired median reference/candidate online ratio is **0.985551**. The online interval is Rust `Instant` around 96 passes over the same 128 frozen point multiplications and affine recovery after table preparation; all outputs were checked afterward. This result is sustained hot-table throughput on one cloud allocation. The physical-host Tier 0 conditions and one-call latency are separate gates. The fixed format is the stronger measured option under this resource envelope.

The [exact shape screen, affine replay, and checked Lean radius theorem](../prime-j0-fourteen-position-mixed-radix-20261015/README.md) specify the ordered mathematical format. The current native tests cover concrete outputs and digit conditions; a candidate-specific Lean theorem connecting all selected digits to the secp256k1 point action remains the formalization step.
