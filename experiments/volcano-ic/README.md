# Volcano index calculus at n = 19

A scaled-down analogue of ECC2K-130 and its 262 conductor-263 descendants,
small enough to run complete index calculus on every curve.

- `E0: y^2 + xy = x^3 + 1` over F_2^19: a = 0, cofactor 4, prime subgroup
  p = 130873, End = Z[tau] with discriminant -7.
- The Frobenius conductor is 457, a prime that splits in Q(sqrt(-7)), just as
  263 does for ECC2K-130. The isogeny class is therefore exactly E0 plus 456
  floor descendants, in 24 Frobenius orbits of 19. `data/enum.gp` finds them
  by point counting over every b; `data/isoclass19.txt` lists them.

Method (`ic.sage`): factor base = points with x in span{1, z, ..., z^9}, up to
sign. Relations decompose R = aP + bQ as +-P1 +- P2 via the Weil-descended
summation polynomial S3 (19 quadratic Boolean equations, 20 variables),
solved with PolyBoRi Groebner bases. Linear algebra is done mod p on the
cofactor-cleared factor base, and every recovered log is checked.

`run.sage`:

    sage run.sage census <shard> <shards>          # tier A, all 457 curves
    sage run.sage ecdlp  <shard> <shards> <ids>    # tier B, full IC x 10 scalars

- Tier A records factor-base size, Z/4 tag counts, the exact relation yield
  (every factor-base pair enumerated), the formal degree of regularity, and
  Groebner decomposition samples drawn from each of the 10 ECDLP instances.
- Tier B runs complete index calculus for the same 10 fixed scalars on every
  selected curve.

`analyze.py` (`sage -python analyze.py`) writes `results/summary.json` and the
figures.

Exact identities checked so far: eligible signed pairs =
2 C(n0,2) + n0 + 2 C(n2,2) + n2 + C(n_odd,2) from the Z/4 tags, and the
decomposition probability is 1 - exp(-eligible / ((p-1)/2)) to birthday
accuracy.

## Results

`results/summary.json` has every number; `figures/` has the plots. `sage -python build_report.py` renders the HTML report.

- **Relation yield depends only on the factor base.** The eligible-pair count equals the Z/4 tag formula on
  457/457 curves. Decomposition probability follows the
  birthday model to within 0.0046. Descendants range 0.544–0.696;
  E0 is 0.608.
- **The yield differences mostly cancel in total work.** Predicted attempts per ECDLP span
  813–847; E0 needs 828.
- **Formal degree of regularity is 11** on all 1371 sampled systems. b only enters as a constant.
- **Gröbner decomposition matches the exact yield:** 28932 hits against 29025
  expected (z = -0.90), with 146 spurious solutions rejected at lift time.
- **Per-solve cost does not depend on the curve** once machine drift is blocked out. Interleaved test over 10 curves × 60 rounds:
  Friedman p = 0.42; E0 costs 1.03× the descendant mean.
- **End-to-end ECDLP:** 310/310 logs verified over 31 curves × 10 scalars.
  - Attempts carry a small curve effect (η² = 0.15, p = 0.017) that the census predicts
    (r = 0.78, measured/predicted = 1.001).
  - There is no scalar effect (p = 0.31).
  - E0 needs 0.996× the descendants' attempts (95% CI 0.976–1.017).

Wall-clock and CPU timings on this shared machine drift with load, including P/E-core placement, and each curve's
runs happened in their own time slot. Compare curves on attempt counts and on the interleaved test, not on raw
seconds. `results/smoke-ecdlp-walltime.jsonl` holds the three wall-clock-only E0 smoke runs, which are not used in
the analysis.
