# Reusable packed factors for one fresh S3 target

This experiment prepares the factor truth tables for equations whose ANF
coefficients do not depend on the target abscissa. The immutable layout stores
the first two S3 links and all block-local point-lift constraints of the
frozen `GF(2^9)`, `m=4`, `ell=3`, `b=1`, modulus `515` chain. Its native table
construction, source loading, and memory are charged to setup. Each query
then constructs the final nine S3 coordinate equations from a fresh target,
builds those factors, copies the cached static tables into a query-local
workspace, eliminates all Boolean variables anew, checks the original ANF
equations, and replays a positive answer with actual curve points. No target
answer or target-dependent factor table is cached.

The matched cold arm gets the same prepared Python field, symbolic coordinate
maps, static ANF equations, and curve. It builds every native factor table on
each query. Both arms use the same 21-variable bag cap, 100-million-state
logical cap, target, query-local elimination, and equation/point checks. The
prepared arm charges cached factor states to that same logical cap and reports
them separately as reused work. Its native layout uses an insertion index to
preserve the cold arm's exact factor order. The primary paired interval starts
immediately before constructing the target-specific final S3 equations and
ends after independent ANF and curve-point replay. Setup, process launch,
fixture construction, source hashing, and evidence serialization are outside
that interval and reported separately.

The frozen target panel is `0, 1, 2, 9, 100, 511`: two reachable abscissae,
the recorded bare-S3 counterexample after point-lift filtering, and three
further unreachable abscissae. One warmup and five measured alternating
AB/BA pairs are retained per target. `semantic_replay.py` checks the prepared
arm on all 512 target abscissae against the independently enumerated and
equation-checked predecessor screen. `test_prepared.py` adds small random
systems checked by exhaustive enumeration and optimized/UBSan S3 controls.

Run the exact prototype after freezing its source:

```sh
python3 experiments/groebner-f6-packed-20261009/build.py
python3 experiments/groebner-f6-prepared-20261009/build.py
python3 experiments/groebner-f6-prepared-20261009/test_prepared.py
python3 experiments/groebner-f6-prepared-20261009/semantic_replay.py --output /absolute/replay.json
python3 experiments/groebner-f6-prepared-20261009/profile.py --output /absolute/profile-directory --reps 5
```

The local macOS host is contended; its paired wall ratios diagnose the
candidate and need an isolated-host receipt before any controlled CPU speedup
claim. The work is a Boolean point-decomposition stage. A complete IC
one-target comparison continues to require the relation, rank, descent,
scalar-recovery, and paired-rho accounting in `AGENTS.md`.
