# Held-out neighbor-search frontier

Source, tests, protocol, and checker were frozen in `a83a83d4`.
Independent affine fixtures were frozen in `a84da833` before either
panel ran. Release and UBSan both passed the serial ten-arm gate on
each curve. Every one of the 40 raw trials, including its exit status,
stdout, stderr, source and binary hashes, and verification digest, is
retained in `panel-release.json` or `panel-ubsan.json`. The counters
agree exactly between builds. Release passed all 16 CTest tests;
UBSan `joint_tau` passed.

| Curve; 1,024 pairs | Scored neighbors | τ steps | Mixed adds | Rotations | Recodes | Weighted score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 2 | 13,494 | 7,592 | 1,348 | 4,084 | 165,824 |
| `glv-j0-32` | 3 | 13,352 | 7,502 | 1,294 | 6,126 | 163,928 |
| `glv-j0-32` | 4 | 13,313 | 7,456 | 1,251 | 8,168 | 163,145 |
| `glv-j0-32` | 5 | 13,309 | 7,421 | 1,221 | 10,210 | 162,706 |
| `j0-56` | 2 | 33,641 | 16,184 | 1,786 | 4,084 | 381,656 |
| `j0-56` | 3 | 33,520 | 16,021 | 1,739 | 6,126 | 379,090 |
| `j0-56` | 4 | 33,534 | 15,978 | 1,700 | 8,168 | 378,662 |
| `j0-56` | 5 | 33,507 | 15,892 | 1,644 | 10,210 | 377,498 |

The frozen weighted score is `6 * tau_steps + 11 * mixed_adds +
rotations`; its weights are heuristic and omit recoding work. On
`glv-j0-32`, three neighbors capture 61% of the five-neighbor score
gain over two while requiring one-third as many *extra* recodings.
Four capture 86% with two-thirds of the extra recodings. On `j0-56`,
the corresponding gain fractions are 62% and 72%. This establishes a
source-level tradeoff, not a faster implementation.

The local Release median `online_ms` across two repeats for scored
2/3/4/5 was respectively `0.968/1.123/1.341/1.486` on
`glv-j0-32` and `1.952/2.343/2.622/2.907` on `j0-56`. The host
lacked verified exclusive CPUs, NUMA isolation, fixed frequency, and
noise gates. Both panels therefore retain `cpu_speedup_claim: null`
and `isolation_receipt: null`. These batch-stage timings are
exploratory and cannot answer the one-target online speed question.

The separate `suffix-analysis.json` reproduces the older-fixture
atlas-state screen. Of 43,524 five-neighbor atlas states on
`glv-j0-32`, only 95 repeat within the same scalar (0.22% maximum
reuse). On `j0-56`, 80 of 93,565 repeat (0.086%). A perfect cache
could avoid at most those counts before its own lookup overhead.
The evidence does not support implementing shared suffix memoization
for this neighborhood.

The next useful design step is to reduce or predict recoding cost
before expanding the neighbor set, or change the point-operation
format enough that the lower point-work count outweighs search cost.
Any CPU claim still requires a verified one-target comparison under
the isolated benchmark contract. Academic novelty remains unproved.
