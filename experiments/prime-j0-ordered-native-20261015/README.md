# Native ordered prime-norm fourteen-position evaluator

The ordered `394−τ, 380−τ, 380−τ, (371−τ)×11` scalar format now has a native secp256k1 evaluator. Three digit atlases are shared across fourteen position-specific point windows. The implementation passed exhaustive residue/congruence/norm checks for norms 154,057, 143,263, and 136,531, plus an independent 128-point binary scalar holdout. A 96-pass standalone preflight verified all 12,288 outputs and reported 26,556,708 retained bytes and 3,970.78 ms preparation. Its 138.03 ms online interval is a diagnostic; the frozen direct Tier 1 panel compares it with the fixed `371−τ` fourteen-position reference.

| Evidence | Artifact |
| --- | --- |
| Hash-guarded native overlay and test/build receipts | [`native_ordered14_overlay.py`](native_ordered14_overlay.py), [`linux-test.log`](linux-test.log), [`linux-build.log`](linux-build.log) |
| Frozen scalar preflight and same-point panel | [`linux-preflight.stdout`](linux-preflight.stdout), [`tier1-ordered-rules.json`](tier1-ordered-rules.json), [`tier1-ordered-manifest.json`](tier1-ordered-manifest.json) |

The overlay requires source SHA-256 `aff42df465e44e2f3fe1d10c524b6a336a76c5091791894cac5cba618cc441ee`, produces source SHA-256 `a35a0532cd190d5d7aa830d74fc0c5793bbaffe2be2226d2d569893c9e3be0ad`, and the release binary SHA-256 is `756ea3b99af4deed650934b8d404d5e8ecda8b60063f9933878bed6a212eb4dc`. The three digit atlases are retained once each; distinct point windows are retained for each of the fourteen positions. The 22,267,136-byte direct point payload from the exact shape screen is smaller than the fixed radix's 22,313,920 bytes, while atlas and terminal-code metadata raise total retained memory above the fixed native evaluator's 26,035,988 bytes. The frozen panel will test whether the ordered recoder's online cost offsets that memory tradeoff.

The [exact shape screen, affine replay, and checked Lean radius theorem](../prime-j0-fourteen-position-mixed-radix-20261015/README.md) specify the ordered mathematical format. The current native tests cover concrete outputs and digit conditions; a candidate-specific Lean theorem connecting all selected digits to the secp256k1 point action remains the formalization step.
