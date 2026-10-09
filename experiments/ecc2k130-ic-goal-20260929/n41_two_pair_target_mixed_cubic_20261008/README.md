# Two-free-pair target propagation: a mixed-cubic falsifier

This bounded experiment tests one cheap route to the target-coupled
pair-block propagator requested by the [N41 gate](../NEXT_TARGET_COUPLED_BLOCK_GOAL.md).
The route fails its structural gate on the frozen N41 geometry. It does not
test a complete point-decomposition solver, recover the public target log, or
measure IC versus rho.

## Design and falsifier

Write a valid eight-point relation as `Q = U0 + U1 + U2 + U3`, where each
`Ui` is the sum of two distinct-column factor-base points in one W6 window.
Let `s0` and `s1` be the six-bit seed-sum masks for the first two pairs.
Before choosing either leaf of `U2` or `U3`, an exact universal equation in
`(s0,s1,Q)` could reject entire first-two-pair branches without building the
two-free-pair Cartesian index. It must vanish on every valid four-pair
relation, over every target point.

We froze two Boolean feature families before evaluating each one:

* `Vx`: constant, all degree-one and squarefree degree-two terms in the 12
  bits of `(s0,s1)` and the 40 free bits of `x(Q)`, plus all 1,440 mixed cubics
  `s0_i s1_j x_k`. The known trace-zero x bit is omitted. Dimension: 2,819.
* `Vy`: the same construction with all 41 bits of `y(Q)`, including all
  1,476 mixed cubics `s0_i s1_j y_k`. Dimension: 2,908.

For a feature family `V`, evaluate its monomials on exact valid relations to
form a binary matrix `M`. Any universal necessary equation in `V` lies in
`ker(M)`. A full-column-rank witness made of valid relations proves that
kernel is zero, regardless of how an equation might be discovered. A rank
deficit in a finite sample would be inconclusive and would require more
rows, an independent holdout, and an exactness proof before use as a filter.
These rules are in the [x protocol](protocol.json) and [y protocol](protocol_y.json).

## Executed N41 experiment

Both screens consume the same 8,192 valid eight-point rows from the frozen
`EC1N41Ckb1h7d5e80d3c4d0` W6 geometry. The four exact unordered pair
domains have 1,956 states each. The prior [checked-Sage audit](../n41_four_pair_target_quadratic_rank/sage_audit.json)
replayed all 8,192 sampled group sums and distinct-column conditions; its
input hash is frozen in both protocols. These are planted structural rows
over many resulting points. They estimate neither ordinary-target relation
yield nor fixed-target online cost.

| Frozen feature family | Columns | First rows consumed | Rank | Independent audit |
| --- | ---: | ---: | ---: | --- |
| `Vx`, two pair sums and target x | 2,819 | 2,820 | **2,819** | [PASS_FULL_RANK](audit.json) |
| `Vy`, two pair sums and target y | 2,908 | 2,909 | **2,908** | [PASS_FULL_RANK](audit_y.json) |

The [x result](result.json) and [y result](result_y.json) retain every
pivotal row index, source/data hashes, and measured producer wall time.
The exploratory producer times were 9.028 and 19.078 seconds on this host;
they are rank-screen costs, not a solver-speed comparison. Separate auditors
rebuilt the monomial order in reverse and eliminated with low pivots rather
than the producers' high pivots. The [receipt verifier](verification.json)
checks both ranks, source hashes, and the earlier Sage audit. Neither screen
used the frozen public N41 target as a search input.

Because the pivotal rows are exact valid relations and each evaluation
matrix has full column rank, **no nonzero universal Boolean equality in
either declared feature family exists**. This is an exact algebraic
conclusion for this N41 factor-base policy. It excludes this particular
cheap prefix filter even if a different solver tries to derive it.

The result leaves open equations that retain pair-output coordinates or
leaf products, mix target x and y, have higher degree, or arise from a
target-specific elimination. A fixed-target classifier learned after an
exhaustive completion search would already have paid for that search.

## Next constructive design and gate

The surviving design retains each pair's output point `Ui` and its exact
seed variables. For pair `i`, use `s_i=a_i+b_i` and
`a_i b_i=a_i^2+s_i a_i` to share local products, impose the exact pair
S3 relation, and connect the four outputs to the supplied public `Q`
through a balanced S3 tree. The proposed new operation is a target-bound
block eliminant: eliminate the still-free variables of pairs 2 and 3
while retaining `(s0,s1,U0,U1,Q)`. It must reject impossible first-two-pair
states from `Q` before enumerating either free pair. Keep sign and
exceptional branches and independently group-check every decoded row.

The next experiment should freeze the same public N41 point and the known
twelve-row census as a private correctness oracle. Its public solver must
load neither those rows nor their scalars. Measure eliminant build cost,
partial states pruned while both last pair domains are free, failed
attempts, peak RSS, and time to one independently Sage-replayed row under
120 seconds and 4 GiB. If the eliminant is identically zero, exceeds the
cap, or classifies prefixes only after enumerating the two-pair product,
the method fails. Before an N131 query, use the exact W18 base and a
source-bound 600-second, 4-GiB work/memory projection. This rank experiment
supplies neither the eliminant nor that projection; no N131 query was launched.

## Replay

These standard-Python diagnostics use the previously saved Sage audit and
start no Sage job. In a fresh copy of this directory, with the frozen input
hashes still matching, run `screen.py`, `audit.py`, `screen_y.py`,
`audit_y.py`, and `verify_receipts.py` in that order with Python 3.9 or newer.
Set `PYTHONDONTWRITEBYTECODE=1` to avoid Python cache files. The runners
refuse to overwrite retained receipts.

All candidate and run IDs remain null; no complete IC pipeline or
single-target speedup is claimed. CPU timings lack an isolated-host receipt
and stay exploratory.
