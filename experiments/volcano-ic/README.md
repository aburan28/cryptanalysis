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
