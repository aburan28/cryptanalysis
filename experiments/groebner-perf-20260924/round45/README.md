# Independent symmetry in complete Boolean basis verification

Round45 reduces repeated verification when swapping two fixed-variable blocks leaves every original equation unchanged. The CPU checker proves that symmetry afresh from independently decoded packed ANFs, checks representative certificates, and carries their exact counts to matching branches. The existing round44 producer and tagged proof format are reused. Mismatched proofs, asymmetric inputs, odd splits and exhausted optimization budgets retain complete verification.

This is an opt-in Boolean split solver/checker experiment. It does not change default dispatch or establish a general F4/F5 complexity improvement. The checker itself runs on the CPU; the unchanged producer may use Apple Metal.

`adapter.SymmetryQuery` wraps round44's complete public-point query, including fresh descent, the unchanged producer, independent root and reduced-basis verification, original-equation checking and signed curve replay. `independent_checker.Checker(..., symmetry=False)` is an ablation with the previous checker arithmetic. `configure_symmetry(bool)` can switch a reused context; it never preserves target coefficients or prior decisions. See [PROTOCOL.md](PROTOCOL.md) for the proof, budgets and counter definitions.

## Reproduction

From the repository root, build the accepted dependencies before the new checker:

```sh
for version in 20 23 31 32 33 34 35 36 37 38 44; do
  python3 "experiments/groebner-perf-20260924/round${version}/build.py"
done
python3 experiments/groebner-perf-20260924/round45/build.py
cd experiments/groebner-perf-20260924/round45
python3 -m unittest -v test_symmetry.py test_sparse_guard.py test_adapter_isolation.py
python3 validate_native.py --output /tmp/symmetry-correctness.json.gz
python3 audit_queries.py --input /tmp/symmetry-correctness.json.gz --output /tmp/symmetry-audit.json
```

On macOS, build round44 with `--metal` and pass `--metal` to `validate_native.py`. Device availability is an explicit result. Linux and macOS CI rebuild all native dependencies on the runner and retain actual binaries, receipts, runner identity, every query result and full proof payloads. A hosted paravirtual Metal device is not a physical M4 performance measurement.

The validator runs all 6,001 frozen systems with partial-affine production and checker symmetry each enabled and disabled, on optimized CPU and UBSan, plus the selected Metal producer when available. It compares with round44's independent checker, brute truth and reduced bases, the original-ANF witness oracle, and the immutable physical reference. Root-limit cases remain inconclusive records. It also executes all 18 frozen public-point inputs in every configuration. The separate Python audit checks every full proof from original equations, recomputes symmetry and alias matching using dictionaries and tuples, checks complete roots and reduced bases, and reconciles physical and inferred work.

## Physical evidence and measurement limits

The physical Apple M4 Pro implementation passed 72,012 system records: 71,796 verified and 216 expected producer root-limit records. It passed 216 fresh complete queries with 47 distinct proofs and 13 targeted test groups. The packaged implementation independently passed the same 72,012 records and 216 complete queries. Its separate Python original-ANF audit passed all 216 query records and 47 distinct proofs, including independently derived symmetry and avoided-work accounting. [The retained physical evidence](evidence/physical-m4-correctness.json.gz) identifies exact sources and binaries; full proof payloads remain in local and CI artifacts.

On the three 27-variable controls, enabling symmetry changed physically enumerated assignments from 57,388 / 56,314 / 57,540 to 28,756 / 28,202 / 28,818. Partial-affine work changed from 16,394,615 / 16,117,783 / 16,507,779 to 8,215,996 / 8,072,767 / 8,267,885. The new guard costs roughly 1.53 million additional abstract units and 1,310,720 auxiliary bytes. These counts have different meanings and are not wall-time speedups.

A first exact guard scanned all coefficient pairs. The support-only revision reduced its original-ANF coefficient comparisons from 6,017,536 to 89,280 on each of these controls, while retaining cancellation, unsorted-input and wide-limb checks. The complete transform still runs in full. Neither operation-count reduction establishes a complete-query elapsed-time gain.

The preceding round44 paired timing attempt completed 864 verified 18-variable queries, but only one trial met its load gate and no repeated win was established. Two rejected admissions exhausted the predeclared retry limit; the other 31 planned trials were not run. That result remains a non-promotion. Round45 needs its own source-frozen, repeated complete-query comparison including guard costs and all prior comparators. No automatic routing changes are enabled.

These are planted PDP-stage controls. They do not estimate natural relation yield, a complete single-target IC/rho speedup, other devices, high-regularity general systems, or asymptotic improvement. `candidate_id` and `online_speedup` remain null.
