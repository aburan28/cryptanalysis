# F4 dominates certified native continuation; F4/F5 query panels are ready for CUDA replay

Early parity compression from round112 supplies the same owned proofs and
complete point-decomposition answers to the instrumented continuation. On five
frozen 12-variable queries, all ten optimized and undefined-behavior-sanitized
phase workers matched the independently audited uninstrumented result in
status, basis, work counters, assignment, curve replay, and serialized proof
SHA-256. The repeated optimized panel passed 30/30 workers, including five
warmups. Its source and native binary hashes, reference report, and native-free
audit are bound in the [lossless evidence archive](results.tar.gz) and
[archive receipt](archive.json).

## Native continuation phases

One warmup and five measured repeats ran per case with rotating case order.
Durations below are medians with median absolute deviations in milliseconds;
the F4 share is the median of each run's `f4_ns/total_ns`. The timer covers
seeded native continuation only. The complete query's coefficient borrowing,
matrix production, independent equation replay, and curve checks have their
own boundaries in the round112 validation. The local macOS 26.6 arm64 host was
contended, so these timings identify work concentration and are exploratory.
Every case uses `F_(2^31)` with irreducible modulus `2147483657`, binary curve
coefficient `b=1`, three summands, four factor-base coordinates per summand,
and the target abscissa shown below.

| Query | Target x | F4 ms | Proof composition ms | Total native ms | Median F4 share |
| --- | ---: | ---: | ---: | ---: | ---: |
| pdp-12-seed-1 | 1,909,423,073 | 104.189 ± 66.879 | 0.828 ± 0.056 | 105.640 | 98.14% |
| pdp-12-seed-2 | 867,195,139 | 45.941 ± 6.770 | 1.485 ± 0.531 | 47.500 | 96.72% |
| pdp-12-seed-3 | 2,257,189 | 64.878 ± 20.417 | 0.870 ± 0.020 | 66.329 | 97.81% |
| pdp-12-seed-4 | 332,124,186 | 76.757 ± 32.862 | 1.108 ± 0.331 | 84.160 | 96.98% |
| pdp-12-seed-5 | 287,642,293 | 85.475 ± 47.463 | 0.954 ± 0.097 | 87.337 | 97.64% |

Each worker's five exclusive nanosecond fields sum exactly to its native total.
The median columns need not sum because each phase can attain its median on a
different repetition. The next native optimization target is F4 construction
and elimination, followed by a fresh complete-query profile. Proof composition
has a smaller median cost on all five cases.

## Complete-query F4/F5 CPU and CUDA boundary

The same Rust binary times target conversion, Boolean-system construction,
matrix F4 or signature-filtered matrix F5, independent evaluation of returned
assignments against the original equations, and curve-point replay. CUDA
upload, launch, synchronization, and download occur inside that interval when
selected. Four exclusive query phases sum to `online_ns`; the independent
callback is reported as a subset of solve time. Curve and factor-base setup
precedes the target-dependent interval. These are point-decomposition stage
queries; the repository's verified one-target IC/rho comparison has a separate
measurement contract. Each query result retains the field modulus, curve and
subgroup orders, cofactor, actual factor-base point count, basis, target, and
solver limits. For this panel the base has 55 usable points over a six-coordinate
subspace on the 508-point curve, with subgroup order 127 and cofactor four.

The frozen `a=0`, `n=9`, two-summand, degree-five scan kept all 41 abscissae
from `0` through `40`: five queries returned verified decompositions and 36
completed with no decomposition. Abscissae `12`, `14`, and `22` are its first
three verified-positive controls. Three repeats of each completed and replayed
under both F4 and F5: 18/18 verified answers, with identical assignments in
all nine paired F4/F5 observations. The arm64 host build used the debug Rust
profile and has no CUDA device. The device-source emulator passed 14 focused
tests, including F5 row skipping, cap handling, host-equivalent decisions, and
echelon reduction. Physical CUDA query timing remains to be collected with
the paired `pod_query_ab.sh` run.

The algebra counters reveal an F5 work question independent of wall-clock
noise. These counts were identical across all three repetitions of each cell:

| Target x | F4 rows / word XORs | F5 rows pruned / remaining / word XORs |
| ---: | ---: | ---: |
| 12 | 14,929 / 5,672,772 | 2,470 / 12,491 / 7,529,396 |
| 14 | 11,566 / 3,787,678 | 1,833 / 9,753 / 4,128,813 |
| 22 | 12,288 / 4,195,443 | 1,869 / 10,424 / 5,214,109 |

F5 removes rows on each input but performs more counted word XORs. The next
F5 experiment should profile pivot density and ordering after signature
filtering, then test a deterministic criterion-versus-F4 choice on these same
complete queries. No wall-time speedup is promoted from this host.

## Isolated CPU replay and structural F6 boundary

`make_isolated_manifest.py` selected nine PDP cases where both round112 modes
had complete independently checked proofs and original-equation/curve replay.
It retains three other PDP cases with their exact validation statuses. The
`isolated_worker.py` command emits the complete target-dependent `Context.run`
time and `verified=1` only when the answer and proof bytes match the frozen
audit. The configured Linux SSH allocation identified itself as Docker with
cgroup v1, no isolated CPU partition, and no `nohz_full` set. The Mac host also
fails the Linux preflight. A controlled CPU speedup requires this manifest on
a physical Linux host satisfying [the isolation contract](../../../docs/ISOLATED_BENCHMARKS.md).

For F6, exact Boolean elimination reconstructed solutions on 245 random
systems checked by exhaustive enumeration and a 48-variable local quartic
chain. It now charges factor-table construction to the state cap before
allocation. The exact S3 auxiliary-coordinate study used `n=9`, `ell=3`,
modulus `515`, curve `b=1`, and seed `1`. As summands increased from three to
six, Boolean variables grew from 18 to 54; the measured greedy and explicit
left-to-right widths were 15 for three summands and 21 for four through six.
The latter meets the proved `2*n+ell` support-width bound. The 21-variable
middle link exceeds the current explicit-table cap of 12. A packed local
factor or proof-carrying F4/F5 projection is the next implementable boundary;
its certificate transport and ordinary-query yield need direct tests.

The archive includes the first interrupted/failed phase and emulator attempts,
all raw successful phase and query records, proof bytes, code and binary
receipts, the S3 support record, and the host preflight. The archive was
stream-verified byte for byte after content-addressed deduplication. Its SHA-256
is `5a85c7080479496e6ec4e517973247972dba6ed5a3d1a9ca8a4fc86cf0b3cc3b`.
