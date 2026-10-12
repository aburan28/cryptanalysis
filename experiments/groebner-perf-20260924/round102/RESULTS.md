# Independent bitset proof-value results

The frozen complete-query panel supports continuing this opt-in path. The matrix
producer's large derivation proofs are much less expensive to verify with bounded
bitsets on the tested small Boolean rings. The default implementation is unchanged.

These are CPU-only local diagnostics on an unisolated macOS ARM64 host. There is no
qualified CPU speedup, GPU gain, complete IC/rho comparison, world-fastest claim,
or asymptotic F6 result. The thirteen inputs are small algebra/PDP controls; this
panel is not a repetition of the earlier eighteen-variable Python-verifier query.

| Frozen case | F4 / hash query ms | F4 / bitsets query ms | Matrix / hash query ms | Matrix / bitsets query ms |
|---|---:|---:|---:|---:|
| PDP6 seed 1 | 4.443 ± 0.054 | 4.169 ± 0.132 | 3.654 ± 0.079 | 3.122 ± 0.159 |
| PDP6 seed 3 | 4.068 ± 0.095 | 3.762 ± 0.055 | 4.026 ± 0.273 | 3.647 ± 0.216 |
| PDP9 seed 4 | 82.716 ± 0.669 | 60.627 ± 0.420 | 271.280 ± 1.750 | 23.066 ± 0.118 |
| Dense MQ12 | inconclusive | inconclusive | 516.217 ± 6.060 | 26.736 ± 0.457 |

Entries are medians ± median absolute deviations of four observations, following
one warmup. The four arms rotate in a preset order. Each observation uses a fresh
process; setup and artifact serialization are separate. Complete-query time
includes coefficient descent, native production and checking, proof materialization,
root extraction, independent equations/curve replay where applicable, and teardown.
The MQ row reports a complete basis rather than a point decomposition.

Both matrix variants certify all five PDP9 instances and the MQ12 control. F4
certifies one of five PDP9 instances at the frozen producer limit. All five PDP12
cases remain inconclusive under every arm. Failed attempts and F4 fallbacks remain
charged and recorded. An inconclusive F4 stop is not a competing solve time.

On PDP9 seed 4, matrix checking changes from 253.969 ms to 5.509 ms; matrix
production remains about 4 ms. The F4 checker changes from 28.137 ms to 7.166 ms,
while F4 production remains about 47 ms. On MQ12, matrix checking changes from
494.496 ms to 4.928 ms. Bitset checking uses more conservative charged work because
word operations and conversions are charged in addition to the reference term
counts; these counters are not comparable machine-instruction speed ratios.

Budgeted dense proof storage peaks at 1,447,652 bytes for PDP9 seed 4 and
2,866,004 bytes for MQ12, including reserved value metadata and use counters.
All final dense proof values are released. This counter excludes the unchanged
input/basis sets, allocator bookkeeping, and process setup; raw peak RSS is retained.

Validation passed with sixteen freshly built native libraries: optimized and
UBSan versions of eight components. Six unit-test groups cover independent Python
replay, random ideals, Boolean cancellation, shared operands, malformed proofs,
work and memory boundaries, equation limbs, and the sparse fallback through 64
variables. The 104 control queries have 44 exact algebra certificates, 40 verified
PDPs, 60 inconclusive outcomes, and no process failures. Hash/bitset producer traces,
proofs, bases, and verified assignments match. The native-free audit checks exact
Boolean completion and zeros, proof liveness, dense work, memory, and all budgets.

The diagnostic panel retains 260 rows (52 warmups and 208 observations), 110
algebra certificates, 100 verified PDPs, and 150 inconclusive rows. Thirty-four
altered-artifact cases are rejected, as are fifteen synthetic CI-admission
corruptions. Synthetic admission controls do not constitute actual CI evidence.

The original numerical source is `0a18dfaa4a3339f1905890c7edc008f355f75169`.
A subsequent clang-format-only repair is
`9b9630cdd3ed4d9cb1e64d1e826b9027e5917f4b`. Fresh correctness validation at the
formatted source reproduces all 104 complete control traces. Generated C++ agrees
when whitespace is removed; compiler/commands agree, but native binary hashes
differ and both builds are retained. The timing panel was not repeated or selected
based on its results.

The next decision is to isolate complete-query measurement and profile the
remaining Python transport/proof-materialization cost. Preserve the independently
checked certificate and owned result lifetime while testing a compact binary proof
copy. Larger Boolean rings still require sparse/adaptive storage; dense coefficient
space grows exponentially and is deliberately capped at twelve variables here.
