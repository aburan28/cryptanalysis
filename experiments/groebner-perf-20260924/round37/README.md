# Fixed-width affine elimination with exact certificates

This candidate specializes the initial round36 producer's coefficient-row
loops for one, two and three uint64 words. The residual dimension is validated
as 1..10, so the cubic Boolean monomial count is at most 176 and no other width
is possible. Dispatch happens once for each fresh residual system. A compile-
time assertion bounds each instantiation; an impossible internal width fails
explicitly rather than selecting an unchecked specialization.

The mathematical algorithm is unchanged. Each row and dependency bitset has
the same layout; pivot selection, XOR order, source IDs, cancellation, proof
reconstruction and symmetry expansion are preserved. The producer continues
to emit full constant/affine identities consumed by the unchanged independent
round34 checker. The round36 independent Python model checks its exact work
counts. No new numerical pivot cache or target-answer reuse is introduced.

All query and per-branch work limits remain unchanged. Deferred work charges
generated rows, pivot-row reductions and reconstructed pivots. Reconstruction
failure produces no partial accepted certificate; uncertified branches retain
the bounded exact CPU fallback. The CPU implementation is portable C++17.
Metal remains opt-in and uses the unchanged supported-shape shader; wider
24/27-variable requested Metal still records CPU shape fallback. Specializing
the host affine stage does not establish GPU execution of that stage.

## Evidence and promotion

The initial deferred implementation and its negative performance result remain
in [round36](../round36/RESULTS.md). A six-variant exploratory CPU pilot motivates
this narrower change; it is not a promotion result. Source-index packing and
full residual-shape specialization are deliberately separate ablations. The
full harness compares the new producer with initial deferred provenance,
accepted symmetry, affine provenance and the old expanded-enumeration exact
algorithm. Small controls additionally retain the other existing methods.

The complete timed interval starts with the public point and includes fresh
packed descent, solving, proof generation/copy/hash, independent certification,
original-equation checks, curve replay and independent reference-ANF evaluation.
Fixture generation, invariant workspace construction and additional offline
auditing are separate. Each arm solves afresh. These planted PDP controls do
not estimate natural relation yield, and their candidate/IC/rho fields stay null.

Small trials use 31 measured repetitions plus one warmup for nine controls;
wide trials use seven plus one for nine 21/24/27-variable controls. Two trials
are predeclared. An unsigned 64-bit `--order-seed` is recorded for each trial;
the auditor reproduces every shuffled arm order and rejects a mismatch.
Admission, all group-start/end samples and final one-minute load must stay at
or below one per logical CPU. Preserve ineligible, failed and interrupted runs.
No local builds, tests or offline mathematical audits run concurrently with
timing. Direct complete-query comparisons, not products of historical ratios,
support any eventual cumulative speedup claim.

Correctness validation covers every residual dimension, equation bits through
128, all 256 three-variable Boolean functions, complete byte-identical proofs
against initial deferred provenance, original-ANF identities, complete roots
and bases, fresh reuse, corruption and forced budget fallback. Physical Metal
and CPU paths are checked separately. Linux CI rebuilds its own native binaries;
hosted/virtualized correctness does not imply a physical-device speedup.

Use ordinary Python; no Sage imports or Sage jobs are required. Build rounds
20, 23, 31, 32, 33, 34, 35, 36 and 37 in order. On macOS append `--metal` for
rounds31 through37 and set `QUADRATIC_TEST_METAL=1` when testing.

```sh
python experiments/groebner-perf-20260924/round37/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round37 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round37/measure_fixed_width.py --correctness-only --repetitions 2 --order-seed 2026092937 --output correctness.json.gz
python experiments/groebner-perf-20260924/round37/measure_fixed_width.py --correctness-only --large-controls --repetitions 2 --order-seed 2026092938 --output wide-correctness.json.gz
python experiments/groebner-perf-20260924/round37/audit_fixed_width.py wide-correctness.json.gz
```

Append `--metal` to include requested Metal measurement arms. Exact original
mathematics, full proof payloads, work/capacity counts, binary/source receipts
and hash-chained journals must pass independent audit before performance is
reported. A GPU win must use the actual GPU and beat the strongest paired CPU
on the full query. CPU dispatch stays the default. No global F4/F5, novel F6,
general asymptotic, new complete IC/rho, or untested-device claim follows from
this bounded code-generation change.
