# Result: ONB Frobenius byte tables

The accepted source is SHA-256
`c8a39e9a28df54138d094e649f5bf5db1ac5390bbfe23fc28d9620a5fbbeb8c7`.
It changes only the Python ONB Frobenius permutation. The input mask retains
the original treatment of high and negative bits, and the original
normalization remains at the end. Tables are allocated lazily only for the
two exponent residues corresponding to 1 and 2; other exponents use the
original loop. The cache therefore holds at most two tables per field object.

| Measured warm stage | Paired run A | Paired run B |
| --- | ---: | ---: |
| `Onb.frob`, degree 5, exponents 1 / 2 | 1.72× / 1.82× | 1.60× / 1.74× |
| `Onb.frob`, degree 9, exponents 1 / 2 | 2.51× / 2.55× | 2.53× / 2.51× |
| `Onb.frob`, degree 131, exponents 1 / 2 | 9.42× / 8.18× | 8.92× / 13.40× |
| `Curve.halfTrace`, degree 131 | 10.42× | 9.71× |
| `Curve.frob`, degree 131 | 6.85× | 6.21× |
| `Curve.pointFromX`, degree 131, 48 inputs | 3.44× | 2.62× |

`benchmark.py` used 9 alternating paired rounds per run and 64 identical
seeded inputs per field size. `point_recovery_portable.py` used 7 alternating
paired rounds, 48 seeded inputs, 25 recovered points, and the same Euclid
inverse algorithm on both sides. These are wall-time stage diagnostics on
the local Apple Silicon CPU. Variation across paired runs is visible in the
raw JSON. No Metal kernel is used by this Python ONB path.

The first degree-131 Frobenius call at each of exponents 1 and 2 had a median
cost of about **0.63 ms** on the candidate versus **0.02 ms** on the original
in fresh processes. For the two tables, peak Python allocation under
`tracemalloc` was 924,478 bytes versus 1,800 bytes for the original. Cold
table construction is charged to setup in any complete IC comparison.

`verify.py` matched **53,368** original Frobenius outputs, including exhaustive
degree-5 bit patterns, random degree-9/131 patterns, negative inputs, high
bits, and exponents including negative values. Algebraic squaring and
periodicity checks passed. Five local IC tests passed with the candidate loaded
first, including wide inverse/trace, subgroup/Frobenius coefficients, and
matrix recovery. Five other local IC tests require `pysat` / CryptoMiniSat and could not run
here because that module is absent. The independent portable point-recovery
script checks exact curve outputs without that dependency.

Held candidates are recorded. A set-bit permutation cache (v1) missed the
wide-field gate. Combining that cache for small fields with byte tables for
wide fields (v2) had one degree-9 control below the 0.95× floor. Restoring the
old small-field loop (v3) regressed all small controls. The v4 all-exponent
table cache cleared stage gates but could grow across uncommon exponents. The
accepted v5 bounds the table cache to the two hot exponent residues and clears
the same frozen stage gates.

These measurements do **not** establish complete index-calculus or DLP
speedup. The local full runner is separate from Sage, its SAT dependency is
missing in this environment, and its logical operation counts lack a
calibrated common unit. No recovered logarithm or end-to-end operation ratio
is claimed from this experiment.
