# Shared-Z degree-seven scalar replay

This is a verified secp256k1 research path, not a controlled CPU speedup
result. The scalar is first reduced to a short representative in
`Z[τ]`, where `τ = 1 - ω`. The recoder can divide by `τ`, `2`, `ρ = 2 - ω`,
or its conjugate. A compact exact tail policy handles states with norm at
most 4096. The evaluator aligns the nine prepared digit points to one
projective Z, performs mixed additions on the scaled curve, and restores the
output Z once.

## Frozen correctness and source accounting

The Rust release executable was run sequentially against all 256 cases of
`fresh-fixture.json`. Every output matched its independently frozen affine
point. The native unit tests cover both degree-seven formulas against group
addition over several Jacobian gauges and reconstruct all 29,688 tail
states for both pending-pair flags. `cargo test` passed 42 tests.

| Same 256 scalar cases | Total modeled M+S | Change from selector |
| --- | ---: | ---: |
| Existing zero-τ/selective selector | 345,972 | reference |
| Shared-Z zero-τ, radix 2 | 335,933 | 2.90% lower |
| Shared-Z degree seven without tail | 335,685 | 2.97% lower |
| Shared-Z degree seven with tail | **333,095** | **3.72% lower** |

The tail reduces the shared-Z zero-τ source count by 0.85% on this panel.
`source_M_plus_S` counts the implemented field multiplication and squaring
formulas, including seed preparation, common-Z alignment, scalar steps, and
digit additions. It does not capture instruction scheduling, memory traffic,
branch behavior, or field operation latency. All values above are operation
counts, not CPU timings.

`generate_shared_z_tail.py` computes shortest paths over 29,688 states and
138,240 transitions. Sixfold unit symmetry stores 4,948 state/action slots
in `shared-z-tail4096.bin` (5,329 bytes; SHA-256
`944a40b13e60a8138d67ecb5abc5951164afbf4f3446059f99af9aa8e5f6330c`).
The generator refuses to replace the table if its bytes change. The longest
decoded tail uses seven steps.

## Isolated timing handoff

`make_shared_z_degree_seven_manifest.py` builds a paired 256-point manifest for the
repository's [isolated benchmark service](../../docs/ISOLATED_BENCHMARKS.md).
Both arms use the same release binary and fixture. The reference is
`--benchmark-shared-z-zero-tau-case`; the candidate is
`--benchmark-shared-z-degree-seven-tail-case`. Each arm starts its internal
`online_ms` timer before scalar and base parsing and stops after the scalar
result matches the frozen point. Fixture loading, process launch, and lazy
constant-table initialization are outside the interval. The service pins the
declared CPU and NUMA resources, alternates pair order, verifies the frozen
input and result fields, and rejects noisy or incomplete pairs.

The manifest generator was checked with the service's schema validator, and
both timed CLI modes produced valid fields and the frozen result for one
case. No host-qualified timing receipt exists for this variant. Consequently
the CPU speedup remains unknown. The recoder is variable time and must not
be used with secret scalars. Academic novelty of this particular combination
has not been established.
