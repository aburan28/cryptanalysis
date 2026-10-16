# Rotated endomorphism radix step

The `31+32τ` Horner step can be evaluated with the secp256k1 order-three x rotation `ω`. Since `τ=1−ω`, the same endomorphism is `63−32ω`. For `Q=32P`, the native candidate computes `(2Q−P)−ωQ`, using six doublings, two projective additions, and one x rotation per nonidentity step. The [hash-guarded overlay](native_sparse_rotated_step_overlay.py) changes only this radix step and the pilot entry point relative to the adaptive digit-graph source.

The [Lean module](RotatedRadixStep.lean) checks `τ=1−ω` in the exact `(a,b)` lattice coordinates, the `63−32ω=31+32τ` identity, and its transfer to a point map under explicit addition, subtraction, scaling, and endomorphism hypotheses. The [fresh pinned build receipt](rotated-radix-step-lean-check.json) records all three `#print axioms` outputs. The native arithmetic and curve-coordinate refinement remain separate proof obligations; the exact-output replay below exercises them empirically.

## Frozen Tier 1 comparison

The [one-scalar](tier1-tau32-rotated-step-1-cpu40-manifest.json) and [128-point](tier1-tau32-rotated-step-128-cpu40-manifest.json) plans were committed before dispatch. They pair the rotated step with the preceding digit-graph path on the same frozen points and CPU 40 of RunPod pod `thyvmdqmzsz5ik`. Sixteen alternating repeats have adjacent reference/reference A/A controls. The [rules](tier1-tau32-rotated-step-1-cpu40-rules.json) and [rules](tier1-tau32-rotated-step-128-cpu40-rules.json) fix the `[0.90,1.11]` noise gate and paired interval criterion. Rust `Instant` includes scalar-local digit preparation and Horner evaluation; process launch, fixture loading, and external replay are outside it.

| Workload | Graph reference mean | Rotated candidate mean | Qualified paired reference/candidate median | Paired bootstrap 95% interval |
| --- | ---: | ---: | ---: | ---: |
| One scalar | 0.561 ms | 0.544 ms | 1.012× | [1.003, 1.035] |
| 128 points | 39.898 ms | 39.170 ms | 1.021× | [1.010, 1.025] |

The [independent auditor](analyze_tier1_tau32_rotated_step.py) checked exact source and binary hashes, all raw commands/stdout/stderr and pair records, independent scalar replay of every measured fixture point, stable artifacts, and A/A controls. Each panel completed **96 valid arms and 48 valid pairs**. The [one-scalar launch](tier1-tau32-rotated-step-1-cpu40-launch.json), [audit](tier1-tau32-rotated-step-1-cpu40-audit.json), and [raw archive](tau32-rotated-step-1-raw.tar.gz) identify job `c61069334c8a4d83bebbb05dc242e1b2`. The [128-point launch](tier1-tau32-rotated-step-128-cpu40-launch.json), [audit](tier1-tau32-rotated-step-128-cpu40-audit.json), and [raw archive](tau32-rotated-step-128-raw.tar.gz) identify job `93837f49c72c4f0d9311366066628dc7`. The [native provenance archive](tau32-rotated-step-native-provenance.tar.gz) preserves both exact source trees, binaries, overlays, and build output.

## Full-fixture correctness

The separately [frozen manifest](tier1-tau32-rotated-step-full-replay-cpu40-manifest.json) and [rules](tier1-tau32-rotated-step-full-replay-cpu40-rules.json) sent two identical candidate arms through the serial worker. Job `09eeb419886a43e393492b4511a8c233` completed with stable artifacts and checked all **12,288** frozen outputs in each arm. The [auditor](analyze_tier1_tau32_rotated_step_full_replay.py), [launch](tier1-tau32-rotated-step-full-replay-cpu40-launch.json), [audit](tier1-tau32-rotated-step-full-replay-cpu40-audit.json), and [raw archive](tau32-rotated-step-full-replay-raw.tar.gz) retain the record. The two intervals were **3.699 s** and **3.712 s**. This A/A replay has a null speedup field.

The measured gain is small under one cloud-instance envelope. A separately frozen replication on another allocation would test transfer before changing the default arithmetic route.
