# Priority assignment for the norm-seven orbit cover

The fixed 67,338-seed radix-1024 cover admits multiple valid representations
for 60,921 of its 174,764 six-unit residue classes. Assigning each class to
the available non-`rho` map first, then to the smallest mapped-digit norm,
reduces `rho` assignments from 36,735 to 19,001 without changing any seed or
the native retained table. On a newly frozen 4,096-scalar panel, the native
evaluator used 20,579 gauge rotations, compared with 22,039 for the original
assignment: 1,460 fewer rotations (6.62%). Both used 49,152 mixed additions
and retained 54,339,936 bytes. All 4,096 points matched the direct-index and
fused evaluators; the first 128 also matched independent binary multiplication.

## Method and checks

The assignment order is `(is_rho, mapped_digit_norm, map_id, seed_id)`.
The 67,338 seed values and their order are fixed. The priority map changes
only the direct-class atlas, which remains 1,667,480 bytes. The complete
residue verifier checked all 1,048,576 pairs modulo 1024 and the assigned
seed, map, bound, and six-unit orbit. An independent 256-scalar design replay
checked the group values. The fresh native panel has input SHA-256
`89e557605be6b8aa329094cfbcab2128847a2232895674fecc6795fa6f1dd9b1`;
both native variants used those exact points and identical generated Rust
source. The priority atlas SHA-256 is
`73dd615b65686ca51c866e28968d0f1c79c7367982730c5c3d115f11b72337c7`.

| Format on the fresh panel | Retained bytes | Mixed additions | Gauge rotations |
| --- | ---: | ---: | ---: |
| Fused prior format | 66,470,376 | 49,152 | 16,477 |
| Exact three-image `tau` format | 64,991,220 | 49,152 | 17,505 |
| Fixed-seed norm-seven, original assignment | 54,339,936 | 49,152 | 22,039 |
| Fixed-seed norm-seven, priority assignment | 54,339,936 | 49,152 | 20,579 |

The exact three-image control uses 10,651,284 more retained bytes than the
priority format and 3,074 fewer gauge rotations on this panel. The two
norm-seven rows isolate assignment cost because the seeds, retained bytes,
scalar panel, and native evaluator source are the same. The three-image
control was checked against the priority points in the same native test.

The complete priority native suite passed 141/141 tests locally. Ten
edge-fixture outputs were independently verified. The local host is contended;
the table reports exact operation counts and retained bytes, not a CPU
speedup. The source-pinned Linux replay records independent correctness and
host evidence. A paired runtime result needs the host-level isolation and
calibration receipt specified in `docs/ISOLATED_BENCHMARKS.md`.
