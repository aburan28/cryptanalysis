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
full retained size also includes the residue atlas, terminal rank prefix,
constants, and Pareto plan; the native build must measure that footprint.
The independent scalar and point holdout follows the frozen protocol.
