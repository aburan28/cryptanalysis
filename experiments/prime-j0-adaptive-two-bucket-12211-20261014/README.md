# Adaptive two-bucket fusion for the 18-position multiplier

This variant uses the same norm-12,211 radix, canonical digits, 18 positions,
and affine tables as the [three-bucket parent](../prime-j0-split-prime-12211-20261014/README.md).
It recodes the scalar before curve addition, counts the points assigned to
unit buckets 1 and 2, and rotates the smaller bucket's affine points into
bucket 0. The final sum then uses at most one projective join and one bucket
rotation. Table size stays at **2,626,858 retained bytes**. The exact number
of extra per-point `x` multiplications is recorded for each scalar.

For unit code `2j+s`, where `j∈{1,2}` and `s∈{0,1}` is the sign, the stored
point can be transformed by `ωʲ` before insertion into bucket 0. The
[Lean proof](AdaptiveBucketFusion.lean) checks that this gives the same
integer-coefficient unit image for both buckets and either sign. The
[native overlay](native_overlay.py) uses the existing secp256k1 Solinas
field multiplier to apply that `x` rotation to the affine point. The native
unit-image test checks this direct affine transform against the existing
projective unit action; scalar replays check the full curve-point result.

The [frozen fixture screen](screen.json) finds 632 per-point rotations
across 128 scalars, a mean of 4.9375. Case 0 chooses bucket 1 and rotates
eight affine points. These counts describe the specified fixture and give a
concrete arithmetic tradeoff; they are not a CPU speed measurement.

The independently verified case-0 operation profile has **17 nontrivial
mixed additions, one projective join, one final bucket rotation, and eight
per-point affine `x` rotations**. The three-bucket parent has 16 mixed
additions, two projective joins, and two final bucket rotations on the same
case. This identifies the exact field-operation exchange that the cloud
panel must evaluate. Both variants retain 18 digit reads and one terminal
read on this case.

| Check | Evidence |
| --- | --- |
| Integer unit folding | `AdaptiveBucketFusion.chosen_bucket_fusion`, Lean 4.34.1; axiom audit in `lean-check.log`. |
| Affine point rotation and scalar replay | `native-test.log`. |
| Frozen case-0 operation profile | `native-case0.log`. |
| Source, binary and proof hashes | `validation.json`. |

Reproduce from a byte-identical generated norm-12,211 Cargo directory:

```sh
python3 experiments/prime-j0-adaptive-two-bucket-12211-20261014/native_overlay.py \
  /private/tmp/prime-j0-adaptive-two-bucket-12211-native
CARGO_TARGET_DIR=/private/tmp/prime-j0-split-prime-8011-target cargo test \
  --manifest-path /private/tmp/prime-j0-adaptive-two-bucket-12211-native/Cargo.toml \
  --offline --locked --release --bin eisenstein_fixed split_prime_ \
  -- --test-threads=1 --nocapture
```

Wall-time ranking against the three-bucket parent requires an alternating,
same-scalar Tier 1 panel with A/A calibration. The current RunPod account
balance prevented worker allocation, so that comparison remains pending.
