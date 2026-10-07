# Bounded four-column elimination with derivation witnesses

This opt-in CPU experiment targets forward elimination in the existing Boolean
Macaulay producer. Round107's five 12-variable controls reach the 20-million
matrix-work cap before completing forward elimination. The experiment keeps the
same 13 inputs, multiplier degree, budgets, checker and fallback policy.

A complete group of four consecutive pivot columns gets a table of its 15
nonzero row combinations. The four column bits select one combination, clearing
up to four scalar reductions with one tail XOR. A unit upper-triangular pivot
submatrix makes the signature lookup bijective. Every combination retains an
XOR derivation from immutable forward pivots. Tables are query-local and released
before backward substitution. Incomplete groups and exhausted table memory use
scalar elimination; all attempted table work remains charged.

This is an adaptation of established M4RI-style combination tables, not a new
F6 algorithm or an asymptotic Gröbner-basis claim. See the
[M4RI table documentation](https://malb.bitbucket.io/m4ri/brilliantrussian_8h.html)
and Albrecht, Bard and Pernet,
[Efficient Dense Gaussian Elimination over the Finite Field with Two Elements](https://arxiv.org/abs/1111.6549).
This prototype uses binary-subset recurrence rather than Gray-code construction.

The independent coefficient model uses Python integers. It reproduces emitted
proofs and all software budget counters, including failed prefixes. Independent
ideal-membership and Boolean Gröbner-completion checks remain mandatory; row
elimination alone cannot certify a complete basis. A failed or incomplete matrix
gets only the remaining producer and checker budgets for the existing F4 fallback.

Run `python experiments/groebner-perf-20260924/round108/run_validation.py --output OUT`
from a committed checkout. Add `--diagnostics` for the frozen paired local timing
panel. On macOS the runner takes the shared heavy-work lock. Optimized and UBSan
libraries are built locally; CI rebuilds on Linux and macOS. No Sage is involved.

The 4 MiB table cap covers index payload plus coefficient/proof/lookup arrays.
It excludes allocator metadata, vector headers and capacity slack. Row payload,
proof graphs and parity compression have separate bounds; process RSS is reported
separately. `MatrixStats.word_xors` includes table construction and applications;
`forward_xors` counts only row applications. The block record splits construction,
copying, applications and the equivalent scalar pivots. Work counts are declared
software charges, not hardware instructions.

CPU timing remains exploratory without an accepted host-isolation receipt.
Qualified speedup and IC online speedup stay null. These are small planted
correctness controls, not estimates of natural relation yield or complete DLP
recovery. No GPU performance or compatibility claim is made by this experiment.
