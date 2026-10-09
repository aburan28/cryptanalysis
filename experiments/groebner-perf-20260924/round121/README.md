# Boolean field-pair obstruction before the matrix-seed checker

The five hard 12-variable queries spend several milliseconds independently
checking a Macaulay seed that is then rejected on the first original generator.
This opt-in candidate checks a cheaper necessary Gröbner-basis condition first.
For each seed row `g` whose leading monomial contains `x_i`, it reduces the
Boolean field pair `x_i*g` by the seed rows. A nonzero normal form proves the
seed is incomplete under the declared grevlex order. The query then keeps the
seed for native continuation and independently checks the completed basis and
original equations as before. The exact final proof, assignment, and curve
replay must match the `round119` bitset baseline.

The probe is local to one query. It has explicit bounds of 12 variables, 128
seed rows, 20,000 seed terms, and 200,000 charged work units. Any absence of
an obstruction, exhausted cap, invalid seed view, or wider ring falls back to
the existing independent checker. A found obstruction records the seed row,
variable bit, irreducible leading term, pair count, reduction steps, and
charged work. It is a rejection certificate for the candidate seed, not an
acceptance certificate for a final basis.

Validation freezes the source before timing. `test_guard.py` compares the
native probe with a separate set-based oracle on random small Boolean bases,
plus cap, malformed-term, and wider-ring controls. The five hard queries run
in optimized and UBSan builds against the independently audited reference.
The paired profile compares complete target-dependent queries with the
`round119` baseline, requires identical final proof bytes, basis, assignment,
producer work, equations, and curve replay, and retains every worker and
failure. The local CPU ratios are diagnostics until a qualifying isolated
host replays the complete-query manifest.
