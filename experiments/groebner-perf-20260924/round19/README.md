# Exact tiled Metal certification for one complete public-point query

Round19 connects a two-dispatch Metal truth evaluator to round18's packed public
query. CPU remains the default. This is an opt-in Boolean certificate backend,
not a new F4/F5 implementation or a novel F6 algorithm. It uses an established
subset transform. No admitted GPU speedup or full IC/rho result is claimed yet.

The independently decoded coefficients go directly into shared Metal buffers;
the CPU reads the completed root buffer in place. Each equation is transformed
in tiles of 4,096 64-bit words using 32 KiB of threadgroup memory. The second
kernel combines at most four high tiles (20 variables) and intersects equation
zeros. No coefficient or root memcpy lies between those stages. Each call zeros
its coefficient scratch and overwrites every transformed/root word. Only ring
layouts, buffers, pipelines and immutable low-variable truth masks are reused.
Fresh targets require fresh descent, coefficients, solving and certification.

The packed decoder, direct original-equation evaluator and exact basis proof are
pinned to merged CPU sources. The certificate checks the complete Boolean zero
set, basis vanishing, staircase dimension, minimal leaders and standard tails.
The producer is the existing evaluation/Buchberger–Möller path, independent of
the checker. Limits remain 1–20 Boolean variables, 1–128 equations and at most
256 producer roots. This does not remove exponential verification or solve the
high-degree-of-regularity problem. Odd-degree curve fields through 63 use the
independent native curve replay; wider supported fields retain Python replay.

`GPUQuery(..., arm='cpu')` uses round18's combined optimized CPU path. The opt-in
arms are `gpu-blocking` and `gpu-poll`. The latter polls for at most 5 ms before a
blocking fallback; polling cost is charged and reported. Device errors remain
explicit failures. There is no silent CPU substitution. Python locks protect
workspace calls, statistics and destruction. Raw ABI users must supply live
handles, sufficient buffer extents and synchronization, with immutable inputs
for each call, as in round18.

The local Apple M4 Pro passed the integrated optimized and UBSan host checks:
96 certificate comparisons against a separate direct evaluator, 8,352 direct
packed equation evaluations, and 20 complete CPU/GPU public-query comparisons.
The tests also cover duplicate parity, empty/many-root ideals, invalid ABI and
basis inputs, 63/64/65/128-equation boundaries, concurrent workspace reuse,
in-place fresh coefficients, changed targets, 20-variable queries, and the
83-degree Python curve fallback. Dictionary materialization is forbidden in the
packed query tests. UBSan checks host code; exhaustive comparisons check shaders.

The separate shader driver checks every intermediate truth and final root word
against CPU direct subset gathering. Two configurations (O3/256 threads and
UBSan/64 threads) cover 48 cases: **1,475,856 intermediate words and 164,384 root
words**. Output sentinels and changed inputs test complete writes. Final logs
are `tile-final-optimized256.log` and `tile-final-ubsan64.log`, bound by the
retained tile build receipt. Earlier logs preserve a sandbox with no device and
a shader compilation failure (`half` was a reserved type), followed by the fix;
those older logs are not evidence for the final binary.

## Measurement protocol

`benchmark.py` compares CPU, GPU blocking and GPU polling on each frozen public
point in randomized paired order. Fixed setup and fixture generation are
separate. The timed interval includes validation, fresh packed descent, basis
construction, independent certificate, direct equation checks, full-point curve
replay and an untouched Python reference-ANF check. A further Python curve audit
is outside that interval and recorded separately. GPU certificate statistics
split preparation, encoding, execution/wait, extraction and exact basis proof;
device timestamps are descriptive only. The headline comparison is the complete
verified query, not the shader time. Initial pipeline compilation is reusable
setup and remains recorded.

The predeclared 16 controls are six 18-variable GF(2^31) queries (m=3, ell=6,
seeds 101–106); 9- and 12-variable GF(2^31) queries (seed 101); six-variable
GF(2^11) and GF(2^83) controls (seed 101); and 20-variable m=2, ell=10 queries
in GF(2^31) and GF(2^63), seeds 201–203. The latter timing seeds differ from the
seed-200 correctness controls. These are planted component fixtures, not
natural relation-yield estimates, high-regularity systems, or recovered DLPs.
`candidate_id`, `IC_online_ms` and `rho_online_ms` remain null.

The local attempt was rejected at load 28.4033 on 14 logical CPUs, before any
timed work. The admission JSON is retained. CI may wait up to 240 seconds before
admission, sampling load every 30 seconds. It then runs 31 pairs plus one warmup
per control. No threshold is relaxed. Every group-start and final one-minute load
must remain at most the logical CPU count. This is necessary, not sufficient,
for a quiet host. Slow, unsuccessful and interrupted runs remain evidence;
incomplete/unsolved controls cannot support a win. Output files are never
silently overwritten. The workflow has a 25-minute cap, not a per-query watchdog.

`audit.py` checks source/build identities, generated decoder/proof/shader hashes,
frozen inputs, attempt coverage, phase accounting, binary identities, original
equations, full curve witnesses, CPU/GPU semantic parity, GPU dispatch/statistics
contracts and load qualification. Synthetic corruption tests exercise rejection
paths without being reported as measurements. Paired ratios use 2,000 bootstrap
resamples of log ratios. Their 95% intervals are exploratory per-control
intervals, without multiple-comparison correction. `candidate_gpu_win` requires
all attempts verified, load eligibility and a lower interval bound above one;
a separate confirmation is required before changing default dispatch.

Reproduce on macOS with real Metal access (Python 3.12 or 3.13):

```sh
python3 experiments/groebner-perf-20260924/round4/build.py
python3 experiments/groebner-perf-20260924/round14/build.py
python3 experiments/groebner-perf-20260924/round15/build.py
python3 experiments/groebner-perf-20260924/round17/build.py
python3 experiments/groebner-perf-20260924/round18/build.py
python3 experiments/groebner-perf-20260924/round19/build.py
python3 experiments/groebner-perf-20260924/round19/build_tiles.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round19 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round19/verify_evidence.py
python3 experiments/groebner-perf-20260924/round19/benchmark.py --repetitions 31 --admission-wait-seconds 240 --output /tmp/fresh-metal-query.json.gz
python3 experiments/groebner-perf-20260924/round19/audit.py /tmp/fresh-metal-query.json.gz
```

Linux CI checks the portable admission/audit contracts and retained evidence.
macOS CI builds and actually executes both shader-driver configurations and all
integrated tests. Missing Metal access is a failure, not a successful device
skip. A load-rejected benchmark can coexist with passing correctness CI, but
cannot supply a GPU speedup. The next gate is a replicated complete-query win on
an admitted GPU host, followed by ordinary public-target and full-IC validation.
