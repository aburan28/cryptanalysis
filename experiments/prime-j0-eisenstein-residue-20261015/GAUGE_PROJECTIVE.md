# Projective join of gauge-class affine sums

The [projective overlay](native_gauge_projective_overlay.py) changes the
last join in the radix-14 gauge-class scalar pipeline. It first computes
the three class sums with the existing batch-affine tree. After rotating
each class sum, it joins the available sums in XYZZ coordinates with mixed
addition. A single batch inversion recovers all 128 final affine outputs.
The point table and scalar recoder are unchanged from the gauge-layer
candidate; retained table storage is **26,035,988 bytes**.

The overlay is guarded by the gauge-layer front and window source SHA-256
values `5ef632cd74ea7bc3ec38ce7b815481bf91cd56e8d2444621e1d010a95ea8edee`
and `3650b42e1ff33c761efd7fd73a3dac4c12a21111afe5fbc8ac73b4e0782557bd`.
Its resulting front, window, and Linux release binary SHA-256 values are
`8b1eefde25f2e3881611ef31d1333d11a76c4e854f002de880fe19f7b83377f4`,
`9b103346a8bb5a4594c0f26fc073a9dc92faa7121d4c97a71b0e7944a258bdb9`,
and `7db95bf8adeda3c907e7b3c24420041397916a6a8e6c5fa5dae288e50003fdde`.
Applying the overlay again to the frozen source locally reproduced both
resulting source hashes.

The x86-64 candidate reproduced all **12,288 independently computed points**
in the frozen uniform-derived fixture, SHA-256
`a1c4964f174e36ea26f6a1897128f651a2ce7251e4bf4ffd532ff09221e721d3`.
The direct full-stream diagnostic measured **72.044163 ms** for 96 batches
of 128 scalar multiplications, with output checks outside the timed interval.
This direct time is exploratory. The frozen
[Tier 1 manifest](tier1-eisenstein-gauge-projective-cpu40-manifest.json)
and [rules](tier1-eisenstein-gauge-projective-cpu40-rules.json) compare the
projective join with the previous gauge affine join in 16 alternating
repetitions, bracketed by adjacent A/A controls on CPU 40. Serial RunPod
job `792dca682b8d4aa799e4745fb7dd1ce9` completed all **96 arms and
48 pairs** with stable artifacts. The
[independent audit](tier1-eisenstein-gauge-projective-cpu40-audit.json)
checked every raw arm, both source chains, both binaries, the overlay
replay, and all adjacent A/A controls. Every control passed the frozen
`[0.90,1.11]` gate.

| Same 12,288-scalar stream | Gauge affine join | Gauge projective join |
| --- | ---: | ---: |
| Mean timed interval | 69.059095 ms | 70.361658 ms |
| Retained table | 26,035,988 bytes | 26,035,988 bytes |

The qualified paired median reference/projective ratio is **0.983894**,
with a predeclared paired bootstrap 95% interval
`[0.974294,0.988284]`. The projective join is slower by this matched
comparison under the observed Tier 1 cloud-instance envelope. It therefore
does not improve the gauge path's measured wall time. The previous packed
and gauge comparison against the two-x table retains its independent
**unknown after gate** status; the present same-gauge comparison does not
repair that earlier panel's failed controls.

The [raw panel](792dca682b8d4aa799e4745fb7dd1ce9/) and its
[archive](792dca682b8d4aa799e4745fb7dd1ce9.tar.gz) retain every arm.
The raw archive SHA-256 is
`34fb7b4b152f5ef0a5aa18790a3f59dfd0367640fc2b8e721e6166b7a8a52c43`.
The [source and binary provenance archive](eisenstein-gauge-projective-native-provenance.tar.gz)
has SHA-256 `57bc84eebb2f588beb2c658705a9b4e7a35aa713ac770dd5bd9c9379ea53e6da`.
