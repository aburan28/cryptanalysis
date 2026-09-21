# Direct-order polynomial reduction

`PACKED_DIRECT_REDUCE=1` selects a generated reducer that avoids reversing the
upper product coefficients to compute the quotient. Its default is zero,
which retains the previous implementation. Both modes use the existing
GF(2^131) modulus and polynomial representation.

The change applies to ordinary polynomial products, both outputs of paired
products, and polynomial squaring. It preserves the walk formula, batch
inversion, distinguished-point rule, report format and checkpoint format.

## Identity

For an input product of degree at most 260, let `H = product >> 131`, a
130-bit vector. Addition below is XOR:

```text
R = H ^ (H >> 1) ^ (H >> 3)
Q = H ^ (R >> 1) ^ (R >> 9) ^ (R >> 25) ^ (R >> 57) ^ (R >> 121)
T = Q ^ (Q << 2) ^ (Q << 3)
remainder = product ^ T ^ (Q << 124) ^ (T << 64) ^ (T << 96)
                    ^ (T << 112) ^ (T << 120) ^ (T << 128)
```

The final result is truncated to 131 bits. This is the existing reciprocal
quotient circuit conjugated by reversal on 130-bit vectors: a truncated left
shift becomes a right shift after reversal. The final remainder circuit is
unchanged. The top word of `H`, `R` and `Q` contains at most two bits, allowing
the generated code to omit shifts whose results are known to be zero.

The nine-word input represents a degree-260 product. Tests also preserve the
old convention that unused upper bits of the ninth word are ignored; this
does not extend the routine to reduction of arbitrary degree-287 inputs.

## Compiler tradeoff

CUDA 13.0.48 on `sm_120`, with batch 32, 256 threads and minimum two resident
blocks, reports 128 registers per thread in both modes. The ordinary product
helper falls from 583 to 564 non-NOP instructions, and the paired helper from
1,140 to 1,098. Their BREV counts fall from 10 and 20 respectively to zero.

The caller's stack frame grows from 16 to 48 bytes. A static branch/call model
of one full batch step, with all 32 slots live, no report emission and no guard
handling, counts 4,437 versus 4,328.125 instruction visits per scalar update.
Those totals include the new local-memory instructions. Logical steady spill
traffic rises from 31 to 52.625 bytes per update, with another
`0.75 / launchSteps` bytes from initial pointer stores.

These are compiler and path-model observations. Instruction visits are not
cycle estimates, and local load/store bytes are not measured DRAM traffic.
Controlled GPU measurements determine whether this tradeoff improves throughput.

## Validation and measurement provenance

Generator checks compare all 261 product basis vectors, edge inputs and dense
inputs with polynomial long division. Independent checks exercise the actual
generated C++ and word boundaries under UndefinedBehaviorSanitizer. Field
tests cover basis products, both paired outputs, squares and canonical outputs.
Host actual-kernel fixtures inject zero denominators and guard-boundary
conditions. GPU client and checkpoint comparisons cover state transitions,
report replay, checkpoint resume and guard-boundary reseeding.

The controlled comparison uses the same B32/T256/min2 geometry and 192,512
workers for both modes. Every timed sample completes 201,863,462,912 scalar
walk updates. Warm-ups are excluded from ranking, controls bracket the screen,
and a qualifying candidate receives three alternating benchmark confirmations
and three collection samples per mode. Matching logical workloads must produce
the same sorted report corpus with zero drops.

## Controlled GPU comparison

The [complete comparison](benchmarks/direct-reduction/comparison.json) uses one
RTX PRO 6000 Blackwell Server Edition, CUDA 13.0.48, native sm_120 code and
driver 580.95.05. Its three alternating confirmations per mode measured:

| Workload | Reciprocal reducer | Direct reducer | Change |
|---|---:|---:|---:|
| Benchmark median B scalar updates/s | 6.826154 | **6.906059** | +1.17% |
| DP34 collection median B scalar updates/s | 6.722592 | **6.799047** | +1.14% |

Benchmark ranges were 6.825899–6.827569 and 6.904167–6.909294 B/s respectively.
Collection ranges were 6.718760–6.723208 and 6.797970–6.801348 B/s. The direct
reducer was faster in every paired repetition. Both GPU arithmetic and full
client suites passed; common-seed normalized states matched at 64 and 16,384
slots. The runtime resource reports matched the compiler comparison.

Every sample completed **201,863,462,912 scalar updates**. All six collections
contained **5,149 records, 164,768 bytes and zero drops**, with identical sorted
record hashes. Warm-ups and the initial screen are retained separately from
the confirmation and collection medians. The screen's bracketing control drift
was -0.2614 percent.

The raw comparison SHA256 is
`818cbdab45336ddacd87364afc20edb35206d16d67b537dc1a082b02edf2804d`.
It retains all 98 source-file hashes, both binary identities, compiler/device
metadata, resource probes and validation outputs. This paired comparison
estimates the change's gain; a later native audit validates the published
entry point. Rates from different allocations must not be used to infer an
additional speedup. GPU clocks in metadata are a snapshot before validation,
not an operating-clock trace.

## Native preset audit

The [native audit](benchmarks/direct-reduction/native-audit.json) runs the
published `make audit-rtx-pro6000` command on a separate GPU allocation:

| Workload | Median B scalar updates/s | Range across three repetitions |
|---|---:|---:|
| Complete walk benchmark | **6.905227** | 6.884149–6.928427 |
| DP34 collection | **6.767191** | 6.765677–6.767747 |

All six samples completed 201,863,462,912 updates with the requested 192,512
workers and reducer mode 1. Each collection recorded 5,149 points, 164,768 bytes
and zero drops. This native wrapper checks counts and file sizes; the paired
comparison above supplies the sorted-corpus equality evidence.

The updated GPU arithmetic suite passed 3,120 Frobenius vectors, 2,526 raw
reductions, 18,194 single-product cases, 18,194 paired cases and 1,157 squares.
Its compiled reducer-mode marker was checked separately from the benchmark
binary's marker. Full client replay, resume, accounting and guard checks passed
before timing. The existing timer includes the final pending reseed; initial
setup and CPU reference replay remain outside the measured interval.

The native raw-artifact SHA256 is
`7e92042b9185f76b3c8fea9d1c3b8f593efcc579739263631a4b9e9c2a0590ac`.
Its source digest is
`fbd4cb0eaf0b15d820909de14e3a6726109660a544c1537164e853bd5d1b62c4`
and binary digest is
`0be5a14572f08f72f153956f8a0e95c8432962c8410606bc44e5834b8de3e36d`.
The [source manifest](benchmarks/direct-reduction/native-source-manifest.json)
also binds the audit entry point separately and identifies the arithmetic files
matched against the controlled comparison. Wrapper and regression-test changes
are included in the native source digest. Final result documentation and audit
artifacts are added after measurement; they do not change the measured code.

The preset enables the new reducer. General Make and environment defaults
remain zero, preserving explicit selection of the previous implementation.
These measurements establish roughly 6.9 billion complete updates/s on the
specified GPU, not the 60 billion target.
