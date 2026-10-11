# Packed proof production and independent native checking

This opt-in path takes packed Boolean ANF coefficients directly into the existing
sparse F4 producer and passes its derivation DAG to an independent native checker
without subprocess text transport, JSON parsing, or Python graph construction.
It preserves exact derivation checking, ideal inclusion in both directions,
reducedness, ordinary critical pairs and implicit Boolean field pairs.

The native variable range is 1–64, matching the existing producer's monomial
encoding. Up to 4096 Boolean equations use term-major, little-endian coefficient
bitsets. Neither the producer nor this checker enumerates assignments or allocates
a full monomial universe. The Python reference/checker still supports wider
monomial masks. No production dispatcher is changed.

## Independence and ownership

`packed_producer.cpp` compiles the unchanged `Engine` from round five. `build.py`
extracts that source before its CLI adapter at a checked marker; the historical
source, CLI baseline and evidence are untouched. Each call has a fresh engine,
input rows, proof graph and result buffers. Only loaded libraries and configuration
persist. The query takes a snapshot of the original packed input before ctypes
releases the GIL.

`native_checker.cpp` is built into a separate library and imports no producer
code. Its hash-set parity arithmetic differs from the producer's sorted-vector
arithmetic, and it decodes the original packed coefficients independently. The
shared `proof_abi.h` describes data buffers only. It checks:

1. Proof version, ring, order, bounds, backward-only node references, and canonical
   nonzero output rows.
2. Every input/XOR/monomial-multiplication derivation, then equality of the selected
   proof values with the proposed basis. This proves output membership.
3. Zero normal form for every original generator, proving reverse inclusion.
4. Reducedness and all non-coprime basis critical pairs.
5. The required pairs with the implicit equations `x_i^2+x_i`.

Coprime leading monomials use the same established product criterion as the
Python checker. For `x_i` dividing `LM(g)`, the ordinary field-pair S-polynomial
modulo the field ideal is the Boolean polynomial `x_i*g`. This is checked explicitly.
See [round five's mathematical explanation](../round5/README.md).

Work and proof-retention exhaustion are inconclusive. They never certify a
partial result. Partial phase times and producer counters are retained for failed
attempts. `compute()` returns a materialized basis only after checking; optional
`export_proof=True` also materializes the proof for independent replay. The normal
path consumes and then frees the native DAG after certification. No root count
or solution list is implied by the algebraic certificate.

All computation state is call-local; shared-library calls can overlap without
sharing numeric state. Error messages are thread-local. Buffers exposed by the C
ABI remain owned by their result handle until `producer_destroy`; direct C callers
must supply valid buffers of the declared lengths and obey this lifetime.

The packed library has deterministic operation/node/row/retention budgets but
**no hard wall timeout**. The CLI baseline retains a hard subprocess timeout.
Keep the CLI path where process isolation or hard cancellation is required.

## Qualification

Optimized and UBSan trap builds pass eight test groups covering:

- 96 deterministic random controls: 95 verify against the existing CLI producer,
  independent Python algebraic checker and exhaustive truth/staircase oracle;
  one exhausts the declared work budget in all producer variants and remains
  inconclusive.
- 672 mutated claims through both builds: 1344 adversarial checks. Any accepted
  mutation also passes the independent exhaustive oracle.
- Explicit counterexamples for missing output membership, reverse inclusion,
  reducedness, ordinary critical pairs and Boolean field pairs.
- Direct ABI mutations, malformed offsets/masks/coefficient bits, forward graph
  references, and repeated packed masks with parity cancellation.
- Structured inputs through 64 variables; equation bitsets through 4096 equations;
  zero/unit ideals; budget failure followed by successful calls; 64 threaded calls.
- Independent replay of previously retained algebraic certificates.

The new checker has not been separately rerun through Singular. The unchanged
round-five producer previously passed that qualification; current small-ring
tests additionally use exhaustive independent oracles. Structured wide-variable
controls are correctness controls, not evidence of high-regularity performance.

Signed macOS Python rejected the dynamic UBSan runtime in the initial test setup.
The libraries use trap-based UBSan instrumentation instead; an instrumented
violation terminates the test process. The original loading failure and the first
random-budget discovery are retained in the development logs.

## Measurement boundary

The screen and confirmation each retain 23 inputs and all attempts. The three
proof arms are CLI/Python checking, packed/Python checking, and packed/native
checking. All start from the same packed ANF; any expansion into Python row sets
is charged. Library loading and fixed metadata hashing happen once outside the
packed query interval, and setup is recorded. The comparison therefore measures
the complete interface/metadata change, not subprocess launch in isolation.

The algebra boundary ends after independently certified basis materialization.
The supplementary PDP boundary starts from a public target coordinate and includes
fresh descent, proof production, checking, bounded root extraction, equation
evaluation and curve replay, followed by replay against the untouched reference
ANF. The three proof arms use identical extraction code. A fourth PDP arm is the
existing evaluation/interpolation solver using its normal certified-root path.

PDP extraction is deliberately bounded to these 6/9/12-variable controls and may
scan up to 4096 assignments. This is separate from the non-enumerative algebraic
checker; it does not provide a wide-variable root-finding algorithm.

The repetition policy is fixed before measurement: 15 measured repetitions for
structured algebra and six-variable PDP controls, three for difficult algebra
and nine-/twelve-variable PDP controls, plus one retained warmup per arm/input.
An arm pair receives a speedup estimate only if every measured repetition
independently verifies both arms. Inconclusive attempts are never dropped.

`audit.py` validates hashes, frozen workloads, all statuses and paired basis/answer
equality, then recomputes per-input geometric-mean ratios with paired-bootstrap
95% intervals. These intervals describe repetition variability on the measured
host, not uncertainty across hardware or input distributions. No multiple-testing
correction is applied. Parent CPU time excludes CLI child CPU work; it must not be
used as a cross-arm speedup metric. Full wall time is the primary measurement.
Process memory high-water marks are labelled; exclusive per-input peaks are unknown.

The first screen found that failed attempts lacked partial phase/counter details.
The final code fixes this for producer and checker; the confirmation uses the
final code. `screen/` preserves the exact earlier sources for that screen, including
its tests. Historical source hashes are checked against those preserved copies.
CI subsequently required whitespace formatting in the ABI header. `measured/`
preserves the exact pre-format header and measurement-time audit. The live header
is formatted; no algorithm or data-layout change was made.
Rebuilding after formatting produced byte-identical optimized producer/checker
libraries; `formatting-build-receipt.json` retains that comparison.

No factor-base relation yield or target logarithm recovery is measured.
`candidate_id`, `IC_online_ms` and `rho_online_ms` remain null. Evaluation wins on
these small Boolean PDP controls, and the difficult sparse-F4 cases remain
inconclusive at the declared budget. This change is not a new F6 algorithm or a
single-query GPU win.

## Retained results and next bottleneck

Each run contains **720 attempts**, including warmups: **552 verified results
and 168 inconclusive attempts**. Successful results agree on the complete reduced
basis and, for PDP queries, the independently replayed decomposition assignment.
The difficult random/MQ controls and all sparse-F4 nine-/twelve-variable PDP
attempts exhaust the 20-million-work limit in both runs. Evaluation solves all
the small PDP controls. No failed attempt contributes a speedup ratio.

The confirmation measurements on an Apple M4 Pro are:

| Input / boundary | CLI + Python checker median | Packed + native checker median | Paired geometric mean, 95% bootstrap interval |
| --- | ---: | ---: | ---: |
| Pair products, 21 variables / algebra | 12.162 ms | 0.281 ms | 28.19× [15.09, 45.08] |
| Pair products, 32 variables / algebra | 19.329 ms | 0.408 ms | 36.96× [21.43, 61.49] |
| Pair products, 64 variables / algebra | 25.093 ms | 0.753 ms | 17.90× [9.12, 31.51] |
| Free-variable control, 64 variables / algebra | 14.968 ms | 0.147 ms | 80.51× [40.28, 155.67] |
| PDP 6, seed 1 / complete query | 31.349 ms | 57.600 ms | 0.76× [0.40, 1.48] |
| PDP 6, seed 2 / complete query | 55.250 ms | 14.867 ms | 2.52× [1.36, 4.89] |
| PDP 6, seed 3 / complete query | 25.081 ms | 9.187 ms | 2.09× [1.13, 3.76] |
| PDP 6, seed 4 / complete query | 32.717 ms | 54.500 ms | 0.74× [0.40, 1.35] |
| PDP 6, seed 5 / complete query | 41.515 ms | 35.786 ms | 1.20× [0.69, 2.07] |

The large algebra ratios measure interface and checking overhead on structurally
easy systems. They are not faster F4 mathematics. The first screen's five complete
PDP point estimates were 2.33–3.86×, but the confirmation did not reproduce a
consistent full-PDP win. Both runs are retained; **no general 2× PDP claim is made**.
Confirmation load average was roughly 39 to 36 on 14 logical CPUs. A quieter or
isolated environment is needed for reliable small-query wall-time comparisons.
The evaluation arm remains substantially faster on the tested small PDP inputs.

Partial failure statistics now expose the remaining producer work. For example,
the random eight-variable control processed 83 matrices (14,863 rows in total,
271 peak rows) before exhausting its budget. The dense MQ controls peaked at
262–470 rows before exhaustion; the twelve-variable PDP attempts processed one
matrix of 104–119 rows before their budget stops. These are concrete profiling
targets, not evidence that GPU launch overhead is the dominant cost.

Next, profile polynomial normal forms, symbolic preprocessing and row elimination
separately. In the current prototype, normal-form reduction copies and sorts term
vectors repeatedly. Maintaining monomial order in the polynomial representation
is a specific CPU optimization to test, with unchanged independent certification
and the difficult controls retained. GPU integration into this producer also needs
an independently checkable record of row combinations; its complete cost must be
compared with an equivalent CPU reduction policy.

## Reproduce

From the repository root with Python 3.10+ and a C++17 compiler:

```sh
python3 experiments/groebner-perf-20260924/round11/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round11 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round4/build.py
python3 experiments/groebner-perf-20260924/round11/benchmark.py --output /tmp/new-proof-comparison.json.gz
python3 experiments/groebner-perf-20260924/round11/audit.py
```

The audit always checks the two retained runs, not the new output. Preserve
historical receipts when adding experiments. CI builds with GCC on Linux and
Clang on macOS, runs optimized and UBSan tests, and audits the historical evidence.
It does not reproduce historical timing values or claim to execute Metal.
