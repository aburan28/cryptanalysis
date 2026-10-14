# Exact shifted N83 factor-base geometry at widths 17 and 18

The complete shifted width-18 base has **21,714,958 distinct usable
subgroup points before folding**, represented by **130,813
signed-Frobenius columns**. Width 17 has 10,860,384 usable points and
65,424 columns. Every seed and resulting canonical orbit key was
independently replayed through Sage's polynomial field and curve model;
[the replay receipt](independent_sage_replay.json) is `PASS` for both widths.

The field is GF(2^83), the curve is `y² + xy = x³ + 1`, and the subgroup
order is 2,417,851,639,230,796,216,685,689. For each dimension `d`,
the raw x seeds are `gamma_82 + span(gamma_1,...,gamma_d)`. Every lift is
multiplied by cofactor four, identity is dropped, and the resulting set
is closed under sign and all 83 Frobenius powers. The exact key files and
counts are frozen in [frontier.json](frontier.json); the source and input
rules are in [protocol.json](protocol.json).

| Width | Valid x lifts | Folded columns K | Actual usable points B | Five-subset first moment | Full pair-root plus cached XY payload |
| --- | ---: | ---: | ---: | ---: | ---: |
| 16, prior | 32,652 | 32,648 | 5,419,568 | 16,114,307.7 | 8.49 TB |
| 17 | 65,428 | 65,424 | 10,860,384 | 520,732,413.4 | 34.11 TB |
| 18 | 130,817 | 130,813 | 21,714,958 | 16,641,170,632.3 | 136.35 TB |

The first moments are `binom(B,5)/r`, a combinatorial count under a
uniform-sum model. They are not measured ordinary relation yield. The
full pair-root allocation law is `83 K²` states with 96 bytes per state
for the compact root record and cached coordinates. Both wider full
indexes exceed the declared 8 GiB memory cap; a compressed or partial
index would need a separate design and measurement. The width-18
Karatsuba SAT stage in the neighboring experiment uses only the key and
canonical-x caches, whose sizes are recorded separately.

The checked repository Sage launcher produced the
[runtime receipt](sage_runtime_info.json). The exact enumeration took
20.10 seconds for width 17 and 43.58 seconds for width 18 on the local
exploratory host. Independent Sage replay checked every seed, lift,
cofactor projection, orbit key, and exact key-file payload. These are
geometry and correctness measurements; relation rank and online
target cost remain separate stage questions.

Use a fresh output directory to reproduce the immutable producers:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-width17-18-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-width17-18-20261012/verify_sage.py
```
