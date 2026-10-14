# Split-prime radix for fixed-base scalar multiplication

The new evaluator replaces the two-dimensional mixed-radix digit atlas with
21 signed integer digits in the Eisenstein base `pi = 86 - 21 tau`, where
`tau² = 3 tau - 3` and `N(pi) = 3301`. A single row of positive multiples
of `[pi^i]G` supplies each digit. Two short rows handle the final carry;
one stores `[m]pi^21 G` and the other stores `tau([m]pi^21 G)`. Thus the
online path needs at most 23 selected affine points and no tau evaluation.

In the quotient by `pi`, `tau = 1576 (mod 3301)`. For a coefficient pair
`a + b tau`, choose the centered integer residue
`d = (a + 1576 b) mod 3301` in `[-1650,1650]`, and put
`k = (a + 1576 b - d)/3301`. Exact division gives

```
a' = 23 k - 11 b
b' = 21 k - 10 b
a + b tau = d + (86 - 21 tau)(a' + b' tau).
```

Repeat this step 21 times. The final pair `(a_21,b_21)` contributes
`[a_21]pi^21 G + [b_21]tau(pi^21 G)`. The signed scalar decomposition
already used by the mixed-640 evaluator supplies the initial `(a,b)`;
the same point and 128-scalar frozen fixture are used for comparison.

The existing lattice basis has determinant equal to the secp256k1 subgroup
order. Its floor/ceil representative lies in one basis cell, yielding
`|a| <= |W_0|+|V_0|` and `|b| <= |W_1|+|V_1|`. Therefore the complex
magnitude of `a+b tau` is below
`M = 2252907023369138918423925520396307732351`, using `|tau|<2`.
Since `|pi|=sqrt(3301)>57` and `|d|<=1650`, the magnitude after 21 steps is
below `M/57^21 + 1650/56 < 331.023`. The quadratic norm
`a²+3ab+3b²` is at least `a²/4` and `3b²/4`, so both terminal coordinate
magnitudes are below 663. The native path checks this bound before each
terminal lookup. The table holds 21 rows of 1,651 entries and two terminal
rows of 664 entries: **35,999 points, 2,303,936 point bytes, no atlas**.

`split_prime_radix.py` checks every holdout recoding, exact reconstruction,
the lattice determinant, the numeric bound, and the table counts. On the
128-scalar fixture, 124 recodings use 23 nonzero point terms and four use
22; the largest observed terminal coordinates are 40 and 31. These are
fixture observations; the 663 table limit follows from the bound above.
`SplitPrimeRadix.lean` proves the quotient root and pi residue identities,
the exact division step, recursive reconstruction, and the group-action
evaluation formula. Its numeric lemma checks the final rational bound.
The analytic contraction and the floor/ceil lattice-cell inequalities are
written here and checked numerically by the model; their full Lean bridge
remains open.

`native_split_prime_bench.py` generates the pinned Rust evaluator and a
128-scalar correctness test against independent binary multiplication.
Table construction is recorded as preparation; the online timer includes
recoding, signed lookup, mixed additions, and affine recovery. A matched
serial RunPod comparison with grouped, axial, and frontier-15 formats is the
next performance check. This variable-index fixed-base evaluator is a
research benchmark path; use in a secret-scalar API would require a
constant-time selection design and a separate side-channel review.

Complex-radix scalar expansions in Eisenstein rings have prior literature,
including [Heuberger and Krenn, *Symmetric digit sets for elliptic curve
scalar multiplication without precomputation* (2014)](https://doi.org/10.1016/j.tcs.2014.06.010).
The contribution tested here is the split-prime, single-integer-digit
fixed-base table layout, its bounded terminal carry, and the matched native
implementation on this exact curve and workload.
