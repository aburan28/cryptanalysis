# Exact reusable separator message for fresh S3 targets

The final S3 link of the frozen `GF(2^9)`, four-summand, `ell=3` chain
depends on only 12 of its 30 Boolean variables. This candidate first builds
the 24 target-independent equation factors, eliminates the other 18 variables
once, and retains both the residual boundary factors and witness maps. Fresh
queries construct the nine target-dependent S3 coordinate equations, build
their factors, eliminate a query-local copy of the boundary problem, recover
the cached static witnesses, and check every original ANF equation and the
actual curve points. The target value and target-specific factor tables are
never stored in the layout.

The same 21-variable bag cap and 100-million-state logical cap apply to
setup and each query. Cached static factor and elimination states are charged
to the logical per-query counters; physical setup time and memory are reported
separately. The primary paired timer starts before target-specific equation
construction and stops after independent Python ANF and curve-point replay.
It excludes reusable layout setup, source loading, process launch, and
artifact serialization. The matched prepared-factor arm uses the same Python
field, symbolic maps, curve, target, and checks.

The frozen panel has target abscissae `0, 1, 2, 9, 100, 511`, one warmup, and
five alternating measured pairs. `semantic_replay.py` checks all 512 target
abscissae against the predecessor's independently enumerated screen.
`test_message.py` checks 90 random small systems against exhaustive
enumeration in optimized and UBSan builds and selected S3 controls.

The exact Boolean separator is a conditional, width-bounded method. A
controlled CPU timing ratio requires an isolated-host receipt under
`docs/ISOLATED_BENCHMARKS.md`; the local macOS panel is exploratory. The next
research comparison should measure ordinary relation yield and one-target IC
online time, including failed attempts, rank, descent, and scalar recovery.

After freezing source, run:

```sh
python3 experiments/groebner-f6-packed-20261009/build.py
python3 experiments/groebner-f6-prepared-20261009/build.py
python3 experiments/groebner-f6-message-20261009/build.py
python3 experiments/groebner-f6-message-20261009/test_message.py
python3 experiments/groebner-f6-message-20261009/semantic_replay.py --output /absolute/replay.json
python3 experiments/groebner-f6-message-20261009/profile.py --output /absolute/profile-directory --reps 5
```
