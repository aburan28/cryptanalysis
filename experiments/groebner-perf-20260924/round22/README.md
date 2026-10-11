# Direct coefficient-word Metal verification

This opt-in experiment replaces the round19 CPU coefficient expansion with
sparse scattering into dense 32-bit coefficient lanes. Each bit in a lane is
one original Boolean equation. The GPU performs a low-coordinate transform in
16 KiB of threadgroup memory, then a high-coordinate transform in at most
32 KiB, and packs zero assignments into the unchanged exact proof's root buffer.
There are three dispatches above 12 variables and two at smaller shapes. The
high-coordinate transform avoids a `3^k` subset gather across k high bits.

The packed ABI, input and basis validation, direct original-equation evaluator
and complete basis proof are generated from the same pinned independent CPU
reference. No producer roots, pivots or numerical buffers enter this verifier.
The coefficient scatter handles duplicate masks by XOR and checks unused bits.
It clears numerical state on every call, while retaining allocations and fixed
layouts. The variable range remains 1–20 and the equation range 1–128.

The new representation trades less CPU preparation for more GPU work and, for
some shapes, more memory. Counts labelled `zeta_words` in this backend count
**32-bit coefficient-lane XORs**, with `word_bits: 32`; the old backend counts
64-bit assignment words. They are not interchangeable operation counts. Full
shared-buffer bytes and preparation/encode/execute/extract/proof costs remain
recorded. No new asymptotic algorithm or high-regularity result is implied.

## Correctness and comparison

The native driver exercises the actual decoder and kernels against direct
original-term scans, with no CPU zeta implementation in its oracle. Each of the
optimized/256-thread and UBSan/64-thread configurations checks 40 cases,
26,315,144 partial truth words, 26,315,144 complete truth words and 148,248 root
words on an Apple M4 Pro. Cases include zero/unit ideals, random/dense and planted
inputs, duplicate masks, padding, 32/64-bit equation boundaries, the 12/13-variable
kernel boundary, and 18/20-variable transforms. Workspaces are reused between
numerically different inputs.

Six integration test groups include 96 exact certificate comparisons, 8,352
direct equation checks, 20 CPU/new-GPU complete-query comparisons and eight
four-arm comparison queries. Optimized and UBSan host builds exercise malformed
buffers, corrupted bases, no-dispatch validation failures, concurrent calls,
closed lifetimes, 128 equations and the wide-field curve fallback.

The four benchmark arms are the improved round18 `cpu`, the unchanged round19
blocking `tiled`, new blocking `coeff`, and new bounded-poll `coeff-poll`.
All use fresh descent and solving, independent complete basis certification,
original-equation checking and independent signed curve replay. The frozen
16 planted component controls and complete-query boundary match round19;
conversion, launches, waiting/spinning and extraction are charged. Setup is
separate. No target answer is cached, and CPU remains the production default.
These are PDP components, not recovered IC discrete logarithms or natural-yield
measurements; IC candidate identity and online IC/rho times remain null.

The benchmark retains a warmup and randomized paired repetitions. Admission
requires initial, every group-start/end and final one-minute load at most the
declared logical CPU count. This is necessary, not proof of an exclusive host.
`--correctness-only` is permanently ineligible for performance claims, even on
an idle host. Failed, interrupted and rejected attempts remain evidence and
cannot count as wins. The local performance attempt rejected load 18.7905 on
14 logical CPUs before timed work. No GPU speedup is assumed.

## Recoverable evidence

The journal preserves round21's append-only hash chain, per-arm checkpoints,
flush/sync behavior, ambiguous-write closure and truncated-prefix recovery. Its
schema records final component memory/qualification fields. All fixture and
setup metadata is complete before the first checkpoint and is written once. The aggregate is serialized only on completion or
a caught interruption; it must equal journal recovery before mathematical audit.
For a fixed control set, receipt writing scales linearly with repetitions.
The synthetic byte-count test concerns bookkeeping only.

Seven portable admission/audit groups and six journal groups verify gating,
corrupted identities/phases/source receipts, explicit failures, truncation,
checksums, metadata retention and sync errors. The initial journal schema-adaptation
failure is retained beside the corrected passing run. The first full journal
repeated fixture metadata and expanded to 145 MiB; that correctness-only trace
and its exact source are retained in the task archive named in
`results/initial-journal-layout.json`. The final layout writes fixtures once. Hash inventories and
`verify_evidence.py` require all retained artifacts to be tracked by Git.

## Reproduce

Build round4, round14, round15, round17, round18 and round19 as in the preceding
experiment (round20/build.py builds the CPU dependencies), then on macOS:

```sh
python experiments/groebner-perf-20260924/round22/build.py
experiments/groebner-perf-20260924/round22/build/test-coefficients 256
experiments/groebner-perf-20260924/round22/build/test-coefficients-ubsan 64
python -m unittest discover -s experiments/groebner-perf-20260924/round22 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round22/benchmark.py --repetitions 31 --output /tmp/coefficient-comparison.json.gz
python experiments/groebner-perf-20260924/round22/audit.py /tmp/coefficient-comparison.json.gz
```

Metal execution requires access to a real device. Portable admission, audit and
journal tests run on Linux as well. The CI workflow records device correctness
on macOS and attempts the 31-pair comparison after bounded admission. A candidate
GPU win requires complete verification of every paired attempt and a paired
wall-ratio interval wholly above one against the improved CPU. A reproducible
crossover and full IC integration remain separate acceptance gates.
