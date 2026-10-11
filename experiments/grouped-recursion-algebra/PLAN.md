# Grouped recursion and colour-register-inspired cryptanalysis experiments

Upstream: https://github.com/danadran01/exact-dft-power-saving
Companion: https://github.com/aburan28/crypto-autoresearcher/pull/2063

Status: experiment specification only; no performance claim.

## Target implementations
- C11 index calculus and Rust attack-suite polynomial operations: locate existing multiplication and elimination paths before changing code.
- Add baseline-preserving optional batch scheduling for independent polynomial products.
- Add optional structural common-subexpression interning for repeated sparse polynomial intermediates and Macaulay matrix construction.
- Evaluate exact convolution only when field/modulus and transform-length constraints permit; retain naive/Karatsuba fallback.
- Connect to F4/F5 relation solver paths behind disabled-by-default flags; preserve all original verification checks.

## Paired experiment matrix
Run identical seeded workloads on binary m=31,51,53,83 and representative prime-field inputs. Record compiler, CPU, NUMA, memory, source commit, and timeouts. Compare exact polynomial outputs and independently verify every resulting relation. Measure kernel speed, matrix assembly, elimination, total solver time, peak RSS, duplicates, failed searches, and independent rank.

Primary metric: total elapsed time / newly independent verified relations (including preprocessing, misses and verification). Require >=2x improvement versus fastest valid baseline at larger factor bases before claiming a breakthrough. Keep negative results. Stop any arm on a correctness mismatch; avoid cloud spending until microbenchmarks justify it.

## Next tasks
Locate actual entry points, implement differential-testable kernels, run paired benchmarks, publish immutable run receipts, request independent validator review.
