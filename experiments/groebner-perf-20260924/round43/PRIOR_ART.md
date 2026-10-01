# Scope relative to existing algebraic approaches

The base branch now contains `experiments/linearized-half-decomposition/`.
Its own documentation identifies its symmetric-coordinate linearization as
related to existing point-splitting work and does not claim a new idea.
That experiment uses different decomposition sizes, base dimensions and
accounting boundaries. Its timings are not paired with this Gröbner query
experiment and must not be substituted as a speedup comparator.

Courtois, *On Splitting a Point with Summation Polynomials in Binary Elliptic
Curves*, section 3, uses low-degree restrictions and affine constraints in
a point-splitting method. Its argument includes expected independence of
constraints. This supports treating affine elimination as prior art, not
labelling our witness format a novel general Gröbner algorithm.
[Primary paper](https://eprint.iacr.org/2016/003.pdf).

Karabina, *Point Decomposition Problem in Binary Elliptic Curves*, studies
the tradeoff between more auxiliary variables and lower-degree equations.
Section 3.4 distinguishes degree of regularity from first fall degree;
the final acknowledgment explicitly cites evidence that their approximate
equality may fail as field degree grows. A low-degree relation in our code
therefore cannot establish a constant regularity bound.
[Primary paper](https://eprint.iacr.org/2015/319.pdf).

The engineering distinction here is explicit independent certification:
derive each consequence from the original equations, recompute actual rank,
enumerate every remaining assignment, and fail explicitly when budgets are
exhausted. This avoids assuming generic rank for correctness. Whether it
improves complete query cost depends on the measured rank distribution,
proof construction and checking costs, and fallback frequency. No novelty
or whole-algorithm asymptotic claim follows from this certificate alone.
