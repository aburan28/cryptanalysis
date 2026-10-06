# Producer coefficient transform experiment

The round51 producer evaluates its branch-major coefficient table with an
ascending Boolean subset transform before uploading the result for Metal
projection. This experiment tests that transform separately. It does not
change the solver, the independent round66 checker, dispatch defaults, or
the mathematical algorithm's asymptotic complexity.

For each feature, the desired output at assignment `a` is the XOR of input
coefficients indexed by every subset of `a`. Stage `b` XORs the coefficient
at `a ^ b` into `a` exactly when `a & b` is nonzero. These bit operators commute;
their product is the subset transform and, in characteristic two, an
involution. The tiled kernel performs the first four stages inside each
16-row block. Padding lanes load zero and participate in all barriers; only
valid rows and features store. Remaining ascending stages run in separate
encoders on a normal queue with an explicitly tracked shared buffer.

Two kernels are tested: one dispatch per bit, and a 16-row by 16-feature
threadgroup tile followed by the remaining bit dispatches. A function constant
specializes the invariant feature stride during context construction, using
[Metal's specialized function API](https://developer.apple.com/documentation/metal/mtllibrary/makefunction%28name%3Aconstantvalues%3A%29?language=objc).
All equation coefficients are fresh device input on every call. Context
setup requires actual device capacity for 256 threads per threadgroup and
the requested buffer; missing Metal remains an explicit result.

Limits are 1–20 fixed variables, 2–56 uint32 features including the constant,
and 64 MiB per table. Every successful call copies in the entire table,
waits for completion, and copies out the entire table. The owner serializes
calls and destruction. Failed requests reset success counters and cannot
reuse an earlier result. Planned logical XORs, encoded/submitted/completed
dispatches, and padded dispatched thread counts are distinct fields.

Build and validate using ordinary Python, without Sage:

```sh
python3 experiments/groebner-perf-20260924/round67/build.py --metal
python3 experiments/groebner-perf-20260924/round67/run.py --output /absolute/new/evidence-directory
python3 experiments/groebner-perf-20260924/round67/audit.py --evidence /absolute/new/evidence-directory --output /absolute/audit.json
```

Omit `--metal` for portable CPU and explicit unavailable-backend controls.
Use `--physical-hardware` only on a known physical, untranslated host. Hosted
CI does not set it. `--allow-unavailable` permits recording an unavailable
requested device while completing the portable controls; it never substitutes
CPU timings for a GPU result. Other probe failures stop the run.
The run requires committed sources and retains source/native hashes, generated
shader bytes, raw failures, setup logs, host information, correctness controls,
frozen original-ANF inputs, balanced arm order, warmups, and every timing row.
The 18-, 24-, and 27-variable inputs are stage diagnostics from round40,
not complete IC candidates or independently recovered discrete logarithms.

The timed interval covers only the transform: it includes GPU uploads,
encoding, waits, and downloads. Original-ANF loading and scattering, allocation,
pipeline setup, and exact output comparisons are outside this interval. Check
times are retained separately. All permutations of the three arms repeat
three times, retaining 18 observations per arm and case plus a warmup.
Ordinary-host CPU and GPU comparisons remain exploratory, with no isolation
receipt, `timing_eligible: false`, and aggregate speedup unknown.

An integration would reuse the producer's existing input buffer for subsequent
projection after copying the transformed coefficients back for its unchanged
symmetry guard and CPU proof paths. That requires explicit current-invocation
ownership, failure invalidation, full query checks, independent original-ANF
replay, and measurements that charge all copies, synchronization and verification.
Standalone kernel time cannot establish that integration's benefit.

The completed physical Apple M4 Pro experiment and its integration decision
are recorded in [RESULTS.md](RESULTS.md), with frozen evidence under `results/`.
