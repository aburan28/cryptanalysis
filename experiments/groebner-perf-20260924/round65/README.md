# Independent Metal coefficient transform

This experimental path replaces only the independent certificate checker's
Boolean coefficient subset transform. It does not change the producer, proof
format, accepted ideals, Boolean field relations, or work budgets. CPU remains
the default. Metal must be requested explicitly and requires the full transform
mode. Unavailable Metal is an explicit error, not silent CPU routing.

`transform_backend='metal'` retains the stagewise reference kernel.
`transform_backend='metal_simd'` uses bit-based indexing for the high stages
and combines the lowest stages within 32-lane GPU SIMD groups. It combines five
stages for 32-bit coefficients and four for 64-bit coefficients, or fewer for
small tables. The fused kernel checks the device's SIMD width explicitly. All
threads participate in shuffles, including padded lanes; guarded loads and
stores keep padding outside the coefficient table. The high and low halves of
a 64-bit coefficient stay in separate lanes.

Each check scatters the original packed ANF into its own freshly cleared
coefficient table. Its independent Metal buffer receives every byte anew. A
descending sequence of XOR butterflies evaluates each feature slice. No
producer coefficients, specialized rows, pivots or GPU buffers are shared with
the checker. Existing identity, affine-space, enumeration and basis checks then
consume the returned coefficients. Prepared generations bind the exact fresh
input and preserve device metadata across worker threads. Configuration changes
invalidate preparation. Context locks serialize use and close.

The GPU uses one or two `uint` lanes per coefficient and supports the checker's
32-bit and 64-bit words, including two equation limbs. Logical operation counts
remain the same as the CPU transform. Separate ordinary Metal compute encoders
use explicitly tracked storage in one command buffer. The host waits for
completion before reading the output. This follows Apple's resource conflict
ordering for a normal `MTLCommandQueue`, not Metal 4's untracked queue model:
[Apple resource synchronization](https://developer.apple.com/documentation/metal/resource-synchronization).

The checker retains at most one additional 64 MiB GPU scratch buffer. The
existing CPU coefficient-table limit remains 64 MiB. Audit builds can allocate
a separate reference table and record its size. No target answer is cached.
Device preparation and shader compilation are reusable setup; fresh copy-in,
dispatch encoding, execution/synchronization, copy-out and all verification
remain inside each complete query. Device timestamps are nested diagnostics,
not an additive wall-time breakdown.

## Validation and performance interpretation

Build dependencies through round54 as in the workflow, then run:

```sh
python experiments/groebner-perf-20260924/round65/build.py --metal
experiments/groebner-perf-20260924/round65/build/test-kernel
experiments/groebner-perf-20260924/round65/build/test-kernel-ubsan
experiments/groebner-perf-20260924/round65/build/test-kernel-unavailable
INDEPENDENT_TEST_METAL=1 python -m unittest discover -s experiments/groebner-perf-20260924/round65 -p 'test_checker.py' -v
python experiments/groebner-perf-20260924/round65/validate_queries.py --metal --output /tmp/independent-transform-queries.json.gz
python experiments/groebner-perf-20260924/round65/audit_queries.py --input /tmp/independent-transform-queries.json.gz --output /tmp/independent-transform-audit.json
python experiments/groebner-perf-20260924/round65/measure_diagnostic.py --output /tmp/independent-transform-diagnostic
```

Omit `--metal` and `INDEPENDENT_TEST_METAL` on a portable CPU build. The native
kernel controls cover zero, dense, random and sparse inputs, both word widths,
odd splits, 20 fixed variables and the actual 48,234,496-byte 27-variable table.
Small cases compare against direct subset evaluation; larger cases compare
against a differently ordered CPU transform. Each case also checks the
characteristic-two involution. Certificate tests cover width boundaries,
sanitizers, malicious and valid alternative witnesses, budgets, stale input,
configuration changes, cross-thread preparation and absent backends. Complete
query controls retain source/binary bindings and exact proof hashes; the offline
Python oracle independently checks the original polynomial identities and bases.
The retained-artifact auditor hashes rebuilt binaries without loading them and
reruns the original-equation oracle after validating source bindings. The
balanced diagnostic exercises all six arm orders three times, retaining every
fresh complete query. Its medians remain exploratory and do not enable routing.

These are synthetic algebra/PDP correctness controls. They are not natural
relation-yield estimates or one-target IC/rho measurements. Ordinary-host times
are exploratory. A CPU speedup or CPU/GPU crossover remains unknown without
the repository's host-isolation receipt and a matched full-query panel. Keep
Metal opt-in until that gate passes. This kernel changes constants and memory
execution, not the exponential transform size, and establishes no new F6
algorithm or asymptotic bound.
