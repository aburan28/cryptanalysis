# W16 prefix cache reproduces the validated XCNF byte for byte

Precomputing the W16 source-validity prefix removes **327,407 CNF clauses**
from each target-dependent formula build while preserving the previously
validated XCNF *byte for byte*. The complete cached control has the exact
SHA-256
`1ac5db0fe73adc5ccbd8aa626d7abc77ebe9f6c16ff406e984a7c0fc15e80f3b`,
98,640 variables, 528,425 CNF clauses, and 34,600 native-XOR rows. Its
target-dependent completion, write, and hash check took **12.864 seconds**
after the reusable cache and field source were loaded. The
[independent artifact audit](audit.json) recomputes the frozen source
hashes, decompresses the original full XCNF, verifies formula identity,
and accounts for the measured phases.

This is the exact N131 W16 signed-prefix five-pair residual on
`EC1N131Ckb1heb5f1998f20b`. The [audited W16 source](../n131_w16_w18_sixpair_width_gate_20261010/RESULT.md)
has **B=393,552** actual subgroup-usable points and **K=32,675** folded
columns. The fixed first-pair columns are `(7887,12331)` and the
constructed residual subgroup point is
`(195299749687542804345334901261125836908,
1128961186580568451488859020590389941242)`.

The [prefix builder](core.py) executes the original circuit through mask
and flag allocation, the one-hot target-fiber selector, and every W16
source-validity clause. It stops immediately before the first fixed-prefix
clause. The [target suffix](core.py) continues the original statement order:
fixed-column exclusions, distinctness, two same-seed constraints, five
pair products, three upper S3 joins, and the target S3 link. The source
cache therefore preserves variable numbering, clause order, native-XOR
order, and all gate reuse. Byte identity with the archived complete
assignment and group-lift control establishes that this split changes no
solver input for the frozen query.

| Phase | Wall time | Memory evidence |
| --- | ---: | ---: |
| Reusable source-prefix build | 15.276 s | 116,277,248 B peak |
| Source-prefix build and archive | 19.893 s | 1,304,897-byte compressed cache |
| Cache load and source setup | 3.969 s | outside the timed target formula interval |
| Target preimages | 0.281 s | charged |
| Target suffix | 12.430 s | charged |
| Formula write and hash | 0.153 s | charged |
| **Target formula total** | **12.864 s** | **227,065,856 B peak** |

The [protocol](protocol.json) froze the exact source, input, accepted Sage
runtime, one worker, 120-second source-precompute cap, 60-second
target-formula cap, and 4-GiB RSS cap. The [cache receipt](cache_result.json)
and [formula receipt](compare_result.json) retain source hashes, timings,
memory, status, and exact formula identity. CPU timing is exploratory on
the contended host; the archived monolithic W16 build's 30.451 seconds
included different setup work and does not provide a controlled speedup
ratio. `candidate_id` remains null because this is a decomposition-kernel
precompute, not a complete IC pipeline.

W16's source support bound requires at least 32 first-pair prefixes for
a 50% union-bound ceiling. This single-prefix formula build falls below
the optimistic 18.75-second average budget, but repeated cache copying
and all solver attempts must also be charged in a full 32-prefix query.
The next improvement is to cache target-independent gate families beyond
source validity without changing the validated formula, and then obtain
an independently replayed unpinned relation on an ordinary N131 point
inside the frozen 600-second, 4-GiB envelope.
