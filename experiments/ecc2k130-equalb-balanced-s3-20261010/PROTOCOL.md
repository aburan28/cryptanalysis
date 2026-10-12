# Exact balanced-S3 ECC2K-130 equal-B PDP gate

The frozen source W24 and normal-weight-four policies each have
`B=11,743,888` subgroup-usable factor-base points. Their existing
target-first six-summand, four-lift CryptoMiniSat formulas both reached the
internal 120-second limit with `BOUNDED_UNKNOWN`. This gate tests whether a
balanced pair tree changes the exact point-decomposition search on the same
ordinary public query. Query zero is a development gate; later frozen public
queries remain held out until this result and its decision are committed.

## Frozen circuit and comparison

Use the same source curve `EC1N131Ckb1h136f03e58c98`, six exact leaf
membership equations, ascending leaf selectors, W24 prefix, normal4
weight-four rule, and four checked target x lifts as the immediate parent
experiment. For leaf x coordinates `x0..x5`, introduce finite intermediate
x coordinates `u0,u1,u2,v` and impose five S3 equations:

`S3(x0,x1,u0)=S3(x2,x3,u1)=S3(x4,x5,u2)=0`,
`S3(u0,u1,v)=0`, and `S3(v,u2,target_x)=0`.

The final target x is selected by the parent's exact two-bit mux,
`j=s0+2*s1`. This is one formula for one query, rather than four separate
target attempts. The pair tree has four intermediate x variables, compared
with five intermediate x variables and a final equality in the target-first
formula. The same finite-chart limitation applies: a selected signed pair
or four-leaf partial sum at infinity needs a separate branch in a complete
PDP. A SAT model is only a candidate relation until checked Sage reconstructs
all selected leaves, chooses signs, verifies their group sum against the
selected raw target lift, checks the `[4]` projected relation, and records
its row keys. A capped search remains `BOUNDED_UNKNOWN`, never UNSAT.

Before ordinary search, independently replay both planted six-point
fixtures from the parent Sage control receipt. Check all three pair sums,
the four-leaf sum, and the final target in the exact Sage group law, then
evaluate every Boolean IR root with the derived finite x assignments.
Check a one-bit mutation of the target x is rejected by those same assigned
intermediates. Reuse the parent's checked four-lift Sage and native-XOR mux
controls and exact leaf controls as construction prerequisites.

Build normal4 and then W24 ordinary-query XCNFs. Run pinned
CryptoMiniSat 5.14.7 SHA-256
`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`
sequentially, with one thread, native XORs, `--maxtime=120`, a 150-second
external wall guard, and a 4 GiB RSS guard. Preserve exact source/input,
solver binary and formula hashes, raw stdout/stderr, status, conflicts,
restarts, build time, solver wall time, and memory. The prior target-first
receipts are comparison controls; all wall-time ratios on this unisolated
host are exploratory.

The decision variable is verified ordinary relations and novel rank per
fully charged query. If both searches are capped without a verified row,
retain the censored records and select a structurally different solver
strategy before expanding the 16/256-query prefixes. Potential column
counts and search progress alone do not establish relation yield, final
matrix cost, or the one-target online IC result. `candidate_id` stays `null`
until the full collection, matrix, and target-descent pipeline is defined.
