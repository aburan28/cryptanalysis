# Exact point-kernel operation diagnostic

On the frozen 4,096-scalar panel, the tau-preexpanded mode uses **40,697 fewer field multiplications and 12,288 fewer squarings** than the original nineteen-window mode at the cost of 1,404,736 additional retained table bytes. It also uses **24,577 fewer multiplications and 12,288 fewer squarings** than orbit-X at equal retained table bytes. All three modes returned the same point for every scalar in the diagnostic test.

| Native mode | Field adds | Field subs | Field muls | Field squares | Bucket gauge rotations |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original nineteen-window | 98,294 | 493,470 | 638,632 | 233,442 | 16,120 |
| Orbit-X | 98,294 | 493,470 | 622,512 | 233,442 | 0 |
| Tau-preexpanded | 73,718 | 481,182 | 597,935 | 221,154 | 8,191 |

These are exact calls to the native `u256_add`, `u256_sub`, `u256_mul`, and `u256_square` wrappers after prewarming all tables and resetting the counters before each scalar/mode. They include point addition, online tau where applicable, unit/gauge transforms, and exceptional branches taken on this panel. They exclude table construction, scalar recoding outside these wrappers, final binary inversion, output conversion, and hardware timing. The same 4,096 scalar inputs and one source-instrumented binary are used for all three modes.

`ops-diagnostic.patch` is the counter-only change against the frozen mode-140 source. `ops-diagnostic.json` binds that patch, both source hashes, the input, raw test log, and the counting boundary. Rebuild in a separate scratch checkout with this patch and run `TMPDIR=/private/tmp cargo test --release --bin eisenstein_fixed frontier19_exact_point_kernel_operations -- --nocapture`.
