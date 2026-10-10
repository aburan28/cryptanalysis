# N41 repeated-pair relation and target-conditioned hybrid gate

Five repeated W5 rotations yield an **exact ten-column relation on the frozen
degree-41 public point**, and an independent checked-Sage replay verifies the
raw sum, cofactor-four projection, and Frobenius transport. The associated
target-conditioned SAT hybrid has a full public-relation XCNF witness. Its
unpinned 60-second query reached the solver cap, which identifies pair-output
selection rather than the fifth leaf-product multiplication as the next
search bottleneck.

The curve is `EC1N41Ckb1h7d5e80d3c4d0` over
`GF(2^41)` with polynomial `t^41+t^3+1`, subgroup order
`r=549756390943`, and public point
`Q=(1458168294740,1672312028033)`. The factor base uses 17 rational W5
masks per selected rotation. The ten leaf slots have rotations
`[0,0,8,8,16,16,24,24,32,32]`, giving **B=170 distinct usable points**
before folding and **K=14 signed-Frobenius columns**. A row requires all ten
columns to be distinct. The [source protocol](protocol.json) freezes the
input, geometry, native binary, one target, and 60-million-probe,
600-second, 4-GiB search envelope.

The exact native 4+6 join found a relation after 15,847 accepted right-side
probes (51,748 right attempts) and 2.054 seconds of native wall time. The
[native result](run/result.json) and [hit](run/hits.jsonl) record the masks,
signs, columns, and raw sum `(661039828953,605809857607)`. The
[checked-Sage replay](sage_audit.json) independently reconstructs every leaf
from its rational mask and sign, verifies the ten distinct folded columns,
and checks that the cofactor-four projection followed by `1+φ` is `Q`.
This wall observation is exploratory on an unisolated host.

| Same-point stage | Result |
| --- | ---: |
| Canonical row order, accepted probes to first ten-column relation | 15,847 |
| Four independent row-order repeats, accepted probes each | 2,000,000 |
| Repeat statuses | 4 × `CENSORED_PROBES` |
| Repeat group hits / repeated-column rejects | 12 / 12 |
| Exact pair rows / unique pair sums per rotation | 1,056 / 528 |
| Left four-state rows / unique raw sums | 764,544 / 191,136 |

The [repeat protocol](repeat_protocol.json) changes only the order of the
same 34 states in each leaf block, preserving the public point, factor base,
native kernel, and resource cap. All four [repeat rows](repeat_result.json)
reached their two-million-probe caps with their individual failures retained.
Thus the early canonical hit is an exact existence witness, while the repeat
panel gives a more cautious view of relation yield. The
[pair image count](pair_analysis.json) shows that exchanging the two leaves
within a repeated pair duplicates each pair sum twice; two such exchanges
duplicate each left four-state sum fourfold. The image count is exact for
this input, not an estimate of the ten-column relation rate.

The hybrid keeps four leaf S3 links exact. In the fifth link it substitutes
an independent nine-bit polynomial `P` in the degree-2 through degree-10
product span of the W5 source for the exact product `w_a w_b`, while retaining
the S3 equation

`P (z^2+z) = (u_a+u_b+z)^2`.

This gives the upper S3 chain a target-conditioned choice of the fifth pair
output. Any SAT model still requires exact pair inversion and raw group
replay before it can become a relation. The [hybrid protocol](hybrid_protocol.json)
freezes this construction and the one-worker CryptoMiniSat query. The
[public-point preflight](preflight.json) completes every auxiliary wire for
the independently replayed relation and checks all 30,635 CNF clauses and
8,019 native-XOR rows. A matched [exact-formula control](formula_comparison.json)
uses the same point, base, rotations, and witness:

| Matched N41 same-pair formula | Exact fifth pair | Relaxed fifth pair |
| --- | ---: | ---: |
| Variables | 18,089 | 18,066 |
| CNF clauses | 30,710 | 30,635 |
| XOR rows | 8,026 | 8,019 |
| AND gates | 9,681 | 9,656 |
| Full public-relation assignment | pass | pass |

The relaxation removes 25 AND gates and 75 clauses, only about 0.26% and
0.24% of the respective exact-formula totals. The [unpinned query](query_result.json)
logged 336 search restarts and ended `CENSORED_TIME` at the 60-second parent
cap, with zero model lines and empty stderr; sampled solver RSS peaked at
91,013,120 bytes. This is a capped search observation, not a solver-time
ratio. The [terminal audit](terminal_audit.json) binds source, input, formula,
solver log, replay, pair image, and repeat receipts. The first exact-formula
comparison script had an import-name collision, and the first native image
counter included a duplicate `main`; their
[failure](comparison_failure_v1.json) and
[failure](pair_analysis_failure_v1.json) receipts are preserved before the
corrected controls.

This remains an IC design stage with `candidate_id: null`. The next method
gate is a target-conditioned **exact pair-output index**: use the upper
chain to propose a fifth-pair output, apply the W5 inverse lookup before
expanding mask/sign branches, and measure ten-column verified relations and
novel rank on ordinary queries. The challenge-width transfer should use the
audited W14 same-rotation inverse and retain the one-target online and
same-point rho measurements as separate final gates.
