# Quotient summation on ECC2K-130: what a decomposition may cost, and m = 4 on the Frobenius-stable base

An experiment, not an attack. It answers one narrow question left open by
[`../pdp-scaling`](../pdp-scaling/README.md): that study priced index calculus
on ECC2K-130 with **subspace** factor bases, which at `n = 131` cannot be
Frobenius stable (2 is primitive mod 131, so `F_2[t]/(t^131 - 1)` has no
nontrivial submodule and the only stable subspaces have dimension 0, 1, 130,
131). The one quotient that index calculus can still take on this curve is
the Frobenius-orbit quotient of a **nonlinear** stable base, the weight base

    F_w = { P : 1 <= HW(x(P)) <= w  in a normal basis },

which `ecc2k130/runner/codegen/indexcalc.py` already builds. This directory
asks (1) how much one decomposition may cost on that base if the whole attack
is to tie rho, and (2) what one `m = 4` decomposition actually costs on it.
Nothing here is run against the ECC2K-130 challenge.

## 1. The budget at n = 131 (`budget.py`, arithmetic only)

Rho on the `<-1, tau>` classes is `2^60.81` iterations (`../pdp-scaling`).
Columns are Frobenius orbits, `C = B / 131`, credited in full; relations
needed `C`; sparse linear algebra `m C^2`; one group addition counted as one
rho iteration. Heuristics H1–H3 are stated in the script header. Best weight
`w` per arity `m` (smallest gap to the best known method):

| m | w | log2 B | log2 columns | log2 P(decomp) | log2 attempts | log2 LA | log2 budget/attempt | required exponent in B | MITM exponent | log2 MITM/attempt | MITM gap (bits) |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 2 | — | | | | | | none: LA alone exceeds rho at every w | | 1 | | |
| 3 | 6 | 31.6 | 24.6 | -35.8 | 60.3 | 50.7 | 0.5 | 0.01 | 2 | 65.5 | +65.0 |
| 4 | 6 | 31.6 | 24.6 | -5.1 | 29.7 | 51.1 | 31.1 | 0.98 | 2 | 65.5 | +34.4 |
| 5 | 5 | 27.2 | 20.2 | 0.0 | 20.2 | 42.7 | 40.6 | 1.49 | 3 | 84.6 | +44.0 |
| 6 | 4 | 22.5 | 15.5 | 0.0 | 15.5 | 33.6 | 45.3 | 2.01 | 3 | 70.6 | +25.3 |
| 7 | 3 | 17.5 | 10.5 | -13.7 | 24.2 | 23.8 | 36.6 | 2.09 | 4 | 74.1 | +37.4 |
| 8 | 3 | 17.5 | 10.5 | 0.0 | 10.5 | 24.0 | 50.3 | 2.87 | 4 | 74.1 | +23.7 |
| 9 | 2 | 12.1 | 5.0 | -31.8 | 36.8 | 13.3 | 24.0 | 1.99 | 5 | 65.5 | +41.5 |
| 10 | 2 | 12.1 | 5.0 | -22.0 | 27.1 | 13.4 | 33.8 | 2.79 | 5 | 65.5 | +31.8 |
| 11 | 2 | 12.1 | 5.0 | -12.4 | 17.4 | 13.6 | 43.4 | 3.59 | 6 | 78.5 | +35.1 |
| 12 | 2 | 12.1 | 5.0 | -2.9 | 8.0 | 13.7 | 52.9 | 4.38 | 6 | 78.5 | +25.6 |

Reading it:

1. **The quotient moves the budget, not the obstruction.** Compared with the
   subspace table in `../pdp-scaling` (`m = 4`: `2^12.2`; `m = 5`: `2^32.8`),
   the orbit quotient raises what one decomposition may cost to `2^31.1`
   (`m = 4`) and `2^40.6`–`2^52.9` (`m = 5..12`). That is the factor `131` on
   relations and `131^2` on linear algebra, the same constant rho already
   collects through `sqrt(2 * 131)`.
2. **No generic decomposition fits any row.** A decomposition that uses only
   the group law must find `a in L1`, `b in L2` with `a + b = R`, which needs
   `|L1| |L2| >= #E ~ 2^131`: at least `2^65.5` per attempt, above rho's whole
   run. The MITM column carries that floor. Only a method that uses the
   x-coordinate algebra (summation polynomials, their Weil descent, SAT/Gröbner
   on them) can meet any budget above.
3. **What such a method must achieve is an exponent in B of 0.98 to 4.4,
   against the exponents of every known method.** The "required exponent"
   column is `log2(budget) / log2(B)`. At `m = 4` it is 0.98: one
   decomposition would have to cost less than *listing the factor base once*.
   At `m = 6` and `m = 8` it is 2.0 and 2.9. The known decomposition methods
   sit at `m` (exhaustive, WDSat, FES), `m - 1` (hybrid) and `ceil(m/2)`
   (MITM, and that one is floored at `2^65.5`); `../pdp-scaling` measures SAT
   at about 4 (`m = 3`) and 7 (`m = 4`) bits per unit of `log2 B`.
   The smallest gap between a required exponent and a known one is at
   `m = 12` (4.4 against MITM's 6, which is itself unusable because of the
   floor); the exhaustive (`m`) and hybrid (`m - 1`) exponents are at least
   2.4 times the required one in every row (closest: `m = 8`, 7 against 2.87).

So "no efficient quotient summation solver and no demonstrated work below
`2^61`" is the expected state, and this table says precisely what would change
it: a decomposition algorithm for `S_{m+1}` over `F_w` whose cost grows like
`B^e` with `e` below the required column, i.e. **below `m/2` for every `m`**.
That is the obstruction `../pdp-scaling` names (no bucketing of partial sums
under the group law, the reason Wagner's k-tree does not apply), and the
weight base does not remove it.

## 2. m = 4 on the weight base, measured (`ladder.py`)

`../pdp-scaling` measured `m = 4` on subspace bases only, and
`analysis/frobenius-orbit-ecc2k130` in `crypto-autoresearcher` measured the
orbit-union base at `m = 2` only. This fills the remaining cell: the chained
`S_3` encoding of `decomp.buildSystemPb` (three `S_3` links, two intermediate
abscissae; `S_5` is never formed) with the weight constraint as a cardinality
bound, CryptoMiniSat through python-sat, one thread, a per-instance CPU
budget (censored instances are reported as censored, never as UNSAT).

Two arms per cell, same base and system:

- `planted`: the target is a sum of four base points (satisfiable; the
  correctness control);
- `random`: a uniformly random curve point, what relation collection pays
  for.

Every SAT model is lifted to points and re-added. With `--oracle` every
target is also checked against a brute-force enumeration of all signed
4-sums of the base, and a SAT verdict on an unreachable target stops the
run. At `n = 7` all three random targets were UNSAT and all three are
unreachable by brute force (`results/smoke_n7.json`).

### Results

Generated by `summarize.py` from `results/cell_*.json`:

| n | w | B (x-classes) | log2 B | orbits | arm | sat | unsat | censored | spurious | oracle disagreements | median CPU s (completed) |
|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| 9 | 2 | 27 | 4.75 | 3 | planted | 6 | 0 | 0 | 0 | 0 | 0.46 |
| 9 | 2 | 27 | 4.75 | 3 | random | 6 | 0 | 0 | 0 | 0 | 0.49 |
| 11 | 2 | 44 | 5.46 | 4 | planted | 6 | 0 | 0 | 0 | 0 | 1.63 |
| 11 | 2 | 44 | 5.46 | 4 | random | 6 | 0 | 0 | 0 | 0 | 2.77 |
| 11 | 3 | 77 | 6.27 | 7 | planted | 6 | 0 | 0 | 0 | 0 | 4.39 |
| 11 | 3 | 77 | 6.27 | 7 | random | 6 | 0 | 0 | 0 | 0 | 3.13 |
| 13 | 2 | 39 | 5.29 | 3 | planted | 6 | 0 | 0 | 0 | 0 | 103.44 |
| 13 | 2 | 39 | 5.29 | 3 | random | 6 | 0 | 0 | 0 | 0 | 9.71 |
| 15 | 2 | 45 | 5.49 | 3 | planted | 3 | 0 | 0 | 0 | 0 | 215.65 |
| 15 | 2 | 45 | 5.49 | 3 | random | 1 | 0 | 2 | 0 | 0 | 172.05 |

Slope of log2(median random-arm CPU) on log2 B over 4 uncensored cells: 1.34 (descriptive; cells differ in n as well as B).

What the completed cells show, and do not:

- **Correctness holds.** Every completed instance returned a lifted,
  re-added decomposition, with 0 spurious models and 0 oracle
  disagreements (the oracle runs on every cell).
- **Cost here is driven by n, not by B.** At `n = 13` the base is *smaller*
  than at `n = 11, w = 2` (39 against 44 x-classes), yet a planted solve
  costs 103 s against 1.6 s. Planted medians run 0.46 s, 1.6 s, 103 s and
  216 s for `n = 9, 11, 13, 15`, about
  1.5 bits of CPU per bit of `n`. The `summarize.py` slope on `log2 B` is
  therefore not an exponent in B for this encoding and is not compared with
  the required-exponent column. At `n = 131` the factor base is fixed by the
  budget (`B ~ 2^31.6` at `m = 4`), so both dependences would have to be
  small at once; this ladder already shows the `n` dependence is not.
- **`n = 15` is where the random arm starts to censor.** Two of three
  random targets exhausted the 900 s budget (censored, not UNSAT); the third
  decomposed in 172 s. The table's 172 s for that arm is the one completed
  instance, not a median of the cell; the slope printed by `summarize.py`
  excludes any cell with a censored instance.
- **At these sizes the random arm is not the regime that matters.** The
  base is large relative to the group, so every random target decomposed
  (and quickly: median 9.7 s at `n = 13`, below the planted 103 s, because
  such targets have many decompositions). At `n = 131, m = 4` a random
  target decomposes with probability `2^-5.1` (section 1), so relation
  collection there is dominated by unsatisfiable searches, which cost about
  10x a satisfiable one at `n = 7` (`results/smoke_n7.json`).
- **Toy scale, one solver, one encoding.** Six cells with 3–6 trials each
  cannot fix an exponent. The comparison that matters is with
  `../pdp-scaling`, whose SAT `m = 4` fit is about 7 bits per unit of
  `log2 B` on subspace bases; nothing measured here suggests the Frobenius
  quotient base is cheaper per decomposition.

## Factor bases

Every cell's base is archived in `../fb-archive` (family `nbweight`, `l = w`).
`results/factor_bases.json` (`python3 fb_manifest.py`) lists each cell's curve
ID, `factor_base_sha256`, archive path and PS1 label, and
`test_fqm4_factor_bases.py` checks that `indexcalc.factorBase` rebuilds exactly
the archived set. The curves here carry their own IDs (`EC1N<n>Ckb1h...`):
`NormalView`'s field is not always `ToyCurve`'s.

## What this does not claim

- No attack, no relation collection, no discrete logarithm, nothing run on
  the ECC2K-130 challenge. Planted targets are correctness controls, not
  natural yield.
- `budget.py` is a model: H1–H3, sparse LA at `m C^2`, polylog factors
  dropped, one addition = one rho iteration. It is the same model as
  `../pdp-scaling`, so the two tables compare; it is not a lower bound on
  ECDLP.
- The "required exponent" is a target, not a proof that no algorithm meets
  it. A method with a sub-`m/2` exponent for summation-polynomial
  decomposition would move every row, and nothing here excludes one.
- The ladder is small: toy `n`, few trials, one solver, one encoding.
  Its slope is descriptive; the cells vary `n` and `B` together.
- Rows with `m >= 5` assume a chained-`S_3` system with `m - 1` links is
  buildable, which is true for the SAT encoding (it never forms `S_{m+1}`),
  not for Gröbner descents of `S_{m+1}`.

## Reproducing

```sh
pip install python-sat pycryptosat
python3 budget.py --json results/budget.json --md results/budget.md
python3 ladder.py --n 11 --weight 2 --trials 6 --timeout 900 --oracle --out results/cell_n11_w2.json
python3 summarize.py --md results/summary.md
```

Cells run: `(n, w)` in `(9, 2)`, `(11, 2)`, `(11, 3)`, `(13, 2)`, `(15, 2)`,
four at a time on a 4-core VM (CPU time is recorded per instance, so
contention perturbs wall time more than the reported CPU seconds).
