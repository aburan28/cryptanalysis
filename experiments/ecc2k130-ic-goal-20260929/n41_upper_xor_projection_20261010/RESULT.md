# Coupled seed sums yield a 12-atom N41 public-point relation

A six-pair W6 diagonal-atom method found an **exact 12-column relation** on
the frozen public point `Q=(1458168294740,1672312028033)` of
`EC1N41Ckb1h7d5e80d3c4d0`. Pairs 2 and 3 have the same XOR seed sum, as do
pairs 4 and 5. A reusable four-atom group index and a target-conditioned join
found the relation after 730,852 accepted right-side probes. The independent
[checked-Sage replay](w6_sage_audit.json) reconstructed all 12 subgroup
points from the audited W6 source, checked their folded Frobenius columns and
both seed equalities, and summed them to the supplied `Q`.

For two atoms in one rotated source space, let their linear source masks be
`a,b` and their seed sum be `s=a XOR b`. The first two pairs remain free;
the next two share one `s`, and the final two share another `s`. The native
program indexes every distinct-column four-atom sum from the free pairs.
Each constrained four-atom block is enumerated by matching seed sums before
the target is supplied to the join. The online stage samples one state from
each constrained block, looks up `Q` minus their sum, and checks all 12
columns and the full group equation. Every accepted relation remains exact;
the seed equalities remove source families before the group lookup.

| Frozen N41 public-point stage | Result |
| --- | ---: |
| Field and subgroup | `GF(2^41)`, `r=549756390943` |
| Six paired rotations | `0,5,10,15,20,25` |
| Actual factor-base points / folded columns | `B=384` / `K=26` |
| Signed unordered pair states per rotation | 1,956 |
| Reusable free four-atom index | 3,167,136 states |
| Each same-seed four-atom domain | 51,840 states |
| Target-dependent accepted probes / group hits / column rejects | 730,852 / 5 / 4 |
| Reusable index setup / target query | 1.684634834 s / **0.799029083 s** |
| Native peak RSS | 190,955,520 bytes |
| Independent installed-Sage relation replay | **PASS**, 12 distinct columns |

The [frozen protocol](w6_protocol.json), [input export](w6_export.json),
[native result](w6_result.json), [relation](w6_hit.json), and
[terminal audit](terminal_audit.json) bind the source, input, executable,
resource envelope, and replay. The query used one worker, a 20-million
accepted-probe limit, a 600-second online cap, and a 4-GiB RSS cap. Setup
and checked-Sage replay were measured separately from the target-dependent
lookup. These CPU wall measurements are exploratory on an unisolated host.

## Exact support screen and solver gate

The initial W5 12-atom lower-field control was screened before a group
search. Its 14 folded columns leave only
`16,348,151,808 / 549,756,390,943 = 0.029737...` rows per subgroup target
on average after the two seed equalities and all 12 column distinctions.
This is an exact group-wide mean, calculated from the frozen W5 pair index;
it bounds the success probability for a uniformly chosen target by the same
number. The [distinct-column count](n41_distinct_count.json) records the
policy and arithmetic. The W6 source has 26 folded columns and supplied the
public-point relation above.

As a separate upper-chain solver check, exact CNF-private XOR projection
reduced the archived N41 W5 five-pair formula from 15,676 to 11,814
variables and from 5,573 to 1,711 native XOR rows while retaining all
93,985 public CNF clauses. The [projection and reverse-lift audit](control_audit.json)
checks a complete public-point assignment against the original and projected
XCNFs. The projected **all-five-outputs-fixed** CryptoMiniSat query logged
732 search restarts and reached its 20-second parent cap with status
`CENSORED_TIME`; its [result](all_fixed_query/result.json) retains the raw
solver log and 32,440,320-byte sampled solver peak RSS. The projected
unfixed W5 query stayed behind that fixed-output gate. This identifies
upper-chain propagation as the solver obstacle for that separate W5 encoding.

## Challenge-width transfer bound

For the exact N131 W14 source, Walsh XOR autocorrelation and explicit
same-column exclusions give **135,120,112 signed unordered pair states** per
rotation. Six same-rotation pairs at rotations `0,13,26,39,52,65` have
`B=98,640` usable subgroup points and `K=8,160` folded columns. The two
seed-sum equalities leave a group-wide mean of at most **33.324886...**
12-atom tuples per subgroup target before cross-pair folded-column
filtering. The [exact tuple-count receipt](seed_sum_count.json) gives the
integer numerator and the subgroup order; this mean is a support bound, not
a measured fixed-target relation rate.

The N41 explicit join representation does not fit the N131 resource gate.
Even after a same-seed constraint and cross-pair distinct-column filtering,
the four-atom domain has at least **1,111,305,845,632 states**. One 17-byte
compressed group key per state requires at least **18,892,199,375,744 bytes**,
excluding descriptors and indexing overhead. A 4-GiB store holds at most
252,645,135 such keys, so an exact compact representation needs a capacity
factor of at least **4,399** relative to this explicit state-key design.
The free four-atom domain used by the N41 join is still larger at challenge
width. The [transfer calculation](transfer_w14.json) records the union-bound
column exclusions and byte arithmetic. This bound applies to explicit
per-state keys; it sets a concrete compression target for the next method.

The next experiment is an exact target-conditioned representation of the
same-seed four-atom image that supports group-sum membership and witness
recovery without materializing those keys. It should first recover the
archived N41 witness with all source choices unpinned, then run the frozen
N131 public-point relation gate under one worker, 600 seconds, and 4 GiB.
The complete IC candidate ID remains `null` while that decomposition kernel,
relation collection, factor-log solve, and target descent are being specified.
