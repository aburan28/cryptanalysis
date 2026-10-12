# Radix-569 bounded top-ball scalar format

Thirteen radix-569 unit-orbit windows and one bounded terminal table
cover the complete secp256k1 scalar range with **756,033 affine point
entries**, or **48,386,112 point bytes** at 64 per entry. An exact census
of integer radices 500 through 700 finds radix 569 to have the fewest
entries under this thirteen-window bound. Lean checks the universal
digit bound, terminal bound, scalar reconstruction, and congruence;
the finite audit checks all 323,761 residues and 327,235 terminal states.

| Frozen 4,096-scalar design measure | Radix 943 | Radix 671 split-top | Radix 569 top-ball |
| --- | ---: | ---: | ---: |
| Affine point entries | 1,926,717 | 1,044,625 | **756,033** |
| Affine point payload bytes | 123,309,888 | 66,856,000 | **48,386,112** |
| Selected terms | 53,248 | 57,343 | 57,344 |
| Pareto-tree gauge rotations | 9,027 | 9,588 | 10,106 |
| Modeled ordinary-path products | 484,163 | 525,674 | 526,202 |

The radix-569 format saves 18,469,888 point bytes relative to split-top
and adds 528 modeled products over the 4,096 paired scalars. The table's
**complete retained size is 49,929,614 bytes** on the local ARM64 native
build, including the residue atlas, terminal rank prefix, constants, and
Pareto plan. That is 19,056,474 bytes below the recorded native split-top
build's 68,986,088 bytes. Both builds use 64-byte affine points.

The design and theorem sources were frozen in commit `b70c45a3c`, and the
holdout generator and replay source in `3b98eb99e`, before drawing 512
distinct scalars with seed `20261012569`. The input check establishes
disjointness from the listed prior scalar panels. Every final public point
matched an independently generated secp256k1 fixture after each selected
point was accumulated with a separate affine group law. The opt-in native
Rust evaluator matched all 512 points and the frozen point digest
`3ca5e70f667be7dd58de125f7902c8f046847deaf9b98aff3ac99c0c51212274`.

| Disjoint 512-scalar holdout measure | Radix 943 | Radix 569 top-ball |
| --- | ---: | ---: |
| Selected terms | 6,656 | 7,168 |
| Modeled ordinary-path products | 60,519 | 65,760 |
| Gauge rotations | 1,127 | 1,248 |
| Public points verified by independent and native replay | — | **512 / 512** |

The [native result](NATIVE_RESULT.md) retains the build, table, and
per-case replay evidence. CPU wall-time ranking still requires a paired
complete-operation run on a host that passes the isolation preflight.
