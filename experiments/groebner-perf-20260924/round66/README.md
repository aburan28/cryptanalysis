# Prepared constant-identity witnesses

This opt-in checker mode prepares fresh constant witnesses once per check and
scans independently reconstructed coefficient slices without repeating the
symmetry branch. Two portable C++ parity expressions expose regular loops to
the compiler. `constant_identity='original'` retains the preceding loop;
`'prepared'` uses built-in parity and `'folded'` uses explicit XOR folding.
The original loop remains the default. CPU remains the default transform.

The full checker validates proof extent and equation bits and independently
establishes symmetry aliases before preparing any witness. Every scratch word
is overwritten for each proof, including after a failure or a changed input.
At most 16 MiB of extra storage is retained; the 27-variable, 31-equation fixture
uses 1 MiB. Allocation is reusable setup. Witness preparation is charged inside
the complete query's contradiction-check interval. Metadata times are nested
and must not be added to the outer query time.

The mode preserves acceptance, the first failing feature, and the exact prefix
of avoided-parity accounting, including zero and alternative witnesses. It does
not consume producer coefficient tables or elimination state. Changing modes
invalidates prepared generations. Configuration, certification and close remain
serialized. A workspace failure is explicit and leaves the original mode
available. No target answer or proof result is cached.

`generate_checker.py` pins the exact round65 checker hash and derives the small
C++ substitution; a changed reference requires explicit review. The generated
source, full native dependency chain, wrapper, drivers and rebuilt binaries
are hash-bound. The existing producer and proof format are unchanged.

## Validation and reproduction

Build the dependencies through round65 as in the CI workflow, then:

```sh
python experiments/groebner-perf-20260924/round66/build.py
python experiments/groebner-perf-20260924/round66/native_build.py --metal
experiments/groebner-perf-20260924/round66/build/test-constant
experiments/groebner-perf-20260924/round66/build/test-constant-ubsan
INDEPENDENT_TEST_METAL=1 python -m unittest discover -s experiments/groebner-perf-20260924/round66 -p test_checker.py -v
python experiments/groebner-perf-20260924/round66/validate_queries.py --metal --output /tmp/constant-query-correctness.json.gz
python experiments/groebner-perf-20260924/round66/audit_queries.py --input /tmp/constant-query-correctness.json.gz --output /tmp/constant-query-audit.json
python experiments/groebner-perf-20260924/round66/measure_queries.py --metal --output /tmp/constant-query-diagnostic
```

Omit `--metal` and `INDEPENDENT_TEST_METAL` for a CPU-only build. The kernel
controls cover both word widths and one/two equation limbs. Full-checker tests
compare with the unchanged round65 native checker, including malicious proofs,
valid alternatives, budgets, first failure, stale inputs, configuration,
thread/owner boundaries, explicit unavailable Metal and failed allocation.
Full queries span all three identity modes, original producer/checker backend
pairs, sanitizers and serial/prepared/overlapping schedules. The original-ANF
oracle independently checks proof identities, complete roots and exact bases.
CI rebuilds Linux and macOS separately and archives full proof payloads.

The physical-M4 profile and kernel results in `RESULTS.md` motivated this
integration. They remain kernel-only, ordinary-host diagnostics; they are not
complete-query speedup evidence. The full-query diagnostic has balanced arm
positions and predecessor pairs: six-arm Williams orders with a Metal producer,
or all six three-arm permutations for a CPU producer. Every observation and
failure is retained; context setup is separate and all per-query checks remain
charged. A controlled CPU speedup or CPU/GPU crossover requires the repository's
host-isolation receipt. No automatic dispatch or asymptotic/F6 claim is made.
These are synthetic algebra/PDP controls, not natural relation-yield estimates
or a one-target IC/rho comparison.
