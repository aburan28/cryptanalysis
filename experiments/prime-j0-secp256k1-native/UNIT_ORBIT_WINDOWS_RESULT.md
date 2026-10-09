# Eisenstein unit-orbit windows: frozen screen

The 14-window construction reduced the declared point-operation proxy
from **894,371 to 585,728** across the untouched 4,096-scalar holdout,
a **34.51%** reduction. Every scalar representative reconstructed
exactly, and every case improved under this proxy. The candidate uses
one point from each of 14 positional tables, with at most 13 mixed
additions and no online point doubling or tau step.

| Panel | Cases | Graph-aware parent proxy | Unit-orbit proxy | Saving | Regressions | Exact reconstructions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Design | 2,048 | 447,972 | 292,864 | 34.62% | 0 | 2,048 |
| Holdout | 4,096 | 894,371 | 585,728 | 34.51% | 0 | 4,096 |

The [protocol](UNIT_ORBIT_WINDOWS_PROTOCOL.md) and
[checker](unit_orbit_windows_screen.py) were committed in `4938fc1e`
and PR #542 was open before the holdout. The design receipt was
committed in `1e9e9944`. The disjoint [design](unit-orbit-windows-design.json)
and [holdout](unit-orbit-windows-holdout.json) receipts contain scalar
input hashes, all per-case proxy deltas, orbit-map and digit hashes,
baseline binary and source hashes, and every exact reconstruction.
Both panels checked the first 128 baseline cases against the frozen
native graph-aware binary.

The radix-1024 map has 174,764 unit orbits, and the radix-512 map has
43,692. Three large and eleven small positional tables retain
1,004,904 slots including identity slots. At the existing 72-byte
affine format, the points need 72,353,088 bytes. The two four-byte
residue maps need 5,242,880 bytes. Their declared total is
**77,595,968 bytes**, leaving 16,775,872 bytes under 90 MiB for
metadata and alignment. The native implementation reports **78,470,128
retained payload bytes**, including its orbit digits, table pointer
array, and metadata. This is the exact size of its retained Rust
allocations before allocator rounding and page mapping.

The native implementation's full-table test checked all **1,004,904**
slots against independently built group sums, including the fourteen
identity placeholders. The separate [native verification
receipt](unit-orbit-windows-verify.json) records 6,492 point outputs
matched to the frozen graph-aware parent, 261 independently multiplied
points, all 129 expected fixture points, and exact agreement with both
screening panel totals. The Rust point-addition tests cover identity,
equal, and inverse inputs.

The screening proxy counts point operations and excludes scalar
decomposition, residue-map lookups, unit action, table traffic, and
final affine conversion. The RunPod CPU Pod's strict preflight rejected
the timing job because its Docker allocation lacks a host-level isolated
partition, fixed frequency, and IRQ routing. The next measurement is a
paired online wall-time run on a host that passes that preflight; until
then the wall-time speedup is unknown.
