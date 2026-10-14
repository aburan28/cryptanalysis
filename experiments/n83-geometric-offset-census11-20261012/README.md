# Exact one-coordinate shift optimum for the N83 width-11 base

The shifted base already used by Q66 and Q67 is the **largest factor base
among every one-coordinate affine shift of the same width-11 subspace**.
Its shift is ONB coordinate 81 (the basis element named `gamma_82` in the
earlier frontier), with **1,096 signed-Frobenius columns** and **181,936
distinct nonidentity subgroup points before folding**. The next largest
tested shift has 1,066 columns. This is an exact geometry result for the
declared 73 distinct subspaces; it holds the width, curve, cofactor
projection, and orbit rule fixed.

| Affine x-domain | Shift bit | Usable lifts | Duplicate orbit seeds | `K` | Actual `B=166K` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Winning shifted width 11 | 81 | 1,097 | 1 | **1,096** | **181,936** |
| Next largest shift | 26 | 1,066 | 0 | 1,066 | 176,956 |
| Unshifted width 11 | within `W11` | 1,016 | 0 | 1,016 | 168,656 |

The [protocol](protocol.json) exhausts the unshifted subspace and every
one-coordinate offset outside it, bits 11 through 82. Bits 0 through 10
lie inside `W11`, so their affine translations reproduce the unshifted set.
The conditional XOR translation fact is checked by
[Width11Coset.lean](Width11Coset.lean); its [axiom audit](lean-build.txt)
lists only Lean's standard `propext` and `Quot.sound`. The bridge from the
11-bit vectors to the specified ONB subspace is described by the frozen
field representation and is not formalized here.

The independent lift census also certifies the maximum without relying on
the primary orbit count for each losing shift: every other subspace has at
most 1,066 usable lifts, and its folded-column count cannot exceed its
usable-lift count. The winner's 1,096 exact keys are independently replayed.

The [census](census.json) records every raw lift, cofactor projection,
duplicate-orbit count, exact `K`, `B`, and exploratory scan time. It writes
the winner's sorted [canonical key file](best_keys.bin) and checks the
previous width-frontier receipt for shift 81. The exact six-subset
uniform-target first moment on the winning base is
`C(181936,6)/r = 20831.181431121218...`. This combinatorial quantity does
not supply measured ordinary-query relation yield or novel matrix rank.
The 73 local scans took 200.329 seconds in sum; these are geometry costs,
not target-dependent online timing.

[Independent Sage replay](independent_sage_replay.json) uses the separate
polynomial-field model to check the Artin–Schreier lift condition for all
73 subspaces, then recomputes every winner projection, subgroup membership,
signed-Frobenius key, and exact key-file byte. The checked Sage launcher
saved [runtime identity](sage_runtime_info.json) before work. Raw successful
[producer](run.stdout.txt) and [verifier](verify_sage.stdout.txt) progress
remain available; the preflight failure and deliberately cancelled run
were retained separately.

Run the read-only receipt audit from the repository root:

```sh
python3 experiments/n83-geometric-offset-census11-20261012/verify.py
```

This result rules out one-coordinate shifting as a way to enlarge the
current width-11 base at fixed circuit width. A larger search family would
need a separately frozen optimization and an ordinary-target decomposition
test; the exact geometry alone does not select the best complete IC
candidate.
