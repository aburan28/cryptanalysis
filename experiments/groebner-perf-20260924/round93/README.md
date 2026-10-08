# Completion before derivation replay

An incomplete candidate can waste most of its verification time reconstructing
proof values before failing a cheaper algebraic obligation. This opt-in checker
schedule tests reverse inclusion, reducedness and Boolean Gröbner completion
first. A successful result must then pass the original-equation derivation proof.
No acceptance condition or independent polynomial arithmetic is removed.

The default schedule remains `legacy`. `Query(checker_order='completion-first')`
selects the new path for both fresh F4 and reusable Macaulay calls; `proof-first`
runs the refactored checker in its original order for equivalence controls.
Original packed input bytes, production, fallback and budget accounting are
unchanged. Read [PROTOCOL.md](PROTOCOL.md), [RESULTS.md](RESULTS.md) and
[NEXT_STEPS.md](NEXT_STEPS.md) for boundaries and remaining work.

```sh
python3 experiments/groebner-perf-20260924/round93/run_validation.py \
  --output /tmp/completion-first-validation
# Optional exploratory diagnostics, separately labelled:
python3 experiments/groebner-perf-20260924/round93/run_validation.py \
  --diagnostics --output /tmp/completion-first-diagnostics
```

Use Python 3.13 and a C++17 compiler. Validation binds sources to Git, rebuilds
all ten libraries on the current platform, and holds the shared heavy-work lock.
CI rebuilds on Ubuntu 24.04 and macOS 15. It never uses this machine's binaries
for another platform. No Sage or GPU runtime is involved.

The lossless archive under `results/` uses `MANIFEST.json` to map logical paths
to hash-addressed `objects/`. It retains frozen sources/native builds, raw
successes/failures, independent audits, development logs, and synthetic
publication controls. The latter are explicitly not hosted CI. Archived native
libraries are never loaded by the artifact auditors.

This result reduces wasted verification time in some failed proposals. The dense
MQ inputs remain unsolved under their fixed limits. No qualified speedup, new
F6 complexity result, full curve-query result or one-target IC/rho result follows.
