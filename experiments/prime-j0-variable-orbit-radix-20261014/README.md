# Seventeen-position `140−τ` orbit radix

The prime-norm radix `140−τ` reduces the fixed-base recoding to **17 positions** while retaining a 3,714,752-byte direct point payload. This places it between the measured 18-position norm-12,211 rolling format (2,448,196 retained bytes) and the 16-position norm-35,533 direct format (6,829,948 retained bytes). The payload counts only 64-byte affine points; the native retained-byte total includes metadata and table alignment and will be measured separately.

For `τ²−3τ+3=0`, the radix norm is `140²−3·140+3 = 19,183`. The selector checks two residue lifts and three centered `b` values per lift, minimizing `(norm, |b|, |a|, a, b)`. The exact screen verifies all 19,183 residue congruences, sign and six-unit covariance, and the global minimum for all 9,592 sign-canonical residues under the norm-derived `|b| ≤ 93` bound. Its maximum digit norm is 6,348. The 17-step contraction ends below norm `78²`; the digit table has 3,198 six-unit orbit seeds and the terminal table has 3,677.

| Evidence | Artifact |
| --- | --- |
| Selector, orbit, radius, and 128-scalar recoding screen | [`screen140.py`](screen140.py), [`screen140.json`](screen140.json) |
| Independent affine secp256k1 replay on 388 scalars | [`group_replay140.py`](group_replay140.py), [`group-replay140.json`](group-replay140.json) |
| Guarded Rust overlay from the frozen norm-35,533 batch source | [`native140_overlay.py`](native140_overlay.py) |
| Prespecified Tier 1 18-versus-17 panel | [`tier1-18v17-rules.json`](tier1-18v17-rules.json), [`tier1-18v17-manifest.json`](tier1-18v17-manifest.json) |

The affine replay reconstructs each point from window bases `πⁱG`, six-unit orbit actions, and the terminal point, then checks it against independent binary scalar multiplication. It includes the existing 128-case fixture and 260 fresh or boundary scalars. The native overlay applied to frozen parent source SHA-256 `858089fac6083f123c4a9e86afe9cef9db9d24dfdc78df3546d4bed74165e52e`, producing source `e195374c4e6fde368bdba106c769c6335cd319f9f5547e8e2291089fe055335e` and release binary `5b6e9eaf792dafb0d9863a7d04c2dbe29b5156ea0af1f7e3e92b0094fbbf24a5` on the RunPod Linux pod. Its exhaustive 19,183-residue test and 128-case independent-binary holdout passed. The retained table is 4,178,836 bytes including metadata. The first remote test command recorded a `cargo` PATH failure; the corrected absolute-toolchain run passed, and both logs are preserved in the pending panel artifacts.

The table-shape and correctness results are algorithmic diagnostics. The prespecified Tier 1 panel pairs this binary with the 18-position rolling binary on the same frozen 128 scalars, 64 passes per arm, 16 alternating repetitions, and adjacent A/A gates. Its rule file fixes [0.90,1.11] as the acceptance interval before submission. One-call latency requires its own A/A-gated panel.

The full formal proof is in progress. The intended Lean obligations are the exact six-candidate selector and tie rule, the 17-step terminal bound from the selected lattice representative, and the point action under the fixed secp256k1 τ eigenvalue. The existing `190−τ` modules establish the corresponding framework; their numeric radix constants and finite residue certificate do not transfer to this candidate without a new build.
