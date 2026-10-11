# Exact W16 prefix-cut support gate for target-conditioned search

The audited W16 six-pair source gives an exact point at which a
target-independent prefix policy loses useful coverage. One fixed pair
leaves an optimistic uniform-target support ceiling near 1.6% per prefix.
Fixing **two** complete pairs before using the target lowers the best of
the four structural cuts to at most **4.801×10⁻⁷** per prefix. Even the
best two-pair cut therefore needs **1,041,516 distinct prefixes** before
the union bound can reach one half of uniform subgroup targets. Fixing
the two free pairs instead needs **68,253,607,268 prefixes**. These are
exact counting necessities for fixed target-independent prefix lists, not
success probabilities for the published challenge point or lower bounds
on a target-guided algebraic solver.

The source is the [fully audited W16 width census](../n131_w16_w18_sixpair_width_gate_20261010/RESULT.md)
on `EC1N131Ckb1heb5f1998f20b`, with subgroup order
`r=680564733841876926932320129493409985129`. Each of the two free pair
slots has `N=2,151,089,140` signed, distinct-column source states. Each
same-seed two-pair block has `M=70,608,489,011,888` labeled states,
equal to the sum of squared per-seed pair counts. The largest individual
nonzero seed bucket has `h=33,844` pair states. Cross-slot column
collisions and group-sum collisions can only lower the support ceilings.

For a uniform subgroup target, fixing a prefix translates the remaining
sum set; its membership fraction is at most `remaining_labeled_tuples/r`.
The union of `t` fixed prefixes covers at most
`min(1,t·remaining_labeled_tuples/r)`. The exact [arithmetic receipt](result.json)
applies this bound to every distinct way of fixing one or two complete
pairs. A pair fixed inside a constrained block leaves at most `h` choices
for its same-seed partner.

| Target-independent prefix cut | Remaining tuple ceiling | Prefixes needed before a 1/2 union ceiling | Necessary average in 600 s, approximate |
| --- | ---: | ---: | ---: |
| One free pair | `N M²` | 32 | 0.05333/s |
| One pair in a constrained block | `N² M h` | 31 | 0.05167/s |
| Two free pairs | `M²` | 68,253,607,268 | 113.756 million/s |
| One free, one constrained pair | `N M h` | 66,197,628,760 | 110.329 million/s |
| Two pairs in the same constrained block | `N² M` | **1,041,516** | **1,735.86/s** |
| One pair in each constrained block | `N² h²` | 64,203,581,742 | 107.006 million/s |

The [independent verifier](verify.py) re-enumerated all 32,796 rational
source masks, recomputed the signed seed counts with an integer Walsh
transform, corrected same-column aliases, and reproduced `N`, `M`, `h`,
and every exact half-union threshold. Its [audit](audit.json) binds the
support and result hashes. The [protocol](protocol.json) was frozen before
the arithmetic; this is a zero-target source screen, so no Sage workload,
solver search, relation-yield interval, or candidate run ID belongs to it.

This gate directs the next algorithmic experiment: couple the public target
to partial pair-output families **before choosing a second complete pair**,
or demonstrate a complete two-pair-prefix oracle below the necessary
per-prefix work rate with all costs charged. Test sound family rejection and
an independently replayed relation on the existing N41 W6 public control.
Then project the generator's actual operations and memory to N131 before a
fresh ordinary target query. The complete factor-log and one-target
IC-versus-rho gates remain downstream of a verified N131 decomposition.
