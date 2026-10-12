# Last-use proof reclamation

This opt-in independent checker releases a derived polynomial after its final
operand/output use. It still evaluates and validates every proof node, including
unused nodes. Accepted outputs must pass original-equation derivations, reverse
ideal inclusion, reducedness and Boolean Gröbner completion.

The public query consumes packed ANF directly through the existing native path.
`Query(retention='release-cumulative', checker_order='completion-first')` reclaims
values while preserving the cumulative term limit. `release-live` instead limits
simultaneously live proof terms: that is an explicit resource-policy change.
`baseline` remains the default. `keep` instruments the original retention behavior
for equivalence tests. No automatic CPU/GPU routing changes here.

Read [PROTOCOL.md](PROTOCOL.md), [RESULTS.md](RESULTS.md) and
[NEXT_STEPS.md](NEXT_STEPS.md). The complete-call panel includes failed proposals,
all checking and fallback. Fixture packing and reusable setup are separate.

```sh
python3 experiments/groebner-perf-20260924/round94/run_validation.py \
  --output /tmp/proof-liveness-validation
# Optional, separately labelled exploratory observations:
python3 experiments/groebner-perf-20260924/round94/run_validation.py \
  --diagnostics --output /tmp/proof-liveness-diagnostics
```

Python 3.13 and a C++17 compiler are required. The driver binds sources to Git,
rebuilds twelve native libraries on the current platform, and holds the shared
heavy-work lock. It runs ordinary Python, not Sage. CI rebuilds independently on
Ubuntu 24.04 and macOS 15. Archived native binaries are not executed by audits.

The lossless `results/development-evidence.tar.xz` archive maps logical files
through `MANIFEST.json` to content-addressed objects. It retains original frozen
sources, native builds, controls, failures, raw observations, independent audits,
and explicitly synthetic publication controls. Its receipt verifies every byte.
A later audit-only change independently reconstructs all accepted lifetimes;
the source bridge verifies unchanged generated native sources and does not
replace or repeat the original timing panel.

The useful measured change is logical proof storage; it is not process RSS.
Timing is noisy and unqualified. Difficult dense-MQ inputs remain unsolved under
the frozen budgets. The full-query, GPU, F6 and single-target IC goals remain open.
