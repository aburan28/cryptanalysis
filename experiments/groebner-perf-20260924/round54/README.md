# Whole-row work reservations for independent affine witnesses

Round54 changes the accounting loop in the independent partial-affine checker.
The round53 checker repeatedly checks its work budget and writes work/parity
counters while reading each coefficient word. For a nonzero witness row, this
candidate first checks whether the entire row fits the remaining allowance.
When it fits, local counters accumulate the exact executed prefix and flush on
every exit. A row near the limit retains the original per-operation charging.

This is an implementation optimization, with the same work bound and algebra.
Nonlinear witnesses and audit exceptions still flush the exact prefix before
rejection. Rank reconstruction, complete residual enumeration, original ANF
identities, reduced Boolean basis checks, direct equations and curve replay all
remain required. The largest supported row has 112 coefficient words. The
32-bit coefficient case has one witness limb by construction; the reserved
loop exposes that existing invariant to the compiler.

The experimental adapter uses `partial_reservation='reserved'`; `direct`
provides an ablation in the same binary. Both use the unchanged round51 producer
and round53 preparation scheduler. Serial preparation and the portable CPU
backend remain defaults; `preparation='overlap'` and Metal require explicit
selection. Prior adapters are unchanged. Configuration invalidates pending
prepared generations, and every scheduled query drains its worker.

The new receipt records reservation attempts, rows, budget fallbacks, flushes,
exception flushes, charged words and completed parity words. Old logical
counters and failure codes must match the prior checker. The separate
`reservation-budget` UBSan build permits runtime test budgets; production
builds reject that interface and retain the compile-time allowance. Tests sweep
budgets 0 through 512 for valid and corrupted witnesses, cover equation-word
boundaries through 128, and exercise the maximum row and all-zero witnesses.

After building the existing dependencies through round53, run:

```sh
python experiments/groebner-perf-20260924/round54/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round54 -p 'test_*.py' -v
for mode in reserved direct; do
  python experiments/groebner-perf-20260924/round54/validate_native.py --partial-reservation "$mode" --output "correctness-$mode.json.gz"
  python experiments/groebner-perf-20260924/round54/audit_queries.py --input "correctness-$mode.json.gz" --output "audit-$mode.json"
done
```

Add `--metal` to validation when that backend was built. Set
`QUADRATIC_TEST_METAL=1` for unit tests only after detecting an actual device.
CI rebuilds native dependencies on each runner and records actual hardware.
Each mode checks the frozen 6,001-system corpus and 18 complete public queries
through 27 variables against checker53. CPU, CPU UBSan and available Metal,
both symmetry settings, full/tile16 transforms, and all preparation schedules
are covered. Offline Python proof replay reads the original ANFs and loads no
native solver or checker. Sources and binaries are bound before and after runs.

The frozen measurement plan compares complete fresh queries in seven arms.
The primary comparison isolates reserved serial Metal checking against prior
serial Metal and the direct ablation. CPU and overlap measurements are
secondary. Each arm receives the same maximum allowance of two CPU query
threads and the same GPU; serial uses one thread. The timed interval includes
input reconstruction, solving, verification, transfers, synchronization,
worker drain and equation/curve replay. Reusable setup is separate. Timing
requires both modes' complete correctness and independent audits. Rejected
load admissions, failures and unrun trials are retained. Checker phase medians
are descriptive: partial checking is nested in enumeration, and preparation
may overlap production, so those values must not be summed as exclusive costs.

These are bounded query-stage diagnostics. `candidate_id` and complete
single-target IC/rho `online_speedup` remain null. Removing stores in compiled
assembly does not establish a speedup. No new asymptotic algorithm, global
performance record or automatic device-routing decision is claimed.
