# Narrow coefficient words with unchanged exact certificates

Round 33 selects specialization-word widths from the immutable equation count.
For at most 32 equations, the producer now stores one `uint32_t` per residual
coefficient instead of two `uint64_t`s; the independent checker stores one
`uint32_t` instead of one `uint64_t`. The Metal input is a packed `uint` array.
For 33–64 equations the producer uses one `uint64_t`; for 65–128 equations its
two-limb representation remains available. Original packed inputs and the
uint64-limb certificate format are unchanged. Padding is validated **before**
narrowing. CPU execution remains the default.

This changes representation and memory traffic, not the quadratic-lifting
algorithm or the proof obligation. The producer still generates equation
combinations proving that rejected branches satisfy `1 = 0`. The checker
independently reconstructs the original specialized equations, checks every
identity, enumerates every original residual assignment in unresolved branches,
and proves the returned reduced Boolean basis using complete roots and the
Boolean staircase. It shares neither the producer's specialization table nor
its elimination state. Layouts and allocations may persist across queries;
coefficients, roots, proofs, and numerical state are rebuilt for each query.

## Memory accounting

For the frozen 18-variable, 31-equation controls (`x=12`, `y=6`, 4096 branches,
22 coefficients per branch), the native counters must equal:

| Counted allocation | Round 32 bytes | Round 33 bytes |
| --- | ---: | ---: |
| CPU producer table plus proof | 1,474,560 | 393,216 |
| Independent checker table | 720,896 | 360,448 |
| Combined CPU count | 2,195,456 | 753,664 |
| Combined Metal producer, buffers, proof, and checker | 4,194,316 | 1,671,180 |

These are accounted native workspaces, **not total process peak memory**. They
exclude ANF/descent storage, roots/basis containers, allocator overhead, and
Python copies. The auditor derives the expected counts from the frozen shape,
equation width, and actual device execution and rejects inconsistent metadata.
The producer table and GPU input are four times smaller in this width class;
the checker table is twice as small. Those ratios are not runtime speedups.

The unchanged 64 MiB limit applies separately to each specialization table.
Known-root nonlinear controls with 27 and 28 variables now fit that limit and
pass independent certification. This is a capacity result for those controls,
not a claim that arbitrary 27/28-variable point queries finish within the
unchanged enumeration, root, or basis-proof budgets.

## Evidence and limits

`test_narrow.py` replays the prior exhaustive and adversarial certificate tests
against the new producer/checker and adds equation-width boundaries
1/31/32/33/63/64/65/127/128, invalid-padding rejection before narrowing,
simultaneously loaded old/new libraries, bit-identical certificates, and
cross-certification in both directions. UBSan and deliberately small-budget
builds are exercised. Metal remains explicit and capability checked; more than
32 equations or 31 lifted features uses the recorded CPU fallback.

`test_narrow_queries.py` covers all eleven frozen public-point fixtures:
six 18-variable targets, 15-, 9-, and 6-variable controls, and 21/24-variable
controls. It compares complete old/new queries, forbids Python ANF expansion
inside solving, checks certificates with both libraries, and independently
enumerates the original Boolean system and replays the curve witness.

`packed_reference.py` is an **offline-only** Python audit model. It groups
original monomials and directly enumerates their containing fixed assignments,
packing disjoint residual-coefficient fields into Python integers. It uses
neither native zeta transform nor native elimination. Exhaustive small truth
functions, random equation widths, direct coefficient reconstruction, and all
eleven frozen fixtures agree with the untouched round-31 direct model. The
full-space chunked truth oracle remains the unchanged round-32 reference.
Its exact-input caches are used only during offline evidence auditing, never
inside a timed query. `results/reference-differential.json` records the larger
differential controls and both model source hashes.

`measure_narrow.py` retains the original full-query boundary: public target
validation, fresh packed descent, solving, independent certificate, original
equation checks, full-point curve replay, and untouched reference-ANF evaluation.
Reusable setup and fixture generation are separate. Immutable certificate copy,
hash, and verification are charged; archival base64 export is outside the clock.
Each report has an append-only journal and source/build/device identities.

The nine small controls compare four CPU arms (sparse, conditional quadratic,
round-32 certificates, and narrow certificates), plus three explicit Metal
arms when requested. A GPU claim must beat the **fastest paired CPU arm** with
the lower endpoint of its paired bootstrap interval above one. All attempts
must verify. Wide controls are correctness-only until a stronger wide CPU
comparison is paired. Busy-host admissions, failures, and fallbacks remain
explicit results; a failed admission starts zero timed attempts.

The initial physical M4 Pro performance attempt was not admitted: one-minute
load 72.94 on 14 logical CPUs, versus the predeclared limit of 14. Retained
correctness timings therefore establish **no new speedup**. The controls are
planted PDP component fixtures. They establish neither natural relation yield,
complete IC recovery, comparison with one-target rho, general high-degree
behavior, nor an asymptotic improvement or a novel “F6” algorithm.

The physical M4 Pro build passes all 29 test groups. The two retained
`*-final.json.gz` bundles contain 213 verified complete queries (189 small,
24 wide), including their warmups. Both bundles and their journals pass the
independent source-bound audit. None is performance eligible.

## Reproduction

From the repository root, use ordinary Python (these programs do not use Sage):

```sh
python3 -m pip install numpy==2.4.0
python3 experiments/groebner-perf-20260924/round20/build.py
python3 experiments/groebner-perf-20260924/round23/build.py
python3 experiments/groebner-perf-20260924/round31/build.py
python3 experiments/groebner-perf-20260924/round32/build.py
python3 experiments/groebner-perf-20260924/round33/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round33 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round33/measure_narrow.py --correctness-only --repetitions 2 --output /tmp/narrow-correctness.json.gz
python3 experiments/groebner-perf-20260924/round33/audit_narrow.py /tmp/narrow-correctness.json.gz
```

On macOS, add `--metal` to all three round-31/32/33 builds, set
`QUADRATIC_TEST_METAL=1` for tests, and add `--metal` to measurement. Use a new
output path for every run. Add `--large-controls --correctness-only` for the
21/24-variable evidence. For an eligible small-control performance experiment,
omit `--correctness-only`, use `--repetitions 31`, keep the default load gate,
and repeat in a separate clean process before drawing a conclusion.

The `narrow-coefficients.yml` workflow builds native code independently on
Linux and macOS, runs the tests, records fresh complete-query evidence, and
audits both fresh and retained bundles. Hosted or virtual device correctness
does not establish a speedup on physical hardware.

The next performance decision is whether reduced coefficient traffic improves
the complete query. After that, charge polynomial-multiplier contradiction
construction and independent checking against the residual enumeration it
replaces; any extension must preserve exact completeness and explicit budgets.
