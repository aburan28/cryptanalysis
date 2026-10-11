# Exact five-pair swap quotient in the joint W16 N131 circuit

The five remaining W16 pairs now use a canonical unsigned order for their
two source masks. Swapping the leaves of any pair preserves its source sum,
source product, reciprocal pair output, the two shared seed-sum constraints,
the distinct-column set, and the target group sum. Because every pair already
requires distinct masks, the five swaps act freely: each valid relation has
exactly **32 ordered-mask representations**, and the added inequalities keep
one. The [four-bit exhaustive CNF test](test_canonical.py) checks the emitted
comparator for every ordered input; the [checked-Sage orbit audit](audit.json)
replays all 32 swaps of the frozen twelve-point witness and finds exactly
one canonical representative.

The change adds only **75 variables and 300 CNF clauses** to the prior
[joint 32-prefix circuit](../n131_w16_joint_prefix_20261010/RESULT.md).
Its 75 pair-order differences reuse native-XOR rows already present in the
distinct-mask constraints, so the native-XOR count stays fixed. The complete
constructed witness satisfies all clauses and XOR rows after each pair is
put in canonical order, and the [control receipt](control.json) verifies its
projected group sum. This is an exact reduction in equivalent assignments;
it does not imply a factor-32 runtime reduction.

| Frozen constructed-target formula | Joint W16 | Canonical pairs |
| --- | ---: | ---: |
| Prefix/preimage choices | 128 | 128 |
| Variables | 198,137 | 198,212 |
| CNF clauses | 425,729 | 426,029 |
| Native-XOR rows | 34,729 | 34,729 |
| XCNF bytes | 26,491,206 | 26,496,728 |
| Pair-swap representations per relation | 32 | 1 |

## Full-budget constructed search

The [frozen protocol](protocol.json) fixed one constructed public target,
32 signed first-pair choices, four target fibers each, one CryptoMiniSat
worker, a 600-second total wall cap, 4-GiB combined RSS cap, and the exact
solver flags before execution. The formula was built through the checked
repository Sage launcher, whose [runtime receipt](sage_runtime_info.json)
was saved first. The solver read only that unpinned public-input formula; the
known masks were used in the separate validation control.

The [query row](query.json) returned `CENSORED_TIME` at its 595.220-second
safe stop. Formula construction and serialization took 9.867 seconds; the
solver interval took 585.354 seconds. Sampled solver CPU reached **107.062
seconds**, with **847,118,336 bytes** sampled peak combined RSS. The raw
transcript contains **313 restart lines** and no model or final SAT/UNSAT
status. The [independent audit](audit.json) binds the formula and source
hashes, exact 32-member swap orbit, checked group control, raw transcript,
cap, and terminal status. This is a censored constructed-control search, not
an ordinary relation-yield observation or an isolated-host performance
comparison.

The full-budget result narrows the next method step. Removing the entire
five-pair permutation redundancy and searching all 32 prefixes jointly did
not yield a model within the frozen local cap. The next experiment should
couple partial pair-output families to the public target **before** completing
all ten free masks. Use the previously replayed N41 public relation to test
sound partial-state rejection and count proposals, inverse calls, failed
branches, wall and RSS. Transfer only a generator with an exact source-bound
N131 work/memory projection to a fresh ordinary target. `candidate_id`
remains `null` until relation yield, rank, factor logs, target recovery, and
same-point rho are measured for a complete method.
