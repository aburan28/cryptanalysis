# Grouped multiplier checking in the independent Boolean verifier

Round48 tests eight ways of verifying affine multiplier contradiction certificates against freshly reconstructed original ANF coefficients. It targets the multiplier-check stage of the bounded Boolean PDP query. The round44 producer, proof format, complete-root proof and reduced-basis checks remain intact. The independent checker remains a portable CPU implementation; Metal is an optional producer.

Use `adapter.IdentityQuery(..., identity="factored_local")` or `independent_checker.Checker(..., identity="factored_local")`. The default is `dense`. The existing explicit `transform` option is retained, with `full` as its default. No automatic routing is added.

| Identity mode | Candidate change |
| --- | --- |
| `dense` | Numeric monomial multiplication and a byte array |
| `reduce` | Dense multiplication with OR reduction of the identity bytes |
| `packed` | Dense multiplication into packed identity bits |
| `local` | Dense multiplication after copying this branch's coefficients |
| `grouped` | Combine contributions to each output monomial before parity |
| `grouped_local` | Grouped multiplication with a fresh local coefficient copy |
| `factored` | Also factor repeated uses of the same coefficient |
| `factored_local` | Factored multiplication with a fresh local coefficient copy |

Only the bounded monomial layout is reusable. Each certification scatters the current original ANF and each local copy is overwritten for the current branch. The candidate never reads producer matrices, ranks, pivot choices or coefficient tables. [PROTOCOL.md](PROTOCOL.md) derives the identities and describes the counters and limits.

## Reproduce correctness

From the repository root with Python 3.12 or later and a C++17 compiler:

```sh
for version in 20 23 31 32 33 34 35 36 37 38 44 45 47 48; do
  python3 "experiments/groebner-perf-20260924/round${version}/build.py"
done
python3 experiments/groebner-perf-20260924/round48/run_identity_tests.py
python3 experiments/groebner-perf-20260924/round48/run_tests.py
python3 experiments/groebner-perf-20260924/round48/validate_identity.py --output /tmp/grouped-coefficients.json
python3 experiments/groebner-perf-20260924/round48/validate_native.py --output /tmp/grouped-correctness.json.gz
python3 experiments/groebner-perf-20260924/round48/audit_queries.py --input /tmp/grouped-correctness.json.gz --output /tmp/grouped-audit.json
```

For Metal on macOS, build round44 with `--metal` and pass `--metal` to `validate_native.py`. These commands use standalone Python, not Sage. CI rebuilds native code on Linux and macOS, reports actual device availability, and retains all binaries, receipts, proof payloads and failures.

The coefficient oracle multiplies one equation at a time in the Boolean quotient. It compares every output coefficient of all eight modes in optimized and UBSan builds, including exhaustive small systems, equation-word boundaries, cross-limb cancellation and fresh valid/invalid/valid inputs. A separate audit checker repeats the old native multiplication on actual proofs and compares every coefficient, including the zero coefficients above degree three. The ordinary checker does not run this extra audit.

All 13 inherited adversarial proof/guard groups run under each identity mode, followed by three integrated identity groups (107 total). The inherited transform suite runs separately (82 groups). The 6,001-system corpus runs all identity modes with the full transform, partial production on/off and symmetry on/off. All 18 complete public-point query fixtures also run each mode with full and tile16 transforms, both ablations, and CPU optimized, CPU UBSan and available Metal producer configurations. Expected root-limit cases remain inconclusive records. A separate Python audit verifies every proof, full root count and reduced basis directly from the original ANF and reconciles physical versus symmetry-derived work.

## Physical correctness evidence

The final binaries passed the 107 identity groups, 82 transform groups and 326,112 native coefficient replays (6,401,696 coefficient comparisons) on a physical Apple M4 Pro. CPU optimized, CPU UBSan and actual Metal-producer validation completed 576,096 system records and 3,456 fresh complete queries. Expected producer root-limit cases remain inconclusive records. The separate original-ANF audit passed every query and all 47 distinct proof payloads. [The retained evidence](evidence/physical-m4-correctness.json.gz) binds the exact sources, native binaries, accepted reference, integer counters and independent audit.

Two interrupted physical attempts are retained separately in the local evidence; neither counts as a complete validation. The earlier sandboxed CPU-only run explicitly recorded Metal as unavailable. Evidence journals now stream compressed to avoid their previous gigabyte-scale temporary footprint. Correctness reports do not establish performance.

## Performance boundary

At nine residual variables and up to 64 equations, grouping reduces source-level parity calls from 460 to 130 per checked multiplier record. Factoring additionally reduces coefficient ANDs from 460 to 379, at the cost of 81 witness XORs. A local copy reads 46 coefficient words from the original table, then performs the selected computation from local storage. These are exact operation counts, not measured speedups or machine-instruction counts.

Only complete fresh-query comparisons can establish a useful improvement. Include coefficient reconstruction, all checks, data conversion and transfer, and curve replay; keep target-independent setup separate. Compare against the actual accepted CPU and Metal paths and retain failed timing admissions. Audit builds are excluded from timing. This experiment does not establish a general F4/F5 improvement, asymptotic novelty, natural relation yield or full single-target IC/rho speedup; `candidate_id` and `online_speedup` remain null.
