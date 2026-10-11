# Factor-base subspace census (n = 11, 13, 17, 19)

Measurement behind the claim, in the top-level README status note, that
curve-derived factor-base sets give no structural gain over random sets.

For a binary Weierstrass curve with c = a6^(1/2), a nonzero x is a rational
abscissa iff Tr(x) + Tr(c/x) = Tr(a2). After y = x/c this is the set
S = { y != 0 : Tr(1/y) + Tr(c*y) = eps }. A d-dimensional F2-subspace V of
GF(2^n) is a full-density factor base iff V \ {0} is inside S. N_d(c, eps) is
the number of such subspaces. The random model for a set of density rho
predicts E[N_d] = [n, d]_2 * rho^(2^d - 1); the tables report N_d divided by
that prediction at each set's own density.

| file | what it does |
|------|--------------|
| `volcano.py` | trace, conductor, class numbers and reachability of the ECC2K-130 isogeny class (needs sympy) |
| `subsp.c` | exact canonical-basis enumeration of N_d, n <= 13 |
| `subsp2.c` | unbiased Monte Carlo (Knuth tree-size) estimator, N_1 and N_2 exact, used for n = 17, 19; validated against `subsp.c` at n = 13 |
| `analyze.py` | normalises by the random model, Welch tests, prints one block per n |
| `c17.txt`, `c19.txt` | the sampled values of c (seeded; c = 1 is the Koblitz curve) |
| `data/` | raw output of every run |
| `appendix-curve-choice.md` | write-up: class structure, single-parameter reduction, results, claim boundary |

```
clang -O2 -o subsp  subsp.c
clang -O2 -o subsp2 subsp2.c
./subsp  13 0x201B 0 0 "$(cat c13.txt)"        # exact (slow: tens of minutes per class at n = 13)
./subsp2 17 0x20009 500000 c "$(cat c17.txt)"  # Monte Carlo
./subsp2 17 0x20009 500000 r 15                # random baselines
python3 analyze.py
```

Field polynomials: n = 11 `0x805`, 13 `0x201B`, 17 `0x20009`, 19 `0x80027`
(all checked irreducible). Known gaps: at n = 19, 3 of the 41 sampled values of c
did not finish and are absent from `data/n19_curves.txt`. The Monte Carlo
baselines show zero dimension-6 hits because the expected count is below 3
(about 0.3 at n = 17 and 2.9 at n = 19); that is a detection limit, not a result.
