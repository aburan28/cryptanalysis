# Target-conditioned two-pair sparse-product circuit on N41

The two-pair circuit preserves the exact rotated W6 seed-sum and product
spans for both unresolved right-side pairs and couples their reciprocal
outputs to the middle point required by the public target. A complete
known public-row assignment satisfies its 5,662 clauses and 1,125 native
XOR rows. The unpinned known-positive query and two target-derived queries
each reached the 35-second parent cap with `BOUNDED_UNKNOWN`; these runs
therefore do not establish the relaxation's rejection rate.

## Frozen method and controls

The [protocol](protocol.json) fixes `GF(2)[t]/(t^41+t^3+1)`, curve
`y^2+xy=x^3+1`, the previously checked public target
`Q=(1458168294740,1672312028033)`, its raw transported preimage,
and source rotations 20 and 30 for the unresolved pairs. Each pair has
a free six-bit seed sum in its rotated W6 span, an 11-bit product in the
rotated `span(t^2,...,t^12)`, a 41-bit reciprocal output, and a branch bit.
The exact halftrace-cubic pair equations and the S3 equation joining the
two outputs to the target-required middle point are enforced. Product
factorization, rational source lifts, and folded-column checks are
deferred, making this a sound necessary relaxation of the full pair search.

The checked-Sage [target producer](targets_sage.py) constructed eight
middle-point queries from the same public raw target and exact first-two
source pairs, using first-pair seed sums 1 through 8. The
[known-positive control](control_result.json) binds all relaxed variables
from the independently replayed eight-point relation and verifies every
clause and native XOR row. The formula has 1,844 AND gates; target constants
affect simplification, so variable and XOR-row counts differ by query.

| Frozen query | First-pair seed sum | Formula bytes | Solver seconds | Peak combined RSS | Terminal status |
| --- | ---: | ---: | ---: | ---: | --- |
| [Target-derived 0](query_00.json) | 1 | 193,610 | 35.066 | 319,193,088 B | `BOUNDED_UNKNOWN` |
| [Target-derived 1](query_01.json) | 2 | 194,167 | 35.011 | 155,140,096 B | `BOUNDED_UNKNOWN` |
| [Known positive](positive_result.json) | relation fixture | 187,435 | 35.087 | 202,113,024 B | `BOUNDED_UNKNOWN` |
| [Known positive, wider XOR matrix](matrix_positive.json) | relation fixture | 187,435 | 35.030 | 108,756,992 B | `BOUNDED_UNKNOWN` |

All used one worker, 30-second CryptoMiniSat limit, 35-second parent stop,
and 4-GiB combined RSS guard. Formula construction, write/hash, solver,
and post-solver capture are recorded separately in each receipt and
reconciled in the [terminal audit](audit.json). These are exploratory
local stage times; target-independent source setup and target fixture
construction are outside the solver intervals. Each solver log began
search and has no terminal SAT or UNSAT line.

The default solver dropped a later 987-row XOR matrix with 2,764 columns
because its column limit was 1,000. A separate frozen
[matrix protocol](matrix_protocol.json) raised that limit to 3,500 while
retaining the same known-positive formula. Its log confirms use of a
989×2,768 matrix, yet the unpinned positive search still reached the cap.
The widened matrix query on target-derived control 0 was left unrun after
this positive gate did not terminate.

## Method decision

The circuit's full assignment check establishes the intended algebraic
relaxation, but the bounded unpinned searches do not measure whether it
rejects middle-point queries. The next implementation should exploit the
pair equation's linearity in its reciprocal output for each fixed product
`p`: `L_p(z)=H(s^2)+epsilon`, with
`L_p(z)=p*z+H(z^2)`. On N41, precomputing the linear-map solver for each
of the 2,048 product-span elements permits direct enumeration of relaxed
pair-output lists and an exact two-list target join, avoiding repeated SAT
search. The charged construction, list sizes, query yield, and independent
replay will determine whether this over-approximation is selective enough
to justify a symbolic or batched N131 version. `candidate_id` remains
`null` while the full IC pipeline is unresolved.
