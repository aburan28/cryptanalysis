# Automatic CPU route: local result and control limitation

The route is limited to exact list/tuple batches of at least 4,096 points,
field degree 67 or 131, normalized Frobenius power 65, and an NTL codec.
A routed first call includes lazy CPU table construction. Each reported
cold total charges plan setup, the first Sage-point output, exact
verification, output cleanup, and plan close. Warm calls charge the same
output and verification work using the existing plan.

`run-003/` repeated 10 cases on fresh seeds with 48 balanced fresh-plan
pairs per case and eight warm calls per arm. All **46,006,272 outputs**
matched Sage's Frobenius isogeny. The routed results are:

| Phase | GF(2^m) | Points | Power | Cold auto/Sage | Warm auto/Sage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Primary | 67 | 4,096 | 65 | 4.495× | 12.819× |
| Primary | 131 | 4,096 | 65 | 3.961× | 13.638× |
| Primary | 131 | 16,384 | 65 | 7.615× | 12.282× |
| Confirmation, a=0 | 67 | 8,192 | 65 | 8.017× | 11.763× |
| Confirmation, a=0 | 131 | 6,144 | 65 | 4.286× | 13.321× |
| Confirmation, alternate modulus | 131 | 4,096 | 65 | 3.980× | 16.607× |

The routed cold geometric means are **5.137× primary** and **5.152×
independent confirmation**. The corresponding warm means are 12.901×
and 13.755×. Every routed cold cell exceeds the frozen 1.10× threshold.
The exploratory `run-001/` explains the 4,096-point threshold: degree-131
power-65 cold CPU was slower at 256 points, near parity at 1,024, and
faster from 2,048 onward on that input set. The rule chooses the larger
measured threshold for headroom.

## Nonrouted controls

The original acceptance plan required every nonrouted wall-time ratio to
remain at least 0.98×. It failed in both paired runs. In `run-003/`,
the primary nonrouted cold ratios were 1.065× and 1.026×; independent
confirmation measured **0.820×** and **0.991×**. The 0.820× value must
not be hidden or counted as a pass. The implementation calls the same
`frobenius_points` function for both arms when no route is selected, with
only a predicate before that call. The observed large changes in both
directions are therefore inferred to reflect shared-host timing variation.

The separately frozen `control-001/` measured that predicate on the same
plan with one million repetitions per batch. Its median incremental cost
was 0.122–0.126 microseconds per call, at most 0.00336% of a representative
complete Sage call. It also confirmed one direct Sage function call per
nonrouted invocation. This supports a negligible steady-state overhead;
it does **not** turn the failed nonrouted wall-time gate into a pass.
Users who require that strict empirical gate should wait for quieter-host
confirmation before merging.

Fresh-process peak RSS for degree 131, 4,096 points rose from 272,285,696
to 276,955,136 bytes (4.45 MiB, 1.72%), within the frozen 5% resource
limit. Three auto-routing contract groups and six installed CPU/Metal
hardware groups passed. The tests cover routing, fallback when the native
library is missing, nonrouted powers and sizes, iterators, reuse, close,
and exact output points. Device-specific GPU speed is not claimed.

This is a point-map routing result, not a complete index-calculus or
verified discrete-logarithm speedup.
