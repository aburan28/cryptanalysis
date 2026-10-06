# Direct radix-27 shortest-path τ recoding

The [six-step quotient atlas](TAU3_QUOTIENT_ATLAS.md) reproduces the frozen
width-three digit stream from 6,561 coefficient residue states. The [sparse
hot-pair table](TAU3_SPARSE_HOT.md) then pays one mixed addition for a
prepared orbit pair and two for a cold pair. This proposal chooses block
actions by their **actual cost in that sparse table**.

In the Eisenstein coefficient basis used by the native code, `τ⁶ = −27`.
For state `z = a+bτ`, a valid six-step action represents a correction
`C = c+dτ`. It can be used whenever `c ≡ a (mod 27)` and
`d ≡ b (mod 27)`, with exact successor `(C−z)/27`. Enumerating the frozen
343 orbit representatives under all six units, with the existing three-step
spacing rule, gives 2,053 distinct valid actions. The 729 coefficient
residue classes have 397, 222, and 110 classes with respectively one,
three, and nine candidate actions. Every class has at least one action.

For block `i` and current coefficient state `z`, define `D(i,z)` as the
minimum sum of mixed additions needed to reach zero within the prepared
block limit. Its recurrence is:

`D(i,z) = min_{C ≡ z (mod 27)} (charge_i(C) + D(i+1,(C−z)/27))`.

The charge is zero for the identity action, one for a single-digit or
prepared hot pair, and two for a cold pair. The terminal state costs zero;
nonzero state after the last prepared block is infeasible. Ties use smaller
correction coefficient `L1`, action code, then signed coefficients. This
finite shortest-path computation is exact for the declared action alphabet,
point table, and block bound. Every selected path reconstructs the input
coefficient pair because `z_i = C_i − 27 z_{i+1}`. The resulting scalar is
still congruent to the original scalar modulo the subgroup order.

The [Python screen](screen_tau3_radix27.py) is a **retrospective** feasibility
test on the older compact-pos fixture, which also contributed to sparse
hot-map training. It replays each selected correction and compares its
charged additions with the native sparse receipt. Its result cannot serve
as a prospective speedup measurement. A native evaluator must first prove
exact outputs, fallback behavior, and bounded memory and recoding work.
Then freeze a new disjoint scalar fixture before prospective comparison.

This design makes no academic novelty or CPU speedup claim. Related
endomorphism recodings and shortest-path digit selection require a separate
prior-art review. Dynamic programming spends target-scalar-dependent CPU
work and memory; a group-operation saving alone does not establish a
faster scalar multiplication. The current browser session returned an
expired-token error, so no new literature claim is made here.

## Retrospective feasibility result

The [frozen screen receipt](tau3-radix27-screen.json) was replayed by the
[read-only audit](audit_tau3_radix27_screen.py). All 32,768 coefficient paths
terminated within the existing prepared block limits, reconstructed their
inputs exactly, and had zero modeled fallbacks. The shortest-path search
found fewer charged additions than the native sparse action stream in all
eight old point cases:

| Curve, four old point cases | Compact native additions | Sparse native additions | Radix-27 optimum | Saving vs sparse |
| --- | ---: | ---: | ---: | ---: |
| glv-j0-32 | 62,323 | 53,425 | 52,451 | 1.82% |
| j0-56 | 134,062 | 120,896 | 113,144 | 6.41% |

These are **retrospective operation counts**, including data used to train
the hot pairs; the optimum is computed by Python rather than native point
multiplication. The search cache ended with 41,468 states on the smaller
curve and 254,295 states on the larger curve across four point cases. That
shared exploratory cache is not a native online memory measurement. A
bounded per-scalar native solver and a new disjoint fixture are still needed
before evaluating speed or prospective operation savings.
