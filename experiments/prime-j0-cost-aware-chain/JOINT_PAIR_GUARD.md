# Certified center guard for Eisenstein pair recoding

The five-neighbor recoder is globally optimal in L1 on the two exact
study lattices. This candidate accepts the rounded center without
search when two strict coordinate inequalities prove that the center
beats all four axial neighbors. All other scalars use the unchanged
five-neighbor search.

Let the rounded residual be `R=(x,y)`, with basis vectors
`b1=(a,b)` and `b2=(c,d)`. Here `|b|>|a|` and `|c|>|d|`. For either
sign of `b1`, the triangle inequality gives

`||R ± b1||₁ ≥ |x|−|a|+|b|−|y| > ||R||₁`

when `2|y| < |b|−|a|`. Similarly, both signs of `b2` lose when
`2|x| < |c|−|d|`. The [five-neighbor certificate](JOINT_PAIR_FIVE.md)
excludes all other lattice translations. Strict inequalities preserve
the earlier recoder's tie order.

| Curve | Horizontal threshold | Vertical threshold | Guard accepted in 16,384 training scalars |
| --- | ---: | ---: | ---: |
| `glv-j0-32` | 3,275 | 952 | 2,147 |
| `j0-56` | 231,499,057 | 231,359,000 | 16,362 |

The [frozen design](joint-pair-guard-design.json) records the exact
bases, thresholds, parent certificate, and training fixture hashes.
The acceptance counts are algorithmic diagnostics, not runtime
measurements. The new candidate will be checked on scalars disjoint
from seventeen earlier fixtures, against its matching five-neighbor
serial or wavefront control. A controlled CPU wall-time claim requires
a host-level isolation receipt.
