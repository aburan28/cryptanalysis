# A packed 64-seed N131 mixed-S3 inverse stream

The target-split half-trace inverse now scans **64 unpinned W14 source
seeds from a packed disk index**. For the frozen constructed N131
four-atom output, the scan recovered the exact masks `(18,19,24,25)`
and products `(1112,1376)` at seed 1 after reading and checking
**264,202 left output entries**. The trace-zero control had zero hits.
The target-dependent scan intervals, including index reads and decoding,
were **1.158 s** and **1.071 s** with one worker. An independent parser
checked every packed entry and sampled 384 pair equations; separate
bit-field group arithmetic replayed the positive raw and cofactor-four
sums.

This is a proposed-output decomposition component on
`EC1N131Ckb1heb5f1998f20b`, with `candidate_id: null` and
`run_id: null`. The field is
`GF(2)[t]/(t^131+t^13+t²+t+1)`, the source is the audited W14
rational-mask support, and the two pair rotations are 26 and 39. The
query inputs are the previously frozen constructed reciprocal sum
coordinate and its trace-zero control. A public-point relation method
must still generate useful proposed coordinates from the other free
blocks and the supplied public point.

## Exact streamed representation

The [producer and query kernel](stream.cpp) enumerate usable unordered
source-mask pairs by their 14-bit XOR seed. For each pair, the producer
solves the two rotated pair-output quadratics, retaining both reciprocal
coordinates and the packed 28-bit mask-pair descriptor. Left records
contain 17 bytes for the coordinate, 17 bytes for its reusable
half-trace and trace bit, and 4 bytes for the descriptor. Right records
contain 17 bytes for the coordinate and 4 bytes for the descriptor.
Each seed has a six-byte header; the complete 64-seed
[index](index.bin) is **15,588,314 bytes**.

For a supplied coordinate `z`, the query reads each seed's two sorted
tables, uses one target half-trace and one batch inversion per seed,
looks up the two exact S3 roots in the right table, and checks four
distinct folded columns. Its clock begins when `z` enters the kernel,
after loading target-independent support and constructing the field,
and includes the entire index scan, decode, batch inversion, lookup,
and witness checks. Process launch and support loading have separate
startup accounting. The [preparation protocol](prepare_protocol.json)
fixes the source and one-worker/120-second/4-GiB setup gate. The
[version-two query protocol](query_protocol_v2.json) binds the exact
index digest, source, two proposed outputs, one worker, and
30-second/4-GiB per-query limits.

| Frozen stage | Status | Work | Wall interval | Peak process RSS |
| --- | --- | ---: | ---: | ---: |
| Index preparation | `COMPLETE_PACKED_SEED_PREPARE` | 132,101 mask pairs; 264,202 outputs per rotation | 49.593 s parent | 4,685,824 B |
| Constructed output | `COMPLETE_PACKED_SEED_QUERY` | 64 seeds; 264,202 left entries; one exact product hit | **1.158 s query** | 5,521,408 B |
| Trace-zero control | `COMPLETE_PACKED_SEED_QUERY` | 64 seeds; 264,202 left entries; zero hits | **1.071 s query** | 5,292,032 B |

The [independent audit](terminal_audit.json) parsed every 38-byte left
and 21-byte right record, recomputed the support pair count for every
seed, checked two outputs per usable pair in each table, sampled
384 pair-output field equations, and independently replayed the
constructed four-point group sum and subgroup projection. It matched
the original fixed-seed native product witness exactly.

## Preserved reader failure

The first frozen query stopped before seed scanning because the
producer wrote an eight-byte marker containing the seven-character
text `S3STRM1` plus a zero byte, while the reader compared all eight
bytes with the seven-character literal. Its
[failure receipt](query_failure_v1.json) records
`PRODUCER_FAILURE_BAD_INDEX_MAGIC`; the query wall for that attempt is
unknown. The index was retained byte-for-byte. The corrected reader
checks the seven marker characters and the zero terminator; its
[source](stream.cpp), binary, and version-two query protocol were
frozen against the existing index before the completed scans. The
original [source](stream_v1.cpp), binary, protocol, and raw stderr
remain in the directory.

## Full-seed resource projection

The independently audited W14 census contains **33,780,028** usable
unordered pairs across all 16,383 nonzero seeds. At two outputs per
pair, the current packed format requires at most **3,986,141,614
bytes**, including seed headers, for a complete two-rotation index.
Scaling the measured constructed 64-seed query by exact output count
gives **296.2 s** for a complete scan; scaling the observed setup gives
roughly **3.5 hours** of reusable preparation. Both are extrapolations:
the measured index is 15.6 MB and likely benefited from cache, while
the proposed complete index is about 4.0 GB. The
[storage receipt](storage_receipt.json) observed 288,268,288 available
bytes on the repository volume, so a full run needs
separate preallocated storage and a frozen source receipt. These rows
do not establish an all-seed 600-second result or a complete target
online time.

The [exact uniform-residual bound](uniform_residual_bound.json) supplies
a separate target-conditioning criterion. Each free source pair has at
most 135,120,112 signed states, so the projected free-four-atom image
has at most `135120112² = 18,257,444,666,892,544` subgroup points.
For an independently uniform residual in the order-`r` subgroup, its
membership probability is therefore at most **2.683×10⁻²³**. This is
a group-wide occupancy bound, not a distribution claim for the fixed
public point or for residuals generated by the other two blocks. It
shows why the next method needs a joint target constraint that selects
residuals correlated with the free-four-atom support; making a uniform
proposal check fast would still leave too many proposals.

The next algorithmic gate is public-target output generation. It must
constrain the two same-seed four-atom blocks jointly with the other
free blocks, reject seed/output families before leaf expansion, and
recover an unpinned N41 public-point relation with independent replay.
Only a source-bound full-index/I/O gate and that N41 relation should
trigger the frozen N131 public-point query.
