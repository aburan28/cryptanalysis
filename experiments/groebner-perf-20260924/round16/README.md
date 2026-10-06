# Independent Boolean truth evaluation on Metal

This opt-in verifier computes the input equations' complete zero set on an Apple
GPU, then runs the existing independent CPU basis checks. The polynomial solver
and its numerical tables are separate. The GPU never receives solver roots,
solver transforms or pivots. No default dispatch changes, and **a reliable
complete-query GPU speedup has not been established**.

The initial blocking-wait screen retained 320 verified complete queries, including
warmups, over ten frozen planted controls. All CPU and GPU certificate semantics,
basis hashes and replayed assignments agree. Complete-query wall ratios on the
six 18-variable controls were mixed, with every interval crossing one; smaller
controls generally lost to the CPU. A second implementation polls for completion
for up to a 5 ms clock deadline before falling back to a blocking wait. It passes
correctness tests, but its performance run was rejected before numerical work
because the shared host was heavily oversubscribed.

## Independent algorithm and correctness

Split a monomial mask into its high variables and six low variables. For each
equation j and high mask h, the CPU forms the 64-lane word

`C[j,h] = XOR low_truth(m & 63)` over terms m whose high mask is h.

For each high assignment a the GPU directly computes

`V[j,a] = XOR C[j,h]` over all h that are subsets of a.

The low lane is the assignment to the six low variables. A monomial evaluates
to one exactly when both its high and low masks are subsets of the assignment;
the formula therefore evaluates the supplied ANF by AND/XOR. The second kernel
intersects the complemented words across equations. For fewer than six variables,
unused lanes are masked off. `uint2` holds each exact 64-bit Boolean word; there
is no floating-point arithmetic. The host checks little-endian layout.

All target coefficients are independently decoded and duplicate terms cancelled
before this computation. The packed decoder comes from round15; the build script
pins the original core's hash and replaces only its input-zero evaluation region
and the already-qualified sortedness check. The remaining checks establish that
the proposed basis vanishes on every input root, has matching Boolean staircase
dimension, has minimal leading terms and standard tails. The Boolean field
relations are implicit in this finite Boolean ring. This is exact enumeration,
still exponential and limited to 20 variables; it does not supersede round11's
larger-ring algebraic derivation checker.

The gathered work is `E * 3^max(n-6,0)` 64-lane XORs for E equations and n Boolean
variables, plus zero-set intersection. Unlike the adaptive CPU checker, this
prototype evaluates every equation even if the first few remove all roots.
That is an explicit unfavorable case, not a shortcut in certification.

## Reuse, lifecycle and wait variants

A workspace fixes only n, E, shader pipelines, buffers and dispatch dimensions.
Coefficient storage is cleared and populated afresh per call. Both kernels
overwrite their full active output arrays before any output is consumed. A
buffer barrier separates dependent kernels; the host checks successful command
completion before reading shared output. The CPU root vector and basis checks
are fresh. Calls on a shared workspace are serialized, including destruction;
different workspaces remain independent. No target answer is cached.

| Arm | Input-zero computation | Completion policy |
| --- | --- | --- |
| `ordered` | Round15 independent CPU direct-ANF checker | Synchronous CPU call |
| `gpu` | Independent direct-ANF Metal gather and intersection | Blocking command completion |
| `gpu-spin` | Identical Metal kernels | Poll command status until a 5 ms clock deadline, then block if unfinished |

Polling's CPU cost is charged to the query. A descheduled thread may observe the
deadline later than 5 ms; it is not a hard wall-time guarantee. Poll counts,
observed polling time and fallback use are reported. Command errors reject the
certificate. There is no backend fallback or implicit runtime compilation of
the native libraries. Shader compilation and fixed workspace initialization are
explicit setup; command encoding, submission, waiting and output reads are online.

Native and Python entry points require 1..20 variables and 1..4096 equations.
Each of the two large GPU buffers is capped at 128 MiB (256 MiB together, plus
root/parameter storage). This cap can reject otherwise valid dimension pairs.
Input buffer extents and live raw handles remain the C caller's responsibility;
Python owns its buffers and protects lifetime. The ABI checks dimensions,
required pointers, masks, coefficient high bits, offsets and output structures.
The statistics ABI has an explicit size check. Invalid-input tests ensure no GPU
dispatch occurs and a subsequent valid call remains correct. No hard process
timeout is provided.

## Retained complete-query screen

The blocking screen used 15 paired repetitions plus one warmup for each of ten
frozen targets, shuffling CPU/GPU order. The Apple M4 Pro has 14 logical CPUs and
48 GiB RAM. One-minute load was 30.5–32.3, so the environment was already busy.
Values below are observed diagnostics, not qualified crossover claims. Ratios
are geometric means of paired wall times, not ratios of marginal medians.

| Control | CPU median ms | GPU median ms | CPU/GPU paired wall GM [bootstrap 95%] |
| --- | ---: | ---: | ---: |
| 18 variables, seed101 | 37.673 | 36.003 | 1.183 [0.986, 1.543] |
| 18 variables, seed102 | 73.572 | 63.095 | 1.057 [0.911, 1.228] |
| 18 variables, seed103 | 50.470 | 55.050 | 0.963 [0.820, 1.140] |
| 18 variables, seed104 | 30.245 | 30.260 | 1.128 [0.972, 1.319] |
| 18 variables, seed105 | 31.597 | 32.454 | 0.973 [0.813, 1.142] |
| 18 variables, seed106 | 29.848 | 32.023 | 1.004 [0.822, 1.274] |
| 9 variables, GF(2^31) | 7.367 | 10.554 | 0.638 [0.439, 0.927] |
| 12 variables, GF(2^31) | 5.443 | 11.196 | 0.529 [0.413, 0.685] |
| 6 variables, GF(2^11) | 0.907 | 4.513 | 0.288 [0.194, 0.448] |
| 6 variables, GF(2^83) | 36.628 | 38.717 | 0.918 [0.813, 1.037] |

On the 18-variable controls, marginal device-time medians were about 1.1–2.2 ms,
while the submission/wait interval medians were about 3.7–7.3 ms. These phases
motivated the polling experiment. GPU-query CPU time improved on these controls,
but CPU time excludes GPU execution and waiting and is not a speedup claim.
Marginal phase medians must not be added to form a total.

One query starts with the supplied target coordinate and includes fresh native
descent, packed basis computation, independent certification, original equation
checks, full curve replay and an extra untouched reference-ANF check. Exclusive
phase nanoseconds sum to the measured interval. Target-independent ring/layout
and workspace setup, plus fixture generation, are separate. The first 18-variable
GPU workspace setup was 237.3 ms versus 32.7 ms for the CPU workspace; initialization
is not free. Library-hash file reads remain charged per query in both arms.
Parent memory high water is recorded; per-query memory peak remains unknown.

These are planted component controls, not natural relation-yield estimates or
complete IC recovery. The unchanged curve oracle reconstructs its reference
point from fixture points during charged replay. Candidate and IC/rho online
times remain null. The producer remains exact evaluation plus Buchberger–Möller
interpolation, capped at 256 roots. Nothing here establishes faster F4/F5, a new
F6 algorithm, asymptotically faster Gröbner computation, or a global ranking.

## Timing admission and pending confirmation

New benchmark runs first record the one-minute host load and logical CPU count.
The default predeclared limit is one load unit per logical CPU. Excess load
rejects the run before fixtures, workspaces or timed attempts. Existing report
or admission filenames cannot be overwritten. After an admitted run, every group
start and final load must satisfy the threshold to remain timing-eligible. This
is necessary, not sufficient, evidence of an uncontended host; it does not detect
every competing GPU workload or establish exclusive CPU/GPU ownership.

The retained polling-run admission attempt measured load 242.590 against a limit
of 14. It records `admitted: false` and `timed_attempts: 0`; no timing report was
created. The earlier blocking screen predates this rule and remains an unqualified
diagnostic, not retroactively admitted evidence. No polling speedup or confirmation
has been measured. A dedicated or otherwise demonstrably quiet Apple GPU host is
needed for the next complete-query comparison.

## Validation and reproduction

The final local suite passes eight test groups in 21.038 seconds. It includes
168 random GPU/CPU/Python comparisons over both wait modes and optimized/UBSan
host builds, planted nonempty roots, equation counts through 4,096, 63/64/65 and
128-bit equation boundaries, the full 20-variable zero system, duplicate packed
masks, malformed ABI inputs without dispatch, all basis rejection categories,
fresh-state recovery, shared concurrency and closed lifetimes. Complete queries
retain original equations and curve replay over GF(2^11), GF(2^31) and GF(2^83).
Three admission tests verify zero numerical work on rejection, evidence retention,
and disqualification when recorded load exceeds the limit. UBSan covers host C++;
it does not instrument the Metal device shader.

From the repository root, on macOS with Python >=3.10 and Clang:

```sh
python3 experiments/groebner-perf-20260924/round4/build.py
python3 experiments/groebner-perf-20260924/round14/build.py
python3 experiments/groebner-perf-20260924/round15/build.py
python3 experiments/groebner-perf-20260924/round16/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round16 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round16/verify_evidence.py
python3 experiments/groebner-perf-20260924/round16/benchmark.py --repetitions 31 --output /tmp/gpu-certificate-new-run.json.gz
```

The query factory accepts `arm='ordered'`, `'gpu'` or `'gpu-spin'` and supports
the existing owned packed-ANF buffers. Close queries/plans or use context managers.
The CPU arm remains the baseline; selection is explicit.

The blocking report embeds its exact measured sources and binary/build receipt.
Later changes are kept in the live sources and a separate build receipt; historical
results are not rewritten as measurements of polling. Source/evidence inventories
are integrity records, not external attestations. Hosted CI compiles the Metal
host on macOS and checks admission/evidence on macOS and Linux. It does not claim
device execution, shader validation or performance measurements on hosted runners.
