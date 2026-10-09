# N41 ordinary public-target control of second-link lookup propagation

The exact second-link lookup passed a full N41 phi-chain correctness control:
an independently constructed 12-summand relation satisfies every generated
XCNF record, and its second partial coordinate is one of the two enumerated
lookup roots. The [preflight](preflight.json) separately verifies the public
target, subgroup arithmetic, all 30 valid factor-base selectors, every
second-link group output, and byte-exact source and lookup formulas. The
planted [receipt](planted_control.json) is a correctness check; the public
target was generated independently from a scalar before the paired solver
run and that scalar was never pinned in either query.

On that one public target, the source first-link branch and its lookup-guided
version both ended `CENSORED_TIME` at their 120-second wall caps, with zero
status or model lines. The [terminal audit](audit.json) verifies both frozen
input hashes, raw logs, process identities, and drain; its `replay: null`
fields record that there was no assignment to replay.

| Arm | Formula variables | Formula records | Solver wall (s) | Sampled solver CPU (s) | Sampled combined peak RSS (B) | Terminal status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Source first-link branch | 34,334 | 52,450 | 120.106 | 18.233 | 83,869,696 | `CENSORED_TIME` |
| Exact second-link lookup | 34,365 | 54,513 | 120.245 | 20.349 | 89,997,312 | `CENSORED_TIME` |

The two attempts charged **240.351 solver-stage seconds** to the same
target. Fixture generation and target-independent formula construction were
outside these stage clocks. Both arms ran on a contended host without a CPU
isolation receipt, and the low sampled CPU time relative to wall time limits
what this comparison can say about search cost. The [frozen protocol](protocol.json),
source/lookup XCNFs, raw solver logs, [run record](result.json), and checked
Sage runtime receipt preserve the pairing and failure rows.

This control qualifies the lookup's **exactness and propagation semantics**
on a second field size, but it does not pass the ordinary-relation yield gate
for N131 promotion. The next search method must couple a backward
target-conditioned suffix constraint to the forward table. A concrete gate is
to construct and audit a reusable two-leaf suffix-sum index, then constrain
the preceding partial coordinate from the supplied public target and verify
an ordinary N41 relation on the frozen point. Only after a successful replay
and a resource preflight should the corresponding N131 query use the
600-second/4-GiB envelope. Every target-dependent lookup, failed attempt,
and relation check belongs in its charged online interval.
