# Wider Metal residual rows

This opt-in experiment extends round38's compact Metal elimination from 31
to 55 residual features. Quadratic Boolean residuals with 8, 9 or 10 variables
can now run on Metal when there are at most 32 equations. The previous path
uses CPU elimination for these shapes. The portable CPU algorithm and the
independent round34 certificate checker retain their existing contracts.

Each GPU row uses two explicit `uint32` words. SIMD exchange shuffles each
word independently. The host reads the output as `uint64` after checking its
little-endian layout. A branch has 34 output cells: rank/status, 32 residual
rows and an original-equation contradiction witness. The output buffer is
twice the previous size. Equation coefficients and contradiction witnesses
still use 32 bits. The host pivot array supports all 32 independent rows.

The kernel retains uniform SIMD collectives, fresh exact symmetry checking,
the immutable canonical-branch map and complete root/proof expansion.
Equation counts above 32 remain an explicit CPU shape fallback. Missing
Metal devices and shader failures are not silently reported as GPU execution.
The default backend is CPU, and this change does not add automatic routing.

## Build and validate

Use ordinary Python; these programs do not import Sage. From the repository
root, build the portable dependencies and producer:

```sh
for version in 20 23 31 32 33 34 35 36 37 38 41; do
  python3 "experiments/groebner-perf-20260924/round${version}/build.py"
done
python3 experiments/groebner-perf-20260924/round41/validate_native.py --output wide-cpu.json.gz
```

On macOS, add the optional host library and request physical Metal validation:

```sh
python3 experiments/groebner-perf-20260924/round41/build.py --metal
python3 experiments/groebner-perf-20260924/round41/validate_native.py --metal --output wide-metal.json.gz
python3 experiments/groebner-perf-20260924/round41/audit_queries.py --input wide-metal.json.gz --output wide-metal-audit.json
```

The validator covers 4,330 distinct synthetic systems per selected build:
all 4,096 two-variable, three-equation systems; random fresh coefficients
and duplicate cancellations; symmetric/asymmetric reuse; 31/32/33/65-equation
boundaries; all residual widths through 10; a rank-32 matrix with a high-word
pivot; and a contradiction witness using original-equation bit 31. Direct
truth, independent basis checks and original-polynomial certificate identities
establish correctness. Eighteen systems exceed the existing 256-root limit
and must return inconclusive, never a partial accepted answer.

Optimized and UBSan CPU builds run everywhere. A requested Metal build runs
the same controls if a device is present; an absent device is retained as
`UNAVAILABLE`. Other build, shader and allocation errors fail validation.
Four budget controls and eighteen frozen complete queries are also included.
The frozen inputs and original ANFs come from round40; fresh descent,
certificate checking and signed curve replay execute on every query.
CPU proof bytes must match round38 exactly. Metal proofs can differ and must
independently certify the same complete roots and reduced bases.

`audit_queries.py` separately checks every complete-query proof from the
original ANFs without loading native code. It verifies every rejection
identity, exhausts uncovered branches, and checks the reduced basis by its
complete root set and Boolean quotient dimension. CI runs this audit after
native validation on both host platforms.

The isolated prototype already passed 4,328 physical M4 Pro system controls,
72 complete queries and a separate original-ANF proof audit for all 18 inputs.
It actually used the GPU on 17 inputs, including all six 24/27-variable
controls; the 83-equation fixture remained CPU fallback. These are prototype
correctness results; the packaged build has its own validation receipt.

## Measurement and limits

The separate paired pilot includes every retained CPU and GPU comparison arm,
the widened CPU control, the widened Metal candidate and round40's CPU
projection prototype. Two small and two wide trials use seven measured pairs
per input and retain every admission and failure. The charged interval covers
fresh solving, transfer/synchronization, independent certificate checking,
original equations, signed curve replay and an untouched reference-ANF check.
Invariant setup and evidence serialization are separate. Timing qualification
requires every sampled one-minute load to stay below the logical CPU count.

The packaged M4 Pro build passed 12,990 native controls (4,330 systems on
optimized CPU, UBSan CPU and physical Metal), four budget controls and 72
complete queries. Every query proof payload, mathematical result and integer
work counter matches the isolated prototype. The two added high-word controls
also pass. The separate packaged original-ANF audit is recorded independently.

All 5,040 timed queries matched their audited references. Three trials passed
the load gate. The second wide trial reached a sampled one-minute load of
354.558 against a limit of 14 and is ineligible. The first qualified wide
trial has these complete-query median ranges over the three inputs per size:

| Boolean variables | Widened Metal | Fastest measured CPU | Qualification |
| --- | ---: | ---: | --- |
| 21 | 3.45–3.51 ms | 7.90–8.02 ms | Earlier GPU paths are faster; widening adds overhead |
| 24 | 21.15–29.48 ms | 45.31–46.16 ms | Positive paired intervals on this trial; qualified repeat missing |
| 27 | 660.74–671.70 ms | 739.72–749.31 ms | Positive paired intervals on this trial; qualified repeat missing |

Both small trials qualified, but no small input repeatedly beats every prior
comparison arm. No input passed the full repeated promotion gate. The result
files retain all per-input pairs, bootstrap intervals and rejected trials.
`m4-pro-timing-evidence.json` binds the raw archived reports, compressed
journals, proof payloads and driver sources. The analyzer's pre-admission
load-accounting error was corrected in a separately preserved version before
analysis; the measured sources and statistical plan did not change.

On the qualified 27-variable controls, affine-certificate construction still
takes 484–489 ms and independent verification 103–104 ms. GPU wall time is
about 16 ms, including a 6.7–6.9 ms device interval. These are nested diagnostic
medians, not additive phase totals. Further GPU kernel tuning alone cannot
deliver another 2x complete-query improvement here; certificate construction
and checked proof transport are the larger targets.

Correctness alone does not establish a latency improvement. This experiment is separate from round40's
quadratic-first affine projection; there is no combined GPU/projection arm.
It makes no claim for CUDA, OpenCL, HIP, other Apple devices, asymptotic
complexity, natural relation yield or a complete single-target IC/rho solve.
