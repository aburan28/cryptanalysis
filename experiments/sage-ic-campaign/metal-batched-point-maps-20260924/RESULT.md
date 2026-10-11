# Result: independent point-map batching

The measured operation is a complete warm `FrobeniusPlan` Sage point call:
input validation and packing, backend mapping, point construction, and batch
splitting are charged. Verification and cleanup were recorded separately.
The instance is a degree-131 Koblitz curve with Frobenius power 65 and
public, exact point fixtures. Every group contains 256 points. Values below
are medians of twelve alternating calls in each fresh process, in ms.

| Points / groups | Seed | Metal separate | Metal batched | Metal gain | CPU separate | CPU batched | Metal batched / CPU batched |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,024 / 4 | 2026092401 | 0.907 | 0.457 | 1.98x | 0.376 | 0.339 | 1.35x |
| 4,096 / 16 | 2026092402 | 3.975 | 1.450 | 2.74x | 1.504 | 1.370 | 1.06x |
| 1,024 / 4 | 2026092411 | 0.995 | 0.445 | 2.24x | 0.414 | 0.353 | 1.26x |
| 4,096 / 16 | 2026092412 | 3.977 | 1.401 | 2.84x | 1.466 | 1.358 | 1.03x |

The exact point comparison passed on every call. Warm batched Metal is faster
than separate Metal calls, but batched CPU remains faster for all four cells.
The four-arm process peak RSS was 264–270 MiB; this is a process-level peak,
not an incremental memory cost for the method.

Cold setup and the first complete call were charged in separate Sage
processes to avoid sharing compiled Metal state between arms:

| Points / groups | Metal separate | Metal batched | CPU separate | CPU batched |
| ---: | ---: | ---: | ---: | ---: |
| 1,024 / 4 | 38.848 ms | 27.044 ms | 9.523 ms | 9.548 ms |
| 4,096 / 16 | 31.392 ms | 29.193 ms | 10.856 ms | 10.883 ms |

These cold cells each have one process sample. Setup depends on Metal shader
compilation and process state, so they support the routing decision but not a
stable cold speedup estimate. Their peak RSS was 260–268 MiB. The 512 MiB
limit applies to packed working storage; all measured process peaks also fit
within it.

**Decision:** retain `apply_batches` as an explicit API for consumers with
independent batches under one plan. Do not route automatically to Metal on
this hardware. The next Metal experiment changes the per-element kernel and
will compare full calls with batched CPU and native Sage again. These are
arithmetic-stage measurements only: the IC runner does not yet call this
plan, and no complete verified DLP or end-to-end IC speedup is claimed.
