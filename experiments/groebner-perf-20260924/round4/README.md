# Packed ANF queries and reusable descent structure

This opt-in experiment removes the Python equation-set expansion, sorting,
validation scan and repeated row packing from the round-two query path. It
also precomputes the target-independent Weil-descent contraction layout.
It does not change production F4/F5 dispatch, GPU dispatch, or any frozen
round-one through round-three sources or receipts.

## Measured confirmation

One frozen 18-variable planted query, seed 101, measured on an Apple M4 Pro
host with 14 logical CPUs, Python 3.11.14, macOS 26.6:

| Timed boundary | Original median | Packed median | Paired geometric-mean speedup (95% bootstrap interval) |
| --- | ---: | ---: | ---: |
| Already descended ANF through independent certification and curve replay | 48.368 ms | 8.252 ms | 5.390x (4.794–6.003x) |
| Fresh target-dependent descent through the same checks, with reusable ring preparation available | 137.867 ms | 15.003 ms | 8.325x (6.977–9.813x) |

Each comparison has 15 measured paired repetitions plus a recorded warmup,
with shuffled arm order. Ratios are computed per pair; a ratio of medians is
not the reported geometric mean. The other five frozen seeds have paired
speedups of 4.448–5.486x at the first boundary and 6.454–8.234x at the second.
These are separate single-query controls, never an amortized batch claim.
Host load averages were about 40 despite 14 logical CPUs; uncertainty and
all individual wall/CPU samples are retained. A quieter-host confirmation is
still useful. Reusable native allocation alone has no consistent isolated
win across these inputs; the main wins are packed input and descent planning.

The reusable ring plan took 77.326 ms to construct; initial packed workspace
and library loading took 23.145 ms. These target-independent setup costs are
recorded separately, not divided across targets. Every query recomputes its
coefficients, basis, certificate and curve replay. The benchmark also charges
every arm for checking its answer against the untouched frozen reference ANF.
Full dictionary equality with the original descent is checked before timing.

These are **PDP stage diagnostics on planted correctness controls**. There is
no complete DLP recovery, ordinary-query yield estimate, IC candidate claim,
or comparison against rho. The first boundary excludes target-dependent
descent and must not be represented as a complete online cost. A complete IC
comparison must follow AGENTS.md's canonical candidate records and verified
one-target online interval, charging all target-dependent failures/fallbacks.

## Implementation and independence

* `packed_query.py` snapshots the coefficient dictionary and copies keys and
  coefficient words to contiguous native buffers. It never constructs Python
  equation sets. Fields with more than 64 coefficient bits use explicit limbs;
  equation counts 1..4096 are supported.
* `packed_dual.cpp` scatters whole coefficient words directly into the subset
  transform. Its interpolation is the established Buchberger–Möller method
  retained from round two. A workspace owns reusable numerical storage, which
  is completely reset on each call. The 20-variable and 256-root solver bounds
  remain explicit; root-cap exhaustion is inconclusive, never a refutation.
* `packed_certificate.cpp` independently scans each coefficient bit to recover
  equations, then calls the unchanged direct-ANF certificate. It consumes no
  solver roots or transformed values. This verifier still enumerates up to
  20 Boolean variables; larger algebraic certificates remain future work.
* `descent_plan.py` retains only field multiplication tables, symbolic support
  maps and contraction edges for the fixed `(n, modulus, b, m, ell)`. These are
  functions of ring/factor-base structure, independent of the target. All
  coefficient buffers are zeroed before substituting each new target. Returned
  dictionaries own their values and cannot alias scratch storage.

The native workspaces and descent plans serialize shared access. Separate
workspaces can execute concurrently. Use the Python context manager or call
`close()` to release a native workspace. Calls are synchronous; there is no
hard subprocess deadline in this experimental path.

## Reproduce

From the repository root, using Python 3.10+ and a C++17 compiler:

```sh
python experiments/groebner-perf-20260924/unpack_evidence.py
python experiments/groebner-perf-20260924/build_portable.py
python experiments/groebner-perf-20260924/round4/build.py
python experiments/groebner-perf-20260924/round4/test_packed.py -v
python experiments/groebner-perf-20260924/round4/audit.py
python experiments/groebner-perf-20260924/round4/benchmark.py --repetitions 15
```

Set `CXX=g++` for GNU builds. Tests load both optimized and UBSan libraries.
The local python.org 3.13 framework interpreter rejected the macOS UBSan
runtime under its platform policy; Homebrew Python 3.11 ran the complete suite.
The CI workflow uses setup-python 3.12 on Linux and macOS. Build products stay
untracked. Rebuilt binaries need not match the historical binary hashes.

The nine regression groups cover 84 random ideals, ten frozen workloads,
mutated bases, multiword boundaries through 4096 equations, invalid masks and
coefficients, duplicate cancellation, root-cap recovery, 128 concurrent calls,
original curve replay, and exact descent parity on different ring shapes,
curve coefficients and target coordinates. Frozen large cases compare against
the unchanged native row verifier; the existing certificate CI independently
checks that verifier against the Python oracle. Small random cases directly
use the Python oracle here. The initial slower validation also compared all
large frozen cases and mutations directly against Python.

`results/confirmation.json.gz` preserves all 576 confirmation solve records,
including warmups, with source and executed-binary hashes. `results/summary.json`
is the readable summary. `results/screen.json.gz` retains the first 360-record
screen, and `screen/` preserves its two differing source files. The audit checks
936 verified records and their measured source versions. The two screens have
slightly different checking boundaries; do not pool their timings.

## Remaining goal work

Packed input and reusable ring structure now have measured implementation
evidence. Remaining work includes a scalable derivation-certificate path above
20 variables, a GPU win at the full single-query boundary, and controlled tests
of structural algorithm hypotheses. This change establishes neither a novel
F6 algorithm nor a new asymptotic bound. The full goal remains active.
