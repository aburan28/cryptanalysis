# Reusable row scratch preserves certificates and reduces F4 phase time locally

The scratch-buffer candidate completed all five hard 12-variable
point-decomposition queries in optimized and UBSan builds (10/10). Its
serialized proof SHA-256, final reduced basis, assignment, producer work,
checker work, original equations, and curve replay match the `round116`
initial-batch baseline. Exact certificates at 21, 32, and 64 variables also
passed, and a modified proof output was rejected for each control.

| Frozen query | Local paired median complete-query scratch/batch | Local paired median native-F4 scratch/batch | Complete-query ratio range |
| --- | ---: | ---: | ---: |
| `pdp-12-seed-1` | 0.970 | 0.940 | 0.926–0.992 |
| `pdp-12-seed-2` | 0.968 | 0.898 | 0.916–1.012 |
| `pdp-12-seed-3` | 0.999 | 0.946 | 0.966–1.118 |
| `pdp-12-seed-4` | 1.028 | 0.931 | 0.887–1.055 |
| `pdp-12-seed-5` | 1.023 | 0.951 | 0.900–1.086 |

One warmup and five alternating AB/BA pairs ran per query, retaining all 60
executions. The complete-query interval begins with fresh target coefficient
descent and ends after independent proof, equation, and curve checks and lease
teardown. The `GF(2^31)` field uses modulus `2147483657`, the binary curve has
`b=1`, and each query has three summands with four factor-base coordinates
per summand. Target abscissae and frozen equation digests are in the reference
report. The macOS M4 Pro host was contended; the timing ratios are diagnostics,
not controlled CPU speedups. A qualifying isolated-host panel remains the
wall-time promotion gate.

The exact trace parity makes scratch reuse a plausible kernel improvement.
Its local native-F4 median improved in all five cells, while the full-query
effect is smaller and mixed. The next candidate can avoid vector term sorting
and symmetric-difference construction for at most 12 active variables by
performing normalization in a compact bitset, preserving the same reducer
choice and proof derivation.

The byte-verified [evidence archive](results.tar.gz) retains 251 logical
files, including every panel and paired-profile execution, build receipts,
source snapshots, large-variable controls, and the independently audited
reference. Its SHA-256 is
`53fdf9657d44f9fffe38f49a3dd9b00360fcd8dabbda895803e0ac513205a0ea`.
The frozen experiment commit is `94844401143450438e425f460a455b369a5f425f`.
