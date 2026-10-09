# Shared two-output construction for the linked τ atlas

The source formula and protocol were frozen in `cbb31355` before the
native release replay. It constructs `2P−ωP` and `ω(2P)−P` together,
sharing the projective denominator powers and the Y difference.
Preparation costs **70 `M+S`** rather than 75 for the same nine linked
digit orbits. The linked digit stream and evaluator remain identical.
The derivation and exceptional-input condition are in
`TWIN_ORBIT_SEEDS_PROTOCOL.md`.

| Existing frozen panel | Cases | Separate linked preparation and evaluation | Twinned preparation and evaluation | Source saving |
| --- | ---: | ---: | ---: | ---: |
| Original design | 64 | 88,089 | 87,769 | 320 |
| Earlier linked fixture | 256 | 352,827 | 351,547 | 1,280 |
| Edge controls | 30 | 2,481 | 2,331 | 150 |

The saving is exactly five source units per one-use scalar because
only the preparation formula changed. These fixtures were already
inspected in prior experiments; they are **correctness and algebraic
cost controls**, not a newly sampled performance holdout. The
source count excludes field additions, comparisons, memory traffic,
scalar reduction, and final inversion.

The native replay compared every prepared point against independent
Sage linked-seed coordinates: **3,150 seed checks** and **350 final
scalar-output checks** passed. No evaluated cached addition took an
exceptional branch. Both separate and twinned modes matched the same
public point in an untimed paired one-case handoff. The raw release
build, regression, replay, host/compiler, and file hashes are in
`native-linked-twin-checks.json` (SHA-256
`36b628906a852216d0005e0fc5f6dfed11c4d0283c6312b42b725986a0cbc7fb`).
The replayed macOS ARM64 binary SHA-256 is
`685ba7c97b7cfc17cbc0cf789d6e11634591f4d038211279586dc0bf5aec55f5`.

The paired isolated manifest compares complete
`--benchmark-case linked_atlas` and
`--benchmark-case linked_twin` executions on identical scalar/base
inputs. Its structural schema can be checked locally, but a CPU
speedup remains **unknown** without a physical-host isolation receipt.
The structural-only manifest SHA-256 is
`47d2d2eda431bc87cad832ede2140cc7648d9f837605156b03df20b3199fd275`;
`linked-twin-manifest-schema.json` records the synthetic isolation
inputs used for that check.
Shared-input and co-Z point additions have prior art; a specific
novelty claim for this specialization requires a broader literature
and formula comparison.
