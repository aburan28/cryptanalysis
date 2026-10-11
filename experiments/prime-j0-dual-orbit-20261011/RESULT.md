# Folded norm-seven orbit cover on secp256k1

The radix-1024 fixed-base format reduces the native retained table from
66,470,376 to 54,339,936 bytes, a reduction of 12,130,440 bytes
(18.25%), by covering more residue classes with the norm-seven map
`rho=1+tau`. The native evaluator folds its bucket into the two existing
tau buckets using `rho(R)=R+tau(R)`. All 4,096 new, disjoint scalar cases
matched the prior exact implementations; the first 128 also matched
independent binary multiplication. Ten edge-fixture cases passed.

## Construction and verification

The full residue universe has 1,048,576 pairs modulo 1024 and 174,764
six-unit classes. For a seed `S`, the low-cost `rho0` cover permits
`S`, `tau(S)`, `tau^2(S)`, and `rho(S)` when the digit norm remains at most
`1024^2`. Deterministic maximum-gain greedy selection gives 67,338 seeds.
The twelve full windows contain 808,056 affine entries; the exact terminal
window adds 9,288, yielding 817,344 entries and 52,310,016 affine payload
bytes. The direct-class native atlas adds 1,667,480 bytes, with the
remaining retained count supplied by the terminal atlas and constants.

The independent verifiers checked every residue assignment in each
low-cost cover and every direct-class native record and transformed
residue. The 256-scalar design point replay checked both `rho0` and
`rho0_bar0` against independent binary multiplication. The fresh native
test checked 4,096 scalars against the direct-index and fused formats.

| Format | Full-window seeds | Affine payload bytes | Native retained bytes | Fresh-panel recoding counter | Fresh-panel gauge rotations |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fused prior format | 83,051 | 64,377,600 | 66,470,376 | 49,152 | 16,526 |
| Folded `rho0` | 67,338 | 52,310,016 | 54,339,936 | 49,152 | 21,978 |

The recoding counter is the sum of `max(0, nonidentity terms - 1)` and is
not an instrumented count of mixed additions or final bucket merges. The
counter and gauge-rotation columns use the same 4,096-scalar panel. The
norm-seven bucket requires extra projective merges when active; the added gauge
rotations are 5,452 across this panel. These counts identify the memory
and point-work tradeoff without treating a contended host as a timing
comparison.

Two broader design covers also passed complete residue and recoder checks:
`rho0_bar0` uses 57,528 seeds and 44,775,936 affine payload bytes;
`rho0_bar012` uses 52,672 seeds and 41,046,528 bytes. Their additional
norm-seven branch work has not entered a native runtime comparison.

## Replay state

The local targeted native test passed 1/1 with 4,096 cases. The local
edge-fixture verifier passed 10/10. The complete local native suite passed
141/141 on the preceding materialization; the final materialization changes
only the test's paired operation-count reporting, and its targeted and
edge checks passed. The queued Linux replay runs that final materialization's
entire suite.
The source-pinned Linux correctness job is queued as
`20261011T042142Z_prime-j0-dual-rho0-linux-1d8826c_dbExex` at commit
`1d8826c3bce244eea8bc9f844d630bcd909dab15`. Its runner permits one
job at a time; the pre-existing N131 replay was active at dispatch.
The Linux job records correctness and host evidence. A controlled runtime
comparison requires the host isolation receipt defined in
`docs/ISOLATED_BENCHMARKS.md` and a paired run on the same scalar panel.
