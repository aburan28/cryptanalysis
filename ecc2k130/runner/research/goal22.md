# 22 billion complete ECC2K-130 updates per second

Target: at least 22 billion completed scalar updates per second on one
RTX PRO 6000 Blackwell Server Edition, curve 131. Do not aggregate GPUs,
count checkpoint history, or replace complete updates with field operations.

Acceptance: five completed timing repetitions with a median >=22,000 M/s,
retained full output and source/binary/compiler identity, and at least 300
device reports successfully replayed by the independent host reference with
zero dropped reports. An accepted change must also pass applicable arithmetic
tests and report its DP collection rate. A changed walk requires separate
campaign identity and walk-quality validation before production deployment.

## Current status, 2026-09-21 07:57 UTC — target met

- **Accepted: 22.100934 billion completed scalar updates/s** on one
  RTX PRO 6000 Blackwell Server Edition. Five fresh 256-launch measurements:
  22.166455, 22.132776, 22.100934, 22.093414, 22.089525 B/s.
  Warmups excluded. Every sample completed 504,658,657,280 scalar updates.
- Same-run baseline median: **19.852741 B/s**, for **11.32% gain**.
  Do not substitute the higher three-sample screening rate for this result.
- DP34 collection: **21.548499 B/s**, 12,387 reports, zero drops;
  complete corpus equal to the population-matched baseline. The baseline's
  collection geometry is intentionally matched for correctness, not optimal
  throughput; its collection rate is not a fair speedup denominator.
- Independent GPU field/group/metadata checks, 300 report replays, full
  32,688-record replay equality and both checkpoint directions passed.
- Reviewable standalone source, exact patch/build command, source hashes,
  compiler/binary identity and full receipt are in `research/candidates/goal22`.
  Exported proof generator exactly reproduces the measured header; host
  independent field probes pass from the exported source and make dry run passes.
- Receipt: `20260921T075537Z.json`; Modal app
  `ap-8juePXJQ2FunQjZOYRg8I6` completed. No benchmark job remains running.
- Compute Sanitizer unavailable; inherited test-clmad suite is not all green.
  These limits are explicit in `research/candidates/goal22/acceptance.json`.
- Production workers and S3/RDS services unchanged. No ingester launched.
- Earlier sections are historical records; this accepted result governs.

## Recovered baseline, 2026-09-20

Source and existing records were recovered read-only from Modal container
ta-01M30QT3VGSHD865G279PXFPRR into `build/live-22b-baseline`.
`snapshot-manifest.json` hashes 409 recovered files. This is an isolated
snapshot, not an overwrite of production or the migrated local source.

The latest discovered record is ONE-BLOCK-GEOMETRY.md: 20.078 B/s median,
five samples, and 300 replayed reports. It supersedes the previously inspected
17.414 B/s record. Its target is `make gpu-rtx-pro6000-20b`. These are inherited
results, not new measurements in this goal. Reproduction is required.

The documented 20.078 B/s configuration uses batch 16, threads 512, minblocks 1,
native carryless multiplication, the table walk, tag denominators, pipelined
selection, inlined products, chain-first ordering, and reduced conversion.
The target is 9.57% above this recorded rate.

## First experiment

Rebuild the exact baseline with CUDA 13.3.1, sm_120, on an isolated Modal GPU.
Run report replay before timing. Exclude warmup, retain five timing samples,
then measure DP34 collection. Bound the GPU function to 15 minutes, one GPU,
no retries. Do not attach campaign secrets or checkpoint volumes. Production
workers must not be interrupted or share the benchmark GPU process.

Inspect inversion latency and table selection only after reproducing the
baseline. Existing negative results include extra occupancy, larger batches,
fused passes, and several CLMAD reorderings; do not assume they are new ideas.

Fresh reproduction: `build/goal22-results/20260921T032537Z.json`, Modal app
`ap-VG9cDsjfAHkAQ07s4K4pYH`. Five rates in M/s: 20093.586, 20095.859,
20095.171, 20094.698, 20094.491. Median 20.094698 B/s. Every timing run
completed 100,931,731,456 updates. Replay: 300 verified, zero dropped.
DP34 collection: 19.234569 B/s, 2,471 reports, zero dropped. Target unachieved.

Host table-walk nibble and byte probes both passed all 4,096 points. The
inherited `test-clmad` suite is NOT green: one guard test still expects sm_75
rejection although source now supplies a fallback, and two exact-source proof
tests reject the current native-square source shape. Full output is retained
in `build/goal22-host-tests.log`; do not count this suite as passing.

## Inversion scheduling experiment

Hypothesis: inlining the normal-basis multiplier and/or inversion Frobenius
network lets the compiler schedule across the eight dependent inversion
products, reducing latency. Three arms: multiplier only, Frobenius only,
both. Arithmetic and walk identity stay unchanged. These are hypotheses,
not established speedups. Register pressure and code size may make them worse.

Build each from the recovered source in a disposable container, preserving
the original baseline binary. Replay 300 reports per arm before timing.
Use three alternating timing rounds for screening, then five fresh samples
and DP collection for any potential >=22B result. Keep full build logs,
source diffs and binary hashes. Limit the sweep to one GPU and 15 minutes.

## Binary polynomial inversion experiment

Replace the eight-product Itoh-Tsujii inversion in the packed walk with binary
extended GCD directly in the same polynomial basis. This removes the inverse's
carryless multiplies and basis conversions, trading them for shifts, XORs,
degree comparisons, and divergent control. It may be slower on the GPU.
Try inline and out-of-line forms to observe register-pressure effects.

`binary_inverse.h` uses the exact degree-131 modulus from the source generator.
It preserves u=a*b and v=a*c modulo that polynomial; each pass decreases the
sum of polynomial degrees. Zero maps to zero as in the baseline.
`test_binary_inverse.cpp` passed 1,133 inversions against independent
`Ref<CfgF131>`: every basis input, zero, all-ones, and 1,000 dense random inputs.
This is host evidence only. GPU replay and full sorted DP-multiset equality
against the baseline are required before accepting timing samples. Bound the
GPU sweep to 15 minutes; require five fresh samples for a target claim.

Inlining completed: `build/goal22-results/20260921T033347Z.json`.
Medians (M/s): baseline 20091.945, inline_mul 19929.652,
inline_sigma 20108.605, inline_both 19984.442. All replay gates passed.
The best difference is +0.083%; no arm is promoted.

Binary-GCD sweep completed: `build/goal22-results/20260921T033951Z.json`.
Medians (M/s): baseline 20064.226, binary_inline 14092.336,
binary_noinline 13650.327. Every variant replayed 300 reports and produced
identical full multisets of 32,688 DP records (sorted SHA256
`db31c5c36206192fe8fda4cba58152e46620d2ffe5e4d22605e7f7d34909162e`).
Neither candidate is promoted. Target remains unachieved.

## Follow-up inversion screening

`binary_inverse_window.h` batches up to eight divisions by x per pass. It
uses F^-1 mod x^8 = 0x9d and the sparse factorization of F to correct the
coefficient with shifts/XORs, without an extra lookup table or CLMAD.
`divsteps_inverse.h` uses 262 fixed passes, scalar delta, predicated swaps,
and no polynomial degree scans. Screen inline and out-of-line divsteps.
Both passed the same 1,133-case independent CPU reference comparison. A
separate Python polynomial-product/long-division check passed 1,131 nonzero
fixed-step inversions. These are not yet GPU performance results.

Completed improved inverse sweep: `build/goal22-results/20260921T034645Z.json`.
Medians (M/s): baseline 20094.169, window_inline 16628.820,
divsteps_inline 16816.704, divsteps_noinline 16312.834. All 300-report gates
passed and all full 32,688-record DP multisets matched the baseline. No promotion.
Next action: poll this exact launcher and inspect its saved JSON receipt;
do not restart it merely because output is quiet. Any >=22B screening row
still requires five fresh timing samples, zero-drop replay, DP collection,
and source integration before completion can be claimed.

The optional sanitizer test of the original binary inverse was terminated after
more than 16 minutes of active CPU execution (session 61013, PID 28519).
It produced no completion result and is NOT counted as passing. The ordinary host reference
test passed for all three inverse implementations. Production files and
campaign workers remain unchanged.

## Cross-warp inversion product tree

Hypothesis: amortize one existing Itoh-Tsujii inverse over W warps (same lane
index per tree), without changing per-thread batch 16 or the state footprint.
The multiplication count becomes 5 + 5/(16*W), versus 5 + 5/16. This counts
arithmetic, not GPU throughput; barriers and saved tree nodes can erase gains.

`collective_inverse.cuh` uses a 10,240-byte shared scratch and per-thread saved
right subtrees. Test W=2/4/8/16. Substitute one for zero leaves, then return
zero for those leaves, preserving inv(0)=0 without poisoning other lanes.
Partial thread blocks use the original inverse and never enter collective
barriers. Opt into >48 KB total shared memory; total table plus scratch and
reserved memory remains below 64 KiB for this 512-thread preset.

`test_collective_inverse.cu` must pass on the GPU before timings: 1,024
inverses per W checked against independent Ref<CfgF131>, including basis,
dense, zero-lane and all-zero-block cases; two consecutive inversions check
scratch reuse. Full walk replay and DP multisets are then checked as before.

Block-barrier collective sweep completed in
`build/goal22-results/20260921T035503Z.json`. Median M/s: baseline 20025.964,
W2 18700.235, W4 18086.536, W8 18842.640, W16 18065.825. All independent
device inverse probes, 300-report checks, and DP multiset comparisons passed.
All variants were slower; none promoted.

## Independent group barriers

`group_inverse.cuh` changes the collective tree's barriers from whole-block
synchronization to non-aligned `barrier.sync` with one barrier ID per warp
group and an explicit participating thread count. Barrier zero stays reserved
for ordinary block synchronization. The independent device probe runs different
even numbers of consecutive inversions per group to exercise separate progress.
PTX semantics checked against NVIDIA's ISA reference:
https://docs.nvidia.com/cuda/archive/11.4.0/parallel-thread-execution/index.html

Completed receipt `build/goal22-results/20260921T040130Z.json`:
median M/s baseline 20053.720, W2 19726.184, W4 19440.439, W8 19991.624.
All probes and report/multiset gates passed. Group barriers recovered most of
the block-barrier loss, but still did not beat the control. No promotion.

## Mixed integer/CLMAD products

`mixed_product.h` moves one of three 64-bit Karatsuba leaves to the existing
integer-arithmetic carryless multiplier, keeping the other two on native
CLMAD. This preserves the raw 131-bit polynomial product. Its host probe
passed 18,162 products against independent bit convolution (every basis pair,
1,000 dense pairs, zero). Run the same probe on the device before timing.

Screen three placements: single products, single plus inverse products, and
one product of each pair (including the pipelined forward pass). Hypothesis:
use integer execution capacity to reduce demand on the carryless unit. This
may instead add too much integer work or register pressure. No gain assumed.

Completed receipt `build/goal22-results/20260921T040735Z.json`: median M/s
baseline 20097.889, mixed_single 18776.292, mixed_single_inverse 18154.683,
mixed_pairs 17762.351. All independent probes, replay and full DP multiset
gates passed. No promotion.

The driver now validates the final completed scalar count against geometry,
steps, and launch count, and rejects samples with dropped reports. Its
`--certify NAME` path is prepared for five longer 256-launch samples plus
DP34 collection and corpus comparison if screening finds a >=22B candidate.
This confirmation path has not yet run. The 22B objective is still unmet.

## Grouped software inverses

`hybrid_group_inverse.cuh` runs windowed binary GCD or fixed divsteps only
in each product-tree root warp. All eight independent device probe modes
passed, including zero inputs and independently progressing groups.
Receipt `build/goal22-results/20260921T041353Z.json`: median M/s baseline
20079.378, warps4_window 15728.758, warps8_window 16752.340,
warps8_divsteps 17979.025. All replay and corpus gates passed. No promotion.

## More resident warps with reduced register liveness

The 20B kernel currently uses 116 registers with 16 resident warps per SM.
Screen 640-thread blocks (20 warps), with and without forward selection
pipelining / paired product ILP, and 768-thread blocks with both disabled.
The earlier wide-block trial predates the fully inlined 20B kernel. These
are new combinations; expect compiler spills or cache footprint to matter.
All use batch 16 and the same deterministic replay corpus. No gain assumed.

Completed receipt `build/goal22-results/20260921T042222Z.json`: median M/s
baseline 20065.925, threads640 19897.649, threads640_no_pipeline 20213.903,
threads640_low_live 20249.192, threads768_low_live 19037.186. The widest
kernel compiles to 80 registers with zero local bytes but is slower. 640
without forward pipelining uses 92 registers and is only +0.9% over control.
All replay and full DP-corpus comparisons passed. No arm promoted; no >=22B row.

## Polynomial Frobenius maps

`gen_frobenius_inverse.py` generates exact polynomial maps for square powers
2, 4, 8, 16, 32 and 65 by bit-polynomial long division. The inverse uses the
same beta_2,4,8,16,32,64,65,130 chain, with all intermediates reduced in the
polynomial basis. Nibble or byte lookup tables live in cached device global
memory, split into aligned four-word low parts and one-byte top parts.
This saves basis conversions at the expense of cached lookup traffic.

Both nibble and byte host probes passed 1,133 inverses and 6,798 Frobenius comparisons
against independent Ref<CfgF131>, including every basis vector, zero,
all-ones and 1,000 dense random values. Both device probes then passed.
Receipt `build/goal22-results/20260921T042622Z.json`: baseline 20064.771,
nibble 19764.515, byte 18796.051 M/s, all replay/corpus gates passed.
Nibble kernel uses 128 registers and 32 local bytes; byte uses 128/0.
Neither promoted. Cached lookup traffic did not pay in these implementations.

## Compact live metadata

`compact_metadata.cuh` stores dead flags as bits, using atomic OR/AND when
neighboring lanes write the same word, and the three used history tags in
three coalesced 16-bit planes. The fourth tag is never used by the cycle rule;
reads/exports canonicalize it to 0xffff. The on-disk v3 payload sizes and
coordinate/seed encodings stay unchanged through explicit transfer hooks in
`metadata_checkpoint.inc`. Original checkpoints remain loadable in both
directions, subject to testing. No production source changed.

Host primitive probe passed: 1025 lanes, two flag patterns, 200 history
updates per lane. The GPU probe also needs to exercise neighboring atomic
writers. Before accepting timings the driver requires 300 replayed reports,
full baseline corpus equality, and baseline-to-compact / compact-to-baseline
checkpoint continuation equal to a six-launch uninterrupted baseline.

Receipt `build/goal22-results/20260921T043318Z.json`: median M/s baseline
20098.108, metadata512 19983.775, metadata640 20474.136, metadata768 19469.510.
All independent device probes, 300-report replays, full DP corpus comparisons
and both directions of checkpoint continuation passed for every candidate.
The best is +1.9%, below 22B. No promotion or long certification yet.

## Exact pivot search and specialized Frobenius networks

`gen_pivot_search.py` replaces the pivot's max-over-byte lookups with a cyclic
predecessor search in L order. Dense point coordinates usually find a set
bit quickly; a four-candidate variant reads packed coordinate indices from
a small cached table. Both searches remain bounded and select exactly the
same pivot. Host probes passed all 131 basis vectors at all 131 phases plus
1000 dense inputs (18,161 cases), against the independent bit-plane pivot.

`gen_fixed_sigma.py` specializes the five fixed inversion Frobenius powers
(4,8,16,32,65) to literal swap masks, instead of reading mask arrays using
an exponent index. It checks all 256 basis vectors for each generated network.
Screen both inline and out-of-line helpers; a device probe compares 1133
inverses and 6798 maps to the independent scalar field reference.

Receipt `build/goal22-results/20260921T044303Z.json`: baseline 19948.651,
pivot_scan 18807.034, pivot_group4 18439.734, fixed_sigma 20029.096,
fixed_sigma_inline 20038.445 M/s. All primitive probes and replay/corpus gates
passed. Pivot search was slower; fixed masks only +0.4% against the same
control, with slightly variable clocks. No >=22B candidate and no promotion.

## Larger batches with compact metadata

The next metadata revision uses independent byte flags by default, avoiding
shared-word updates. The optional bit-flag path now uses a device-scope
relaxed atomic load as well as atomic OR/AND. NVIDIA PTX atomic-load mapping:
https://docs.nvidia.com/cuda/ptx-writers-guide-to-interoperability/atomic-abi.html
The earlier metadata receipt captured the previous bit-flag source and is
not evidence for this new revision. Updated byte-flag host probe passed.

Screen B24/T512, B28/T416, B32/T384 with the fully inlined arithmetic and
compact metadata, to amortize inversion without the older batch-32 state
footprint. Match 107,520 initial walks across different batch sizes for
replay, so the full DP multiset remains a valid check. Check self-resume at
each batch; cross-batch checkpoint restore is intentionally incompatible.
Timing still uses automatic full-device worker counts and verifies completed
updates. Certification collection, if needed, will match candidate worker
counts in the baseline for corpus equality while timing the candidate at its
normal geometry. No dedicated service or campaign workers launched.

Completed `build/goal22-results/20260921T045042Z.json`: median M/s baseline
20056.467, B24/T512 19243.824, B28/T416 17452.057, B32/T384 18550.355.
All probes, 300-report replays, the 53,364-record matched DP corpus and
self-resume gates passed. No speedup. Actual queried device limits: L2
134217728 bytes, persist cap 83886080, shared memory per SM 102400 bytes,
65536 registers and 1536 hardware threads per SM.

## Cooperative field-tail packing

`patch_bitplanes.py` changes the 256-point compact field tile from 4352 to
4224 bytes, retaining 128-byte alignment. Each warp's three high bits are
stored as three 32-bit planes, with padding to a 16-byte record. Full-warp
stores use ballots and a leader store followed by warp synchronization;
partial reseed stores use masked CAS. This experiment requires logical worker
counts divisible by 32 and tag-rebuilt denominators (all field tops <=7).
The checkpoint encoder/decoder uses the existing field conversion hooks.

Host and GPU probes passed full and partial-warp updates, padded tiles and
host/device encoding agreement. Receipt `build/goal22-results/20260921T045931Z.json`
contains the full arithmetic/corpus and resume gates. Both larger-batch arms
were slower than their controls; no promotion.

## Two independent chains per thread

The next hypothesis keeps the arithmetic count per point at the baseline:
one inverse per 16 points. Each thread instead handles two independent
16-point chains in 32 slots; 256 threads per block preserve the baseline's
total walks. Raw products and the two Itoh-Tsujii chains are interleaved to
expose independent work during inversion. Also screen 320 threads per block.
Reserve 60 KiB dynamic shared memory to guarantee one block per SM, within
the baseline's 64 KiB allocation including the driver reservation.

`paired_inverse.h`, `dual_walk.cuh` and `patch_dual.py` implement the candidate.
The host probe passed 2,266 paired inverses against Ref<CfgF131>, including
zero and every basis input. GPU primitive, full walk and resume gates precede
timings. Uses the revised byte-flag metadata, not the previous bit-flag path.

Receipt `build/goal22-results/20260921T050834Z.json` retained the full source,
primitive device comparison and walk/resume gates, all passing. Both dual
kernels were much slower (about 13.35 and 14.00 B/s) despite no local spills;
neither is promoted. More independent work per thread did not make up for
the lower warp count and changed schedule in this implementation.

## Refine the small occupancy gain

Screen 640, 704 and 736 threads with batch 16, selection pipelining disabled,
pair ILP disabled, and the revised independent byte flags plus three-tag
history. This stays near the only repeated positive result so far rather
than combining unproven arithmetic changes. All comparisons again require
300 reference replays, full corpus equality and cross-build checkpoints.

Completed `--widths` sweep, launcher session 75935, log
`build/goal22-widths-sweep.log`, receipt `build/goal22-results/20260921T051637Z.json`.
The 640-thread byte metadata median was 20.231331 B/s (+1.26% vs its control);
wider arms were slower. All replay, corpus and checkpoint gates passed.
The 22B objective remains unmet.
`summarize_22b.py` generates `build/goal22-results/index.csv`, preserving the
receipt link and screening/certification distinction for each measured arm.
No production code, campaign settings or live worker deployments changed.


## Transposed shared lookup tables

`patch_table_layout.py` keeps the walk, table size and following offsets
unchanged, but transposes addend words and/or sign-transform rows. The old
sign rows use stride 4 and the addend words have even bank indices at each
scalar load. Column storage distributes these accesses across all 32 banks.
Screen rows only, addends only, and both at baseline geometry. This is a
scheduling hypothesis; compiler vectorization may offset the expected benefit.
Host and GPU table-selection probes compare 4,096 points against the
independent reference, followed by full-walk replay/corpus checks.

Certification collection now matches initial walk counts for all experiments,
including changed thread widths, not only changed batches. This prevents an
invalid DP corpus comparison between different automatic worker populations.

Active table-layout Modal sweep: log `build/goal22-table-layout-sweep.log`;
launcher session 70830. All three host probes passed 4,096 points with zero
mismatches (session 53163 completed). The first GPU probe has also passed.
GPU probes run before any timing is accepted. All variants use the same amount of shared memory.


## Prepared: multiple blocks with a smaller shared selection table

The source already supports keeping only the 14 KiB selection table in
shared memory while loading addends through global/L1. Test this jointly with
compact byte metadata and 320x2, 384x2, or 256x3 resident thread geometry.
The hypothesis is that more warps can hide inversion latency without the
97 KiB shared-memory allocation that made earlier two-block layouts slow.
A fourth 320x2 arm also moves ONB squaring to ALU instructions. These are
prepared modes, not measurements or promotions. The ordinary 20B control,
300-report replay, exact DP corpus, and cross-build checkpoint gates remain.

All three transposed layouts passed the 4,096-point independent device probe.
The running session 70830 is now compiling the last full client and proceeding
to replay/corpus and timing gates. No timing result yet.


## Prepared: fused passes at intermediate and larger batches

`--fused-batches` screens B20/T576, B24/T512 and B32/T384 with independent
byte flags and three-tag history. The existing fused pass computes next
step selection before storing the current step's coordinates; it reduces
x/y loads but retains the exact walk and completed-update count. The prior
larger-batch sweep used separate forward/reverse passes, while historical
fused measurements predated this source's inlining and compact metadata.
Use identical 107,520 initial walks across batches for replay and full
DP corpus comparison; test self-resume because cross-batch checkpoints are
incompatible. Pending measurement; no predicted speedup is accepted as evidence.

Table-layout sweep completed: `build/goal22-results/20260921T053250Z.json`,
Modal app `ap-5pAS9ainLIlLi2ws7eN486`. All device probes, 300-report replays
and complete DP corpora passed. Medians (M/s): baseline 20073.565, table_rows 20125.476, table_addends 20013.328, table_both 20042.686.
No significant speedup and no promotion. Launcher session 70830 is complete.

Active hybrid-geometry sweep: launcher session **66446**, log
`build/goal22-hybrid-geometry-sweep.log`. Poll this exact session; do not
start a duplicate. The prepared fused-batches sweep has not been launched.


## Prepared: explicit non-aliasing walk buffers

`patch_noalias.py` exposes each disjoint packed walk buffer as a restricted
kernel argument and redirects every access in the walk and its selection
helpers to those arguments. The old pointer members remain in the by-value
scalar parameter structure for ABI simplicity but are never accessed by the
changed walk. Field-blob x/y/prefix regions do not overlap; metadata and
report allocations are separate. Initialization/reseed and on-disk formats
are unchanged. The source's fused-loop comment identifies unknown aliasing
as an obstacle to issuing later loads early; this tests removing that
obstacle directly. More cached values may increase register pressure, so
there is no presumed benefit. Test compact metadata at 512 and 640 threads, plus a 640-thread arm with
ONB squaring on the ALU to reduce native carryless-unit demand.

NVIDIA's restriction contract and register-pressure caveat:
https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/cpp-language-extensions.html
The patch applies after compact metadata and redirects both ordinary and
fused source branches, as well as the packed-engine launch arguments.
Pending GPU compilation/replay/resume/timing; not production code.

Hybrid geometry completed in `build/goal22-results/20260921T054147Z.json`,
app `ap-iTptaB3CNkaFGldIK6l70W`. All replay, corpus and checkpoint gates
passed. Median M/s: baseline 19735.224, hybrid320x2 17575.866, hybrid384x2 17906.143, hybrid256x3 15644.895, hybrid320x2_alu 17406.979.
Clocks varied during the run (some samples at 2250 MHz, with high GPU
temperatures), so small relative differences would not be decisive. Every
candidate is nevertheless well below the target. No promotion. Session 66446
is finished.

Active restricted-buffer sweep: launcher session **43708**, log
`build/goal22-noalias-sweep.log`; poll this exact session. The fused-batches
mode is still prepared but has not run.

Restricted-buffer sweep completed: `build/goal22-results/20260921T054918Z.json`,
app `ap-Y1MQF3HZGsbrEk2zmh0Z0A`. Median M/s: baseline 20094.959, noalias512 20035.272, noalias640 20563.501, noalias640_alu 20420.814.
All 300-report replay, full DP corpus and bidirectional checkpoint gates
passed. The 20.716537 B/s warmup is excluded from accepted medians. Clocks
varied; target remains unmet and nothing is promoted. Session 43708 finished.


## Zip-based normal-basis squaring

`zip_square.h` interleaves two 32-bit streams using three masked swaps and
two byte permutations. The existing normal-basis square interleaves the
input with its reversed field coordinate; using a joint zip avoids the four
native carryless spreads (or four separate longer ALU spreads). Field and
walk identity are unchanged. `patch_zip_square.py` replaces only `sqr131`.

A bit-index proof checked every one of the 64 basis inputs to zip2 against
its required even/odd destination. The actual C++ host implementation then
passed 1,133 inverses and 6,798 Frobenius maps against Ref<CfgF131> (session
74950 completed). GPU probe and full replay/resume gates remain mandatory.
Screen the restricted-buffer kernel at 512 and 640 threads, with a fresh
restricted-buffer 640 control as well as the original baseline.
The fused-batches experiment is deferred while this arithmetic-preserving
squaring implementation is tested.

Active zip-square sweep: launcher session **83432**, log
`build/goal22-zip-square-sweep.log`. Poll this session. The new best completed
screening median is restricted-buffer 640 at 20.563501 B/s (+2.33% vs its
20.094959 control), not the excluded 20.716537 warmup.

Zip-square completed: `build/goal22-results/20260921T055622Z.json`, app
`ap-24FJIFkZXJn5IQo1AlbS27`. All field probes, 300-report gates, full
DP corpora and checkpoint continuation passed. Median M/s: baseline 20038.146, noalias640_control 20484.363, zip512 20140.277, zip640 20630.218.
Target remains unmet; source has not been promoted. Session 83432 finished.


## Rotated logical warp identities for grouped inversion

`rotated_group_inverse.cuh` preserves each barrier group and lane but rotates
logical warp identities by the physical group index. Previous tree roots
were always the last warp of each group, such as 3,7,11,15 for four-warp groups.
New four-warp roots are 3,6,9,12 (plus 19 at 640 threads). This distributes
root work among different relative warp positions; whether it improves
hardware scheduling is a hypothesis to measure, not a claimed mapping of
CUDA warp IDs to physical schedulers.

The point inputs map bijectively within their original groups and lanes;
the field product/inverse is unchanged, including zero handling. Static
checks passed all indices for 512 threads with W=2/4/8/16 and 640 with W=4.
The existing device inverse probe, full walk corpus, and bidirectional
checkpoint checks must pass before timings. Test compact metadata plus
restricted buffers at W4/T512, W4/T640, and W8/T512. Header lists are now
deduplicated before recording patches when experiments compose.

Active rotated-group sweep: launcher session **44305**, log
`build/goal22-rotated-groups-sweep.log`. Poll this exact session. It tests
W4/T512, W4/T640, and W8/T512 with the first rotation revision.


The next rotation revision changes **only W=2** to rotate every pair of
physical groups. At 640 threads its roots become 1,3,4,6,9,11,12,14,17,19,
covering all four relative warp positions. W4/W8/W16 mappings stay identical.
All host index/bijection checks passed again. A `warps2_rotate640` arm is now
available for a subsequent run; the already-running session 44305 has the
previous frozen three-arm image and will not test it. Device checks and
measurements for the W2 revision are pending.

Rotated-group sweep completed: `build/goal22-results/20260921T060412Z.json`,
app `ap-AT0OeLMO13ucsSEKEtdfXI`. Median M/s: baseline 20087.43, warps4_rotate512 20824.101, warps4_rotate640 21756.348, warps8_rotate512 20230.624.
All primitive inverses (including zero and consecutive calls), full replay
and checkpoint gates passed. This is a substantial improvement but still
below 22B. Session 44305 is complete.


## Combined rotated-group tuning

`--finish-tuning` screens W4/T640 with zip squaring, transposed sign rows,
and both. It composes only transforms that already passed their independent
probes. Zip variants run the field-map probe and the collective inverse
probe against the combined source before full-walk replay/resume/timing.
The W2 rotation revision is present in the helper's source but the timed
kernel uses W4, whose mapping is unchanged from the prior sweep.


## Prepared: fewer barriers and private right-branch inverses

`lean_group_inverse.cuh` keeps each downward right-child inverse in its
thread's registers, storing only the left child's inverse. The root's final
upward product, inversion and first downward split happen in the same warp,
so the barriers between them and the intermediate shared stores are removed.
Each leaf reads only its own output slot; a later call first writes only the
caller's own slot and then synchronizes before cross-warp accesses. Therefore
the final reuse barrier can also be removed. For W4 this is four group
barriers rather than seven. This reasoning still needs device validation.

`--lean-groups` screens W4/T640, W4/T640 with zip squaring, and W2/T640. It
requires the independent inverse probe with zeros/consecutive calls, full
walk replay/corpus, and both checkpoint directions. If Compute Sanitizer is
available it also runs memcheck, racecheck and synccheck on the primitive
before building timed clients, each capped at 90 seconds. Nonzero sanitizer
exit prevents accepting timings. Subprocess timeouts now retain partial
output and return code 124 instead of losing the entire receipt.

Sanitizer flags and scope: https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html

Combined tuning completed: `build/goal22-results/20260921T061245Z.json`.
Medians M/s: baseline 20086.995, warps4_zip640 21647.961, warps4_rows640 21713.466, warps4_zip_rows640 21790.405.
All arithmetic, replay, full DP corpus and checkpoint gates passed. No
candidate reached 22B and none is promoted. Session 60520 completed.


## Lean result and further bounded screens

Lean retry `20260921T062828Z.json`, app `ap-SS3J2z15kwvdPOQlQl4wh5`,
completed. Median M/s: baseline 19939.808, W4 lean 21413.114, W4 lean+zip
21483.831, W2 lean 21211.578. All full walk, report and checkpoint gates
passed. Instrumentation unavailable: Compute Sanitizer 2026.2.1 reports
Device not supported on an unrelated 32-element CUDA write kernel too.
No sanitizer pass is claimed. Functional screening continued with that
limitation retained in the receipt.

The initial rotated+B17/B18 launch stopped at an overly restrictive harness
assertion (`noalias` disallowed all batch changes), before any timings.
The assertion now permits the composed rotated-group experiment.
The replay population is rounded to 32*LCM(all batch sizes): B16/B17/B18
uses 156672 initial scalar walks, with full equal report corpora and
self-checkpoint continuation. It never compares truncated unequal populations.
Flag forwarding for report-gate, rotated+batching, and lean modes was checked
locally against the execute signature before the new launch.


Rotated B17/B18 sweep `20260921T063550Z.json`, app
`ap-EAxo8g3u06Vu1sZh0b66sH`, completed with all gates passing.
Median M/s: baseline 19869.616, B17 21186.074, B18 21099.239.
Both were slower than the B16 leader. Session 64225 completed.

## Conditional report metadata and history load experiment

`--report-gate` places the existing dead-flag read behind the already-known
`hw <= dpWeight || guard` condition in all three report paths. Nothing can
be emitted or marked overdue outside that condition, so observable behavior
is unchanged. It applies in production collection as well as benchmark mode.
Compare plain, zip+row-layout, normal-L2-cache, and 64-bit-history arms, all
with rotated W4/T640/B16. The extra history width trades 2 bytes/point for
fewer load/store instructions; whether that helps is strictly empirical.

Both history widths passed 1025-lane host tests with 200 history updates per
lane and fruitless-cycle comparisons, and then passed the same device probes.
Full report corpus equality and both checkpoint directions remain required.
A separate deliberate-overdue test uses 1280 threads, DP0, max-iters4096,
4096 steps and three launches. It checks every lane was reseeded and compares
the complete serialized checkpoint, canonicalizing only unused history bits
48..63. Checkpoint curve, version, geometry, length and final iteration count
are validated before comparing state hashes.


Prepared (not run yet): `--rotated-groups --batching --geometry` screens
B12/T768, B14/T768, B12/T896. Unlike the earlier wider B16 tests, these keep
the estimated hot footprint at 95.836/111.809/111.809 MiB while increasing
active warps. Total shared bytes including the driver reservation are
65116/65116/67676, respectively. More occupancy may hide latency; higher
inversion cost per update and register pressure may offset it. No speedup
is assumed. All use the existing equal-population LCM rule and full replay
and self-checkpoint gates. This mode is independent of report-gating.


Report-gating completed: `20260921T064451Z.json`, app
`ap-yPdBnWhe6tvSpwlPdsNPd2`. Median M/s: baseline 20047.042, gated640
21729.638, gated+zip+rows 21783.596, normal-cache 20358.710, full-history
21667.174. Every variant passed the complete report corpus, both checkpoint
directions and the canonical overdue/reseed checkpoint comparison (all
20480 lanes reseeded). The 22.036733 B/s warmup is excluded. Session 85694
completed. No target claim and no source promotion.


Wider smaller-batch sweep completed: `20260921T065132Z.json`, app
`ap-UJD2exX0EyYJMoYfv7TD65`. Median M/s: baseline 20078.464, B12/T768
21660.910, B14/T768 21383.321, B12/T896 21386.559. Full-client reference
replay, equal report corpora and self-resume checks passed. Session 19686 done.

## Correction: primitive probe include selection

At 06:54 UTC the new phase experiment printed only one tested phase, revealing
that test_collective_inverse.cu used a quoted include. Because the test source
lives in /opt beside the original collective_inverse.cuh, that header won over
-Iinclude. Thus earlier primitive tests for grouped, rotated, lean and hybrid
collective implementations tested the original helper instead. Their full
GPU-client tests included the intended helper from include/packedkernels.cuh
and remain valid evidence; do not claim those old primitive records validated
the selected synchronization implementation.

Stopped only the isolated phase app ap-hsGfk5BygCf9Wdd2U8mg6K (session75526)
before accepting results. The test now uses <collective_inverse.cuh>. Phase
builds define GOAL22_EXPECT_PHASE, which refuses a non-phase helper. A fresh
run also revalidates the prior rotated_group_inverse.cuh and
lean_group_inverse.cuh using the corrected probe. Both passed all W=2/4/8/16
independent inverses, zero inputs and consecutive calls. Their exact intended
header hashes are retained in the forthcoming receipt.

## Rotation over successive inversion calls

phase_group_inverse.cuh adds a uniform per-call phase to the existing
within-group permutation. Every supported phase preserves a bijection, lanes
and barrier-group identity. The final group barrier is retained because the
next phase may assign another physical warp to an old scratch slot. Screen
rotation each step, that rotation with zip/row layout, and rotation every 16
steps. Host mapping checks passed; the corrected device probe exercises every
phase separately and changes phase across consecutive calls. Full-client
replays use 64 steps per launch (six launches) to cover all four phases even
in the every-16-step variant. Resume splits remain three+three launches.


Phase rotation completed: `20260921T070332Z.json`, app
`ap-QCV9690IPWnP5nqLLZpL2v`. Median M/s: baseline 20030.067, per-step 21622.075,
per-step+zip+rows 21710.261, every 16 steps 21616.916. Corrected primitive probes
passed every phase and consecutive calls. Both prior rotated and lean helpers
also passed corrected independent probes, retained with header hashes.
Full 114232-record corpora and both checkpoint directions passed for all arms.
Session 15969 completed, no target achieved.

## Instruction overlap and compact shared scratch

`--rotated-groups --geometry` (without batching) revisits pair ILP and forward
selection pipelining at W4/T640: each alone and both. These were previously
disabled to limit live registers, but grouped inversion may change that
tradeoff. No improvement is assumed.

Prepared `compact_group_inverse.cuh` retains the original rotated product
tree and all seven W4 group barriers. It uses aligned uint4 low limbs and
one byte per reduced field top (domain 0..7), reducing scratch from 20 to 17
bytes/thread and allowing vector low-limb shared accesses. Every logical
slot remains owned by the same thread at each barrier stage. B12/T896 now
fits below 64 KiB total shared allocation instead of crossing that boundary.
B10/T1024 also tests equal root-work distribution over eight groups, with
stricter register limits. The corrected independent inverse probe must pass
before any full-client measurement. Same-batch variants now require both
checkpoint directions even inside a mixed-batch sweep; unequal batches use
self-resume and the same initial scalar population as the baseline.


Instruction-overlap completed: `20260921T071300Z.json`, app
`ap-FFWwlN1ndCvf9UVwOjTpTX`. Median M/s: baseline 20066.041, pair ILP
21480.235, forward pipeline 21514.564, both 21305.699. Corrected primitive
probe and all full-client report/corpus/resume checks passed. No improvement.
Session 15773 completed.

Additional prepared arms force-inline the complete grouped-inversion helper
at 640 or 512 threads; arithmetic and barrier protocol are unchanged. The
selected helper is now written afresh for every collective arm, and its exact
text remains in each receipt's extra_header. Those new arms are not part of
the already-completed instruction-overlap receipt and have not run.

## Per-update polynomial squaring and packed reduction

`poly_square.h` replaces the generic 64-bit spreading stages with two byte
permutations and three 32-bit stages. Three GPU arms use zero, one or two native
CLMAD spreads to test arithmetic-pipe balance. Host reference probes passed all
three; active log `build/goal22-poly-square.log`, launcher session 92532.

A further exact algebraic simplification is prepared in `gen_square_reduce.py`
and generated `square_reduce.h`. A square H has zero odd coefficients, so
H>>131 is spread(B)<<1 with B=a>>66. The quotient's compressed even/odd streams
are E=B^(B>>4)^(B>>12)^(B>>28)^(B>>60) and O=B^(E>>1)^(E>>2).
The remainder circuit stays in these 65/66-bit streams until the final zip.
The Python derivation matches independent polynomial long division for all
131 basis vectors, zero, all ones, and 10000 random inputs. The generated C++
passed 1133 square comparisons, 1133 inverse comparisons and 6798 Frobenius
comparisons against Ref<CfgF131>, both alone and with normal-basis zip squaring.
These are host results; GPU correctness and throughput remain to be measured.

Prepared launch: `modal run ecc2k130/research/modal_22b.py --poly-square --geometry`.
It selects plain compact reduction and compact reduction plus the existing
normal-basis zip/transposed-row combination. Do not run alongside the active
isolated GPU experiment. Production source and deployment stay unchanged.

Polynomial-square first sweep completed: `20260921T074246Z.json`. Three-sample
medians in M/s: baseline 19790.916; ALU 21840.693; native1 21628.523;
native2 21514.353. All field probes, full 32688-record corpora, 300-report
replay and both checkpoint directions passed. The 22350.921 M/s ALU warmup
is excluded. GPU clocks/temperature varied across the run; no certification.
Packed-reduction follow-up launched alone, session60012 as recorded above.

Packed-reduction screening completed `20260921T074733Z.json`: baseline
20.070700 B/s, plain packed reduction 22.610829 B/s (22.559671–22.637268),
packed reduction plus normal-basis zip/transposed rows 22.633932 B/s
(22.553410–22.637450). Both are three-sample screens and passed all required
field/walk/resume gates. Select the simpler plain version for the fresh
five-long-sample run because the extra combination's difference is ~0.1%.
No threshold decision may use these screening samples or their warmups.
