# Tiled transforms in the independent Boolean basis checker

Round47 integrates the measured tiled block-symmetric Möbius transform into the independent checker as an explicit option. It keeps round45's full transform as the default, its fresh original-ANF symmetry guard, and every proof, root, basis and resource-limit check. The round44 producer and proof format are unchanged. This is a bounded Boolean PDP-stage experiment, not a general F4/F5 algorithm or an IC speedup result.

`adapter.TransformQuery(..., transform="tile16")` selects the candidate for a complete fresh public-point query, including descent, producing a basis and proof, independent certification, checking the original equations and signed curve replay. `independent_checker.Checker` accepts the same option. Available modes are `full`, general square `axes`, `tile8`, `tile16`, `tile32`, and `hoisted` (the same recursion without blocking). The symmetry modes fall back to the full transform when the original-equation guard is unavailable, fails, or exhausts its budget. Odd fixed-variable counts also fall back. Decisions and target coefficients are recomputed on every call.

The transform operates in place on each residual-feature/equation-limb slice. It adds no coefficient table in ordinary builds. The explicit `transform_audit_test=True` build keeps a second table, independently runs the full transform and compares every coefficient; its extra memory and work are separately reported. That build is for correctness only. [PROTOCOL.md](PROTOCOL.md) describes the algebra and counters.

## Reproduction

From the repository root, with Python 3.12 or later and a C++17 compiler:

```sh
for version in 20 23 31 32 33 34 35 36 37 38 44 45; do
  python3 "experiments/groebner-perf-20260924/round${version}/build.py"
done
python3 experiments/groebner-perf-20260924/round47/build.py
python3 experiments/groebner-perf-20260924/round47/run_tests.py
python3 experiments/groebner-perf-20260924/round47/validate_native.py --output /tmp/tiled-correctness.json.gz
python3 experiments/groebner-perf-20260924/round47/audit_queries.py --input /tmp/tiled-correctness.json.gz --output /tmp/tiled-audit.json
```

On macOS, build round44 with `--metal` and pass `--metal` to the validator. The checker is a portable CPU implementation; Metal is an optional producer. These commands use standalone Python and do not launch Sage. Linux and macOS CI rebuild native code on the actual runner and retain binaries, source receipts, all mathematical results, full proof payloads, and runner identity. Hosted Metal availability is explicitly recorded.

Validation retains all 13 adversarial proof/guard test groups under each of six modes, plus four integrated test groups (82 total). The latter cover large coefficient tables, independently recomputed full transforms on actual 18–27-variable queries, fresh symmetry changes, odd shapes, wide equations, lifecycle, concurrency and allocation limits. The 6,001-system frozen corpus is checked with full, axes and tile16, partial production on/off and checker symmetry on/off. All 18 frozen public-point queries run under all six transform modes and both ablations. CPU optimized, CPU UBSan and an available Metal producer are separate configurations. Expected root-limit records remain failures to solve, not wins.

The separate Python audit loads no native library. It verifies every witness and complete root count from the original ANF, checks the reduced Boolean basis, recomputes symmetry and proof-pair accounting, and independently reconciles recursive transform operations. Audit caches are outside query timing. Exact mathematical results must agree with the accepted round44 physical reference.

## Physical correctness evidence

The final formatted implementation passed all 82 targeted groups on a physical Apple M4 Pro. The CPU optimized, CPU UBSan and Metal-producer validation passed 216,036 system records: 215,388 verified and 648 expected producer root-limit records. All 1,296 fresh complete queries matched the accepted proof, complete roots, reduced basis and recovered decomposition. The separate original-ANF audit passed all 1,296 query records and 47 distinct proofs. [The retained evidence](evidence/physical-m4-correctness.json.gz) binds the exact sources, binaries, original reference and audit; full proof payloads remain in the local and CI artifacts.

On the 27-variable coefficient shape, the tiled transform performs 57,908,480 XORs and 8,731,904 mirror stores, versus 108,527,616 full-transform XORs. No ordinary extra coefficient table is allocated. These counts describe only specialization and do not establish a query speedup.

## Measurement boundary

The motivating standalone screen found repeated improvements for some symmetric table sizes and regressions for others. Those timings excluded scatter, guarding and all later proof checks, so they do not establish complete-query speedups. The integration remains opt-in. Complete-query comparisons must include fresh coefficients, guard and fallback costs, transfers, all certification, equation checks and curve replay; target-independent setup stays separate. Keep full, axes, alternative tile sizes, and accepted CPU/GPU query baselines in the comparison. Record failed admissions and inconclusive runs.

No automatic routing, CUDA/OpenCL performance, physical x86 performance, natural relation yield, high-regularity general Gröbner complexity, or full single-target IC/rho improvement is claimed. `candidate_id` and `online_speedup` remain null. Research context and further degree/compression hypotheses are retained in [round46/RESEARCH.md](../round46/RESEARCH.md).
