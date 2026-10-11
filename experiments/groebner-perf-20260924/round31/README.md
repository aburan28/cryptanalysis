# Conditional quadratic lifting for one public-point query

This experiment adds a bounded, opt-in quadratic solver and a Metal backend for
its independent branch systems. The current CPU evaluation/interpolation solver
remains the default. All three arms use the existing independent sparse basis
certificate, original-equation checks, and signed public-point replay.

The input is one public point. No target solution, numerical pivot, or coefficient
table is reused between queries. Only ring layouts, GPU pipelines and allocations
are reusable. These are planted point-decomposition correctness controls, not
natural relation-yield estimates or full discrete-log recovery measurements.
`candidate_id`, `IC_online_ms` and `rho_online_ms` stay null.

## Algorithm and exactness

Split the Boolean variables into `x` fixed variables and `y` residual variables.
Every nonzero residual term must have degree at most two. The complete query
adapter currently requires three coordinate blocks and fixes the first two.

1. Consume the native packed ANF views directly. Clear and rebuild every numerical
   coefficient from this target. A subset transform evaluates the residual
   coefficients for all `2^x` fixed assignments.
2. Lift the residual variables to their singleton and pair features, giving
   `q = y + y(y-1)/2` unknowns. Solve each resulting affine linear system exactly.
   The CPU implementation eliminates coefficient columns. The Metal implementation
   uses one 32-lane SIMD group per branch and eliminates equation rows.
3. Reject inconsistent branches. If the affine nullity is less than `y`, enumerate
   its complete affine space and enforce **every** pair-feature product identity.
   A solution of the linear relaxation alone is not a root of the original system.
4. For larger nullity, enumerate all original `y`-variable assignments instead.
   Gray-code quadratic derivatives update the residual values. This fallback is
   charged to the same target; nothing is truncated.
5. Sort the exact roots and use the existing Buchberger–Möller interpolation.
   The unchanged independent native checker finds the roots separately and
   certifies the reduced Boolean Gröbner basis and ideal equality. The query then
   checks the untouched equations and a signed curve witness.

Both the original-variable fallback and the lifted enumeration are complete.
The 256-root and 4,194,304-enumeration limits return **inconclusive**, never a partial
basis. The known 18-variable seed-105 control requires four fallback branches and
256 original-variable checks. The tests retain this case and an inconsistent
quadratic system whose linear relaxation has spurious solutions.

The producer accepts `x <= 20`, `y <= 10`, `x+y <= 30`, up to 128 equations, and a
specialization table of at most 64 MiB. The independent certificate and complete
query adapter still support at most **20 variables**. This experiment does not
extend general verification beyond that limit. Input buffers must remain alive
and immutable during a call; workspace locks serialize solving and destruction.

## Metal scope and accounting

The explicit `backend='metal'` variant currently supports at most 32 equations and
31 lifted features. It checks the actual pipeline for SIMD width 32 and support
for 128 threads per threadgroup. A requested supported shape fails explicitly if
Metal is unavailable. Larger equation/feature shapes run the portable CPU path
with `gpu_shape_fallback=1`, a device label explaining the fallback, and zero GPU
time. This is a shape fallback, not evidence of GPU execution.

The pipeline allocates shared input/output buffers before the target arrives.
Each query copies freshly specialized coefficients, dispatches one kernel,
waits for completion, reconstructs each consistent branch's affine space, and
checks the original quadratic constraints on the CPU. Every output slot is
overwritten. Copy, dispatch, synchronization and CPU readback all remain inside
the complete query interval. `gpu_wall` includes the copy and wait;
`gpu_device` is a diagnostic from Metal timestamps and is not the performance
headline. `workspace_bytes` covers the specialization table and Metal buffers,
not all process memory. Process high-water memory is recorded separately.

The use of SIMD-group indices and capability checks follows Apple's
[thread and threadgroup documentation](https://developer.apple.com/documentation/metal/creating-threads-and-threadgroups)
and [threadExecutionWidth contract](https://developer.apple.com/documentation/metal/mtlcomputepipelinestate/threadexecutionwidth).
Only Apple Metal has been exercised here; CUDA, HIP and OpenCL are unimplemented.

## Reproduce

Ordinary Python drives the native experiment; no Sage installation is used.

```sh
python3 -m pip install numpy==2.4.0
python3 experiments/groebner-perf-20260924/round20/build.py
python3 experiments/groebner-perf-20260924/round23/build.py
python3 experiments/groebner-perf-20260924/round31/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round31 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round31/measure.py --repetitions 31 --output /tmp/quadratic-cpu.json.gz
python3 experiments/groebner-perf-20260924/round31/audit.py /tmp/quadratic-cpu.json.gz
```

On a macOS host with an available Metal device:

```sh
python3 experiments/groebner-perf-20260924/round31/build.py --metal
QUADRATIC_TEST_METAL=1 python3 -m unittest discover -s experiments/groebner-perf-20260924/round31 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round31/measure.py --metal --repetitions 31 --output /tmp/quadratic-metal.json.gz
python3 experiments/groebner-perf-20260924/round31/audit.py /tmp/quadratic-metal.json.gz
```

Outputs cannot overwrite an existing result or admission record. Every attempted
query remains in a hash-chained checkpoint journal. Admission uses a predeclared
one-minute-load ceiling of one per logical CPU at start, every paired group's
start/end, and finish. macOS requests USER_INITIATED QoS equally for all arms.
This admission check is necessary, not proof of an otherwise idle host.
`--correctness-only` disables all performance eligibility, including in CI.

The audited online interval includes target validation, fresh descent, solving,
independent certification, native original-equation checks, full curve replay,
and a final evaluation of the untouched Python reference ANF. Fixture generation
and reusable workspace setup are reported separately. An additional independent
Python curve-witness audit is retained outside the timed interval. Failed or
inconclusive attempts disqualify that control's speedup claim.

`audit.py` requires an identical trusted source checkout; it never executes
archived source. It checks source/build/generated-shader identities, binary
receipts, the journal, frozen public inputs, phase sums, actual GPU/fallback use,
and signed curve witnesses. It independently enumerates Boolean truth **bitmaps**
in Python, reconstructs branch ranks by direct residual evaluation and a distinct
row elimination, and validates the complete root sets and reduced bases.
Bootstrap intervals use paired log ratios; the GPU gate compares against the
faster CPU time **in each pair**, not just the slower CPU lifting prototype.

## Research interpretation and next experiments

This is specialized quadratic lifting, related to hybrid specialization and
linearization approaches such as Joux and Vitse's
[Crossbred algorithm](https://eprint.iacr.org/2017/372.pdf). It is not a new F4/F5
implementation or an asymptotic “F6” result.

There is a concrete scaling obstruction: a system with `m` equations and `q`
lifted features has nullity at least `q-m`. When `m=O(y)` and `q=Theta(y^2)`, small
lifted nullity cannot persist asymptotically. The exact fallback preserves
correctness but can still require exponential work. A future algorithmic claim
needs additional structure and a proof that it persists on the intended family.

The immediate next targets are:

- Reduce the coefficient specialization and shared-buffer copy costs while
  retaining the portable CPU path and a complete single-query comparison.
- Produce rank/inconsistency/nullspace certificates for independently checked
  branches. Measure whether their verification beats the existing exhaustive
  checker before attempting larger certified systems.
- Broaden the frozen workload to unplanted public queries, failures and higher
  residual dimensions, preserving the crossover and explicit negative cases.
- Only after those component gates, compare a fully wired IC candidate on one
  previously unseen target through independently verified scalar recovery,
  against rho on the same point and resources, with setup separate.

`hybrid_diagnostic.py` is a separate optional diagnostic requiring the round10
CPU/M4RI build. It compares complete queries using the bounded signature-seed
hybrid and the current independent verifier. Subtracting its measured RREF time
is explicitly a zero-elimination **counterfactual**, not a GPU speed measurement.
It is not part of the quadratic solver's acceptance evidence.

## Retained physical results

Both final runs used the physical Apple M4 Pro CPU and Apple M4 Pro Metal GPU,
31 measured paired repetitions plus one warmup per control and arm. Across the
two runs, **1,728 complete queries passed** with zero failures or missing attempts.
All six 18-variable controls beat the faster CPU arm in both runs. The following
values are from the second, separate confirmation; times are complete-query
medians, and speedups are paired geometric means against the faster CPU sample.

| Control | CPU evaluation (ms) | CPU quadratic (ms) | Metal quadratic (ms) | Best CPU / Metal, paired 95% interval |
| --- | ---: | ---: | ---: | --- |
| n31-m3-ell6-seed101 | 2.1105 | 4.5538 | 1.7132 | 1.213 [1.178, 1.239] |
| n31-m3-ell6-seed102 | 2.1117 | 4.2720 | 1.7270 | 1.225 [1.210, 1.239] |
| n31-m3-ell6-seed103 | 2.1689 | 4.6444 | 1.7591 | 1.233 [1.219, 1.248] |
| n31-m3-ell6-seed104 | 2.0913 | 4.4039 | 1.6918 | 1.232 [1.217, 1.246] |
| n31-m3-ell6-seed105 | 2.1278 | 4.3794 | 1.7184 | 1.237 [1.224, 1.249] |
| n31-m3-ell6-seed106 | 2.1365 | 4.4182 | 1.7460 | 1.199 [1.154, 1.229] |
| n31-m3-ell5-seed101 | 0.5482 | 0.6702 | 0.5440 | 1.006 [0.983, 1.030] |
| n11-m3-ell3-seed101 | 0.1813 | 0.0941 | 0.2228 | 0.417 [0.395, 0.438] |
| n83-m3-ell2-seed101 | 15.0962 | 14.9807 | 15.0219 | 0.997 [0.991, 1.003] |

The first run's six 18-variable paired speedups were 1.205–1.243×; the
confirmation's were 1.199–1.237×. These are improvements over the existing CPU
evaluation solver, not merely over the slower CPU quadratic implementation.
The 15-variable control has no established win. The 9-variable control strongly
favors the CPU quadratic solver. The 83-equation control is a recorded CPU
shape fallback and makes no GPU claim. No automatic dispatch rule is enabled.

In the first final run's seed-101 18-variable query, median specialization was
0.217 ms, Metal copy/dispatch/wait was 0.225 ms (device execution about 0.050 ms),
and independent certification was 0.724 ms. These diagnostic medians need not
sum to the median complete-query time. Certification is the next major cost.

The [first report](results/paired-final.json.gz) and
[confirmation report](results/confirmation-final.json.gz) retain source snapshots,
build/binary identities, CPU/device details, setup, every attempt, phase timing
and proof data. Their adjacent journals and
[audits](results/confirmation-final.audit.json) support reconstruction.
The CI workflow rebuilds on Linux and macOS and audits these same retained
reports. Hosted Metal results are correctness evidence only; they do not extend
the physical M4 Pro speed claim to virtual GPUs or other hardware.
