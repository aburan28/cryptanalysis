# N83 weight-three-or-four SAT pilot: planted gate failed

The [frozen protocol](n83_w34_sat_protocol.json) asks whether a compact
implicit four-equation S3 chain can find a five-summand decomposition on the
complete N83 weight-three-or-four base. This is a point-decomposition pilot,
not a complete index-calculus candidate: `candidate_id: null`. The exact curve
is `EC1N83Ckb1h2bcb59d56ad6`. The [public fixture](runs/n83_w34_sat_fixture_v1/public_input.json)
fixes both a planted target and a separate ordinary target before solver work.
The planted masks, raw point witnesses, and fixture scalar are kept in a local
ignored file; they are not inputs to an unpinned solve or published results.

The fixture producer and an independent checked-Sage replay verified the
planted five-point group sum, all four cofactor-four target fibers, the
ordinary target, and membership of the five factors in the measured base.
The protocol's first search gate fixes the five planted factor x masks and
asks CryptoMiniSat to solve the remaining circuit on the correct raw-target
fiber. This deliberately easier positive control must pass before an
unpinned planted search or ordinary query.

## Frozen search result

The pinned branch built 98,846 Boolean variables, 92,322 AND gates, 277,748
CNF clauses, and 5,855 XOR rows. Its XCNF file was 5,816,842 bytes. The
bounded search receipt recorded 0.532 seconds for circuit construction.

| Attempt | Result | Meaning |
| --- | --- | --- |
| First launch | No circuit | The system Python did not have the required `psutil` package. |
| Second launch | `ERROR` | macOS rejected the attempted `RLIMIT_AS` setting before circuit construction. |
| Third launch | `BOUNDED_UNKNOWN`; outer guard invalid | The sandbox denied process-tree inspection; the inner 45-second watchdog still stopped the solver. |
| Fourth launch | **`BOUNDED_UNKNOWN`**; outer guard complete | Checked Sage and the process-tree RSS watchdog ran. CryptoMiniSat emitted neither SAT nor UNSAT before the 45-second external watchdog killed it. |

The fourth run is the resource-valid search attempt. The solver was configured
for one thread, 30 seconds of its own time, 200,000 conflicts, and a 2 GiB
RSS ceiling. The external 45-second watchdog fired after 45.039 seconds of
solver wall time. Peak sampled process-tree RSS was 107,823,104 bytes, below
the ceiling. The solver did not emit final decisions, conflicts, propagations,
or restarts, so those totals are **unknown**. The watchdog receipt finished
successfully; the SAT branch itself did **not** solve. All timing is
exploratory on an unisolated host.

Separately, the [known-witness audit](audit_n83_w34_known_witness.py) built
the same pinned circuit, assigned all 98,846 variables from the five raw
points and their three intermediate sums, and checked every CNF clause and
XOR row. It passed in 1.261 seconds with 121,257,984 bytes peak RSS. It also
checked that the raw sum projects to the frozen public subgroup target. This
proves that the planted assignment satisfies this circuit. It does not prove
that every circuit solution corresponds to a valid group decomposition;
that ideal-equivalence control remains open.

## Decision

The frozen pinned positive control failed its bounded search gate. Therefore
the unpinned planted branches and ordinary target were **not run**. There is
no measured natural relation yield, verified ordinary relation, factor-base
log system, single-target DLP, paired rho reference, or IC speedup. The
primary one-target online time and speedup are unknown. The complete base's
five-summand multiset/r ratio of 93,832.98 is a counting diagnostic, not a
solver success probability.

The next solver work should first make the planted branch solve under a
frozen limit, then independently replay any model as a five-point group sum.
The small exhaustive S3/point-lift equivalence control must also pass before
an ordinary query. A larger timeout alone would not establish either gate.
The local immutable search and audit receipts live under
`/Volumes/SSD990/llm/tmp/n83_w34_sat_pinned_v4` and
`/Volumes/SSD990/llm/tmp/n83_w34_known_witness_audit_v1`; those directories
contain private-derived data and are intentionally excluded from this PR.
