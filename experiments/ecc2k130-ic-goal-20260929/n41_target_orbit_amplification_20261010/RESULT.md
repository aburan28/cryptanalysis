# Batched Frobenius-orbit target lookup on the six-pair IC control

One prepared N41 six-pair index can query all **41 Frobenius conjugates** of
one public target and transport a factor-log result back to the original
target. A native worker found a twelve-point relation on orientation 26 and
recovered scalar `172371579945`; independent checked Sage replay verified
the conjugated target, all twelve source points and distinct columns, both
same-seed constraints, the factor-log sum, and multiplication by the original
generator. A batched-inversion version returned a **byte-identical witness**
with the same right-block sample stream and 972,629 charged orbit lookups.

The field is `GF(2)[t]/(t^41+t^3+1)`, the curve is
`y²+xy=x³+1`, the subgroup order is `549756390943`, and the curve ID is
`EC1N41Ckb1h023d9a38bbf7`. The source is the previously audited six W6
windows at rotations `0,5,10,15,20,25`: B=384 projected source points,
K=26 signed-Frobenius columns, 1,956 two-point states per rotation, a
3,167,136-row reusable left index, and two 51,840-state same-seed right
domains. The query reused the archived prepared index policy and 26 verified
factor logs. Its public input was the archived fresh point
`(1544641481148,1238630537263)`; it is now an **archived-point mechanism
diagnostic**, not a new unseen-target workload.

The canonical [unbatched candidate](candidate_unbatched.json) is
`IC1N41Ckb1fb384PDP12mitmRCsampleLAgaussTDdirectISO0hf20fa632dd98`;
the [batched candidate](candidate_batch.json) is
`IC1N41Ckb1fb384PDP12mitmRCsampleLAgaussTDdirectISO0h42fa5f4334b6`.
Their [diagnostic run records](diagnostic_runs.json) reuse the archived
one-target workload ID `a90ab6b621fe` and append `Wa90ab6b621feR1` to
each candidate ID. These are implementation-specific N41 identities for
repeating an already published point, not primary fresh-target speedup rows.

For Frobenius `τ(x,y)=(x²,y²)` on this curve, the checked subgroup eigenvalue
is `λ=256851699273` modulo `r`. If a relation for `τ^j(Q)` has factor-log
sum `L`, then the original scalar is `λ^(-j)L mod r`. Both workers check the
subgroup, exact group relation, and recovered original scalar. The batched
worker uses one Montgomery batch inversion for the 41 nonexceptional
denominators `x(τ^j(Q)) + x(R)` per right-block sum `R`; coincident-coordinate
and identity cases use the exact group law. The same frozen RNG seed gives an
identical hit and exact search counters in both orbit workers.

The [first protocol](protocol.json) and [batch protocol](batch_protocol.json)
freeze the executable/source, source points, logs, archived target, one worker,
20-second online cap, 20-million right-sample cap, and 4-GiB RSS cap before
each respective run. Both online intervals start when the target is streamed
to a worker whose index and logs are ready; orbit construction, failed
lookups, relation replay, log transport, and scalar check are charged. Their
five exclusive phase fields sum exactly to the recorded online interval.

| Archived N41 target query | Direct frozen worker | 41-way orbit | Batched 41-way orbit |
| --- | ---: | ---: | ---: |
| Accepted right-block samples before verified hit | 59,042 | 23,723 | 23,723 |
| Target-dependent hash lookups | 59,042 | 972,629 | 972,629 |
| Online wall, seconds | 0.044740209 | 4.136589333 | 0.981907375 |
| Reusable index setup, seconds, outside online | 1.199545708 | 11.486078042 | 7.361825666 |
| Peak process RSS, bytes | 193,167,360 | 190,627,840 | 190,578,688 |
| Recovered original scalar | 172371579945 | 172371579945 | 172371579945 |

The direct column is the earlier [fresh N41 run](../n41_coupled_sixpair_full_ic_20261010/RESULT.md)
on this exact public point and RNG seed. The orbit runs were recorded later
on a contended host, so the wall ratios are exploratory. The exact work
counters show that 41 orientations reduced accepted right samples by about
2.49-fold in this deterministic stream but increased charged hash lookups by
about 16.47-fold relative to direct querying. Batching reduced measured
orbit online wall by about 4.21-fold under these local conditions. The
[native receipts](native.json), [batched receipt](batch_native.json),
[Sage relation replay](sage_audit.json), and [batch equivalence audit](batch_audit.json)
bind those claims. Both native executables [rebuilt byte-identically](rebuild_receipt.json)
from their frozen sources with the recorded C++ flags. The checked
[Sage runtime](sage_runtime_info.json) was
saved before independent replay. The first Sage replay attempt used an
unavailable polynomial encoding method and failed before writing an audit;
the [failure receipt](sage_audit_attempt1_failure.json) records the script
error. The corrected script converts coefficient lists to integers and passed.

The [exact transfer arithmetic](transfer.json) uses the independently audited
N131 W16 census `N=2,151,089,140`, `M=70,608,489,011,888`, and
`r=680564733841876926932320129493409985129`. For one fixed first-pair
prefix and one uniform target orientation, the optimistic support fraction
is at most `N M²/r ≈ 0.01576`. The exact union ceiling reaches one half at
32 distinct orientations and saturates at 131. The previously audited N131
Frobenius eigenvalue has order 131 in this subgroup, so any nonidentity
subgroup target has a full orbit. This arithmetic removes a **counting
obstruction** for trying one W16 prefix across orientations; it does not
establish overlap, target-specific membership, successful extraction, or an
N131 work bound. No N131 orbit query was run.

The practical next gate remains a target-conditioned partial-output
generator that rejects families before a second complete pair is selected.
An orbit dimension is useful only if such a generator can share its expensive
algebra across conjugates and charge every orientation to the same online
target interval. The existing five-pair SAT control remained censored at its
600-second search cap, and this N41 group-index mechanism does not replace
that N131 extractor. An N131 candidate ID remains `null` until its full
decomposition and recovery method is specified and measured.
