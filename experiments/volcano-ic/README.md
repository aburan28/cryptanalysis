# Volcano index calculus at n = 19

A scaled-down analogue of ECC2K-130 and the 262 curves one 263-isogeny below
it, small enough to run complete index calculus on every curve.

- `E0: y^2 + xy = x^3 + 1` over F_2^19: a = 0, cofactor 4, prime subgroup
  p = 130873, End = Z[tau] with discriminant -7.
- The Frobenius conductor [O_K : Z[pi]] is 457, a prime that splits in
  Q(sqrt(-7)). The isogeny class is therefore exactly E0 plus 456 floor
  descendants, in 24 Frobenius orbits of 19. `data/enum.gp` finds them by
  point counting over every b; `data/isoclass19.txt` lists them.
- ECC2K-130's Frobenius conductor is 263 · 146505763881528721. 263 splits like
  457; the 57-bit prime is inert. That class has about 2^65 curves, but any
  isogeny that changes the 57-bit part of the endomorphism ring has degree
  divisible by that prime. From E0 only the 262 curves one 263-isogeny down are
  reachable, and that level is what this study models.

Method (`ic.sage`): F_2^19 = F_2[z]/(z^19 + z^18 + z^16 + z^11 + z^8 + z^6 +
z^4 + z + 1), PARI's default (`MODULUS` in `run.sage`); every factor base
depends on this choice. Factor base = points with x in span{1, z, ..., z^9},
up to sign. Relations decompose R = aP + bQ as +-P1 +- P2 via the
Weil-descended summation polynomial S3 (19 quadratic Boolean equations, 20
variables), solved with PolyBoRi Groebner bases. Linear algebra is done mod p
on the cofactor-cleared factor base, and every recovered log is checked.

`run.sage`:

    sage run.sage census <shard> <shards>          # tier A, all 457 curves
    sage run.sage ecdlp  <shard> <shards> <ids>    # tier B, full IC x 10 scalars

- Tier A records factor-base size, Z/4 tag counts, the exact relation yield
  (every factor-base pair enumerated), the formal degree of regularity, and
  Groebner decomposition samples drawn from each of the 10 ECDLP instances.
- Tier B runs complete index calculus for the same 10 fixed scalars on E0, one
  seeded curve per Frobenius orbit (`results/tierb-ids-1.txt`), and the three
  descendants with the fewest and the three with the most predicted attempts
  (`results/tierb-ids-2.txt`).

Cross-checks, which share no code with the census for the tier-A part:

    python3 crosscheck.py     # numpy tier A, random subspaces, trace-zero subspace, S3 solutions
    sage crosscheck.sage      # conductors, Frobenius-stable subspaces, S3/S4 bit-degrees,
                              # dreg controls, PolyBoRi S3 solutions (about 15 minutes)

`analyze.py` (`sage -python analyze.py`) writes `results/summary.json` and the
figures, folding in `results/crosscheck*.json`.

The eligible signed-pair count 2 C(n0,2) + n0 + 2 C(n2,2) + n2 + C(n_odd,2) is
a counting identity in the Z/4 tags. The decomposition probability follows
1 - exp(-eligible / ((p-1)/2)) to within 0.0046, and the model runs 0.0008 low
on average.

## Results

`results/summary.json` has every number; `figures/` has the plots. `sage -python build_report.py` renders the HTML report.

- **Relation yield depends only on the factor base.** The eligible-pair count equals the Z/4 tag formula on
  457/457 curves. Decomposition probability follows the birthday model to within 0.0046. Descendants range 0.544–0.696;
  E0 is 0.608 exact, 0.606 from the formula.
- **The yield differences mostly cancel in total work.** Predicted attempts per ECDLP span
  813–847; E0 needs 828. The factor base sits near the attempts-optimal λ = 1.256 (curves span λ = 0.78–1.19),
  where a 10% larger factor base saves only about 2% of attempts.
- **The subspace matters, not the curve.** Over 456 random subspaces g·V each, E0, O14.13 (lowest yield on V) and
  O11.16 (median) average 824.3, 824.7 and 824.6 predicted attempts. A subspace inside the trace-zero hyperplane makes
  every factor-base point halvable and cuts predicted attempts from 824 to 602 on every curve (−27%, about −19% in
  modelled Gröbner time). That has not been run end to end.
- **Formal degree of regularity is 11** on all 1371 sampled systems. That is the minimum for this variable split: the
  quadratic part is bilinear in the x1 and x2 bits, so monomials in either set alone survive to degree dim V = 10.
  Random bilinear systems of the same shape also give 11; random quadratic ones give 5. b only enters as a constant,
  and the same holds for the top degree of S4.
- **Gröbner decomposition matches the exact yield:** 28932 hits against 29025
  expected (z = -0.90). The 146 spurious solutions are x = 0 (2-torsion) solutions; a twist solution cannot occur.
- **Per-solve cost:** no curve effect is detectable once machine drift is blocked out (interleaved test over
  10 curves × 60 rounds: Friedman p = 0.42; E0 costs 1.03× the descendant mean). The test resolves only about ±9% per
  curve, though. Solvable systems cost 584 ms and unsolvable ones 350 ms, so the expected cost is 350 + 234·Pr ms,
  477–512 ms across curves. Modelled Gröbner CPU per ECDLP spans 404–418 s, in the reverse order of attempts.
- **End-to-end ECDLP:** 310/310 logs verified over 31 curves × 10 scalars.
  - Attempts carry a small curve effect (η² = 0.15, p = 0.017) that the census predicts
    (measured/predicted = 1.001; residual χ² = 23.2 on 31 df, p = 0.84; r = 0.78 against 0.77 expected from
    sampling noise alone).
  - There is no scalar effect (p = 0.31), as a uniform target αP + βQ guarantees.
  - E0 needs 0.996× the descendants' attempts (95% CI 0.976–1.017); the census predicts 1.005×.

Wall-clock and CPU timings on this shared machine drift with load, including P/E-core placement. Each curve's runs
happened in their own time slot, and for 95% of runs instance k ran in worker process k, so the timing ANOVA's curve
and instance factors carry load and process effects. Compare curves on attempt counts and on the interleaved test, not
on raw seconds. `results/smoke-ecdlp-walltime.jsonl` holds the three wall-clock-only E0 smoke runs, which are not used
in the analysis.

## E0 with a τ-invariant factor base

`tau.sage` and `nbsat.sage`, run with `sage run.sage taucmp <shard> <shards> [variant]`; results in `results/tau-*.jsonl`
and `figures/tau.png`.

E0 alone has the Frobenius endomorphism τ. On the prime subgroup it acts as λ, a root of λ² + λ + 2 mod p, so a factor base
closed under τ needs one unknown per orbit. Same 10 scalars, CPU time, speedup paired by scalar:

| E0 factor base | decomposition | unknowns | relations | solver calls | CPU s / ECDLP | vs baseline |
|---|---|---:|---:|---:|---:|---:|
| x in V, dim 10 (baseline) | Gröbner | 494 | 504 | 827 | 444 | 1× |
| τ-orbits of x in V', dim 6 | Gröbner, 19 shifts | 29 | 39 | 5434 | 70 | 6.85× (5.70–8.02) |
| τ-orbits of x in V', dim 7 | Gröbner, 19 shifts | 54 | 64 | 2664 | 72 | 6.26× (5.86–6.70) |
| normal-basis weight ≤ 3 | CryptoMiniSat | 35 | 45 | 48 | 668 | 0.68× (0.62–0.74) |

All 40 logs are verified.

- **Weight-≤ 3 normal basis:** the textbook τ-invariant base (665 points, 35 orbits). No 38-variable PolyBoRi solve finished
  within 15 minutes. With SAT (XOR clauses for the descended equations, sequential-counter weight bounds, stop at the first
  lifting model) it works, but each call costs about 14 CPU s, dominated by UNSAT proofs.
- **Orbit-closure bases:** F = {τ^j P : x(P) in V'} works with Gröbner bases. Squaring is F2-linear, so
  R = P1 ± τ^j P2 is a 2k'-variable quadratic system for each shift j.

Timing windows: the τ runs and 4 baseline runs shared one window. The other 6 baseline runs and all SAT runs ran later,
after the external drive dropped out and remounted.
