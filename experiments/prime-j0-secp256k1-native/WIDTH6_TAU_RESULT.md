# Minimum-norm width-six tau atlas

A fixed-generator `tau^6` digit atlas reduces the secp256k1 source
point-formula count to **135,392 field-product units on 128 frozen holdout
scalars**, from 146,400 for the two-orbit depth-two `tau^4` policy on the
same representatives. The saving is 11,008 units (7.52%); each holdout
scalar improves under this formula count. On the existing 86-scalar fixture,
the atlas uses 73,424 units versus 79,506 (7.65%). The atlas has 81 signed
unit orbits, versus 18 for the `tau^4` policy, so fixed-base table
preparation, lookup, and integer recoding must be included in the next
complete-operation comparison.

## Digit construction and termination

In the `(1,tau)` basis, `tau^6 = -27`. Two integers are congruent modulo
`tau^6` exactly when both coefficients agree modulo 27. Divisibility by
`tau` is `a = 0 (mod 3)`, leaving 486 usable residue classes. The screen
chooses a minimum Eisenstein-norm digit for each class, then uses a
deterministic norm/coordinate order to select one seed per signed unit
orbit. There are 81 such orbits.
Its maximum digit norm is 217.

The construction enumerates coefficients in `[-35,35]^2`. Since
`N(a,b) >= a^2/4` and `N(a,b) >= 3b^2/4`, every possible digit of norm
at most 217 lies inside that square. The observed representative for each
class is therefore globally minimum norm. The result JSON records all 81
orbit seeds and each scalar's recoding counts.

For a nonterminal state `z`, the six-step quotient is
`q = -(z-d)/27`. Its norm satisfies
`N(q) <= (sqrt(N(z)) + sqrt(217))^2 / 729 < N(z)` for every
integer norm `N(z) > 1`. Unit-norm states are terminal. Zero-digit steps
divide the norm by three. Thus the recoder terminates for every input.
The screen checks the residue, strict norm descent, and reconstruction
for every visited state.

## Paired operation counts

Each `tau` step costs five source field-product units and each mixed digit
addition costs eleven. The width-six result is:

| Panel | Scalars | `tau` steps | Mixed additions | Width-six proxy | Two-orbit `tau^4` proxy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen edge cases | 22 | 886 | 128 | 5,838 | 6,212 |
| Frozen random design | 64 | 10,116 | 1,546 | 67,586 | 73,294 |
| Frozen random holdout | 128 | 20,243 | 3,107 | 135,392 | 146,400 |

The 128 holdout cases each improve under this formula count. One edge
case has a higher width-six count; every outcome remains in the saved
per-case JSON. The proxy excludes point-table construction, integer
recoding, memory traffic, and affine output conversion. It supports a
point-formula comparison, with complete CPU performance pending a passing
isolation receipt.

The same screen also evaluates a sparse overlay: use a six-step block only
when its minimum-norm digit belongs to one of the existing 18 `tau^4`
orbits, and otherwise use depth-two `tau^4` rollout. It needs no additional
digit-point orbits. Its holdout total is 146,151 units, a 249-unit
(0.17%) reduction from the `tau^4` reference, with 50 lower, 40 equal,
and 38 higher per-case costs. This is a table-budget candidate for native
evaluation, especially if six-step blocks reduce integer rollout work.

## Reproduction and next implementation

```sh
cd experiments/prime-j0-secp256k1-native
PYTHONDONTWRITEBYTECODE=1 python3 width6_tau_screen.py \
  --output /absolute/path/to/new-width6-result.json
```

The script refuses to overwrite a result. The checked-in result SHA-256 is
`7f81556cd0a4f72e6504894ebac8bf591616f200a37778f2b63cc4e899d9e58c`;
the script SHA-256 is
`6e00c83fb627e9116499b69916264eb350b0328eb33351d41b27b18e9ab9ca4c`.
The input is the 214-case verified scalar panel in
[`redundant-tau4-result.json`](redundant-tau4-result.json).

The next step is a native fixed-base width-six path with the same frozen
digit seeds, independent point verification, and separate cold table cost.
Paired full-operation timing then belongs on a host satisfying
[`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md).
Width-`w` nonadjacent digit systems are established prior work; the
implementation and table-budget tradeoff here need a specific priority
comparison before an academic novelty claim.
