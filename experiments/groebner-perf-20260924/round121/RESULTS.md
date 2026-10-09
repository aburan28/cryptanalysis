# Exact field-pair obstruction removes rejected-seed verification work

The bounded Boolean field-pair probe found an exact nonzero normal form in
each of the five frozen 12-variable matrix seeds. Each query then kept that
seed for native F4 continuation and independently verified the completed
basis, original equations, and curve point. The optimized and UBSan panel
passed 10/10, and 30 paired warmup/measured queries matched the round119
bitset baseline in final serialized proof SHA-256, basis, assignment, and
producer work. The separate set-based oracle passed 203 small Boolean bases;
the round119 wider-support proof controls passed at 21, 32, and 64 variables,
including rejection of corrupted certificates.

The probe returns a seed-rejection witness, never a final acceptance result.
Its first irreducible field-pair term is sufficient to show the candidate
seed is not a Groebner basis in the Boolean quotient. If it finds no witness,
reaches a cap, sees an invalid view, or sees more than 12 variables, the
existing independent checker runs with the remaining shared work budget.
The final basis always goes through the independent checker.

| Frozen query | Seed-check work, bitset | Seed-check work, guard | Median complete-query guard/bitset | Range of five paired query ratios |
| --- | ---: | ---: | ---: | ---: |
| `pdp-12-seed-1` | 453,519 | 12,553 | 1.057 | 0.805–1.577 |
| `pdp-12-seed-2` | 488,091 | 13,143 | 0.288 | 0.128–2.986 |
| `pdp-12-seed-3` | 396,636 | 6,877 | 0.736 | 0.172–1.666 |
| `pdp-12-seed-4` | 481,126 | 9,152 | 1.098 | 0.238–3.266 |
| `pdp-12-seed-5` | 521,673 | 11,128 | 0.894 | 0.304–1.844 |

The seed-check work counts are identical across the five measured repetitions
of each case. One warmup and five alternating AB/BA pairs per case retained
all 60 executions. The complete-query interval starts with target-dependent
coefficient borrowing and ends after independent proof, original-equation,
and curve replay. The input is the frozen `GF(2^31)` point-decomposition panel
with irreducible modulus `2147483657`, binary-curve coefficient `b=1`, three
summands, and four factor-base coordinates per summand. The target abscissae,
equation digests, binary hashes, proof bytes, phase intervals, raw failures,
and the interrupted intermediate profile are in the [lossless evidence
archive](results.tar.gz). Its SHA-256 is
`c9478468d0645a14492e421d2421a50fdbaab38fe3a6fe92a546b6fb366b140d`.
The frozen executable-source commit is `eb3a1fb9ffb9d25a7eac0c5611a6d1823ef69403`.

The complete-query ratios vary sharply on this contended macOS M4 Pro host;
they are exploratory diagnostics. The experiment therefore remains opt-in.
The next decision gate is matched complete-query replay on a physical Linux
host that passes the repository's strict CPU-isolation preflight. The round120
manifest and worker establish that measurement boundary for the bitset versus
scratch comparison; a guarded-arm manifest needs the lower expected checker
work recorded separately from the bitset arm.
