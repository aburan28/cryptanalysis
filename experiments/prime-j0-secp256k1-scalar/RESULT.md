# End-to-end secp256k1 τ scalar correctness

The full scalar prototype and protocol were frozen in `e8aa429b`
before the run. The checked repository Sage launcher returned
`status: verified`, Sage `10.10.rc0`, and accepted runtime manifest
SHA-256 `0a27ddfece04798b893c0feef292caab7f30ce68440f4d18092fe6358ef5499a`.
The saved `runtime-info.json` has SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.

All 32 complete secp256k1 scalar outputs matched Sage's independent
`kP` on four subgroup bases. For each base, the fixed workload included
scalars `0`, `1`, `2`, `n-1`, and four SHA-256-derived scalars. Every
case retained its scalar, short lattice pair, τ-adic digit count,
evaluator operation counts, and verified output coordinates in
`result.json`. The lattice congruence and digit reconstruction also
passed. The largest absolute lattice component was 129 bits, and the
longest expansion was 161 τ digits. The script checked norm-decreasing
recode and exact reconstruction on all 1,681 pairs in the 41×41
small-coefficient grid; its independently derived gauge policy agreed
with the relevant C table entries in 24 checks.

Across this mixed edge-and-random workload, the evaluator counted
2,540 τ steps, 653 fused τ pairs, 448 multiplication-free paired Z
scales, 1,686 mixed digit additions, ten digit rotations, and three
final gauge corrections. These are source-level diagnostics. The run
does not compare against an equally prepared full scalar baseline or
measure isolated CPU time. The result records `cpu_speedup_claim: null`.

This establishes an executable 256-bit path from scalar through lattice
reduction, τ-adic recoding, paired/gauge-carrying evaluation, and exact
point recovery. It is a Python/Sage correctness prototype, with no
native 256-bit implementation, constant-time guarantee, or academic
novelty claim. A paired full-operation comparison is the next gate.
