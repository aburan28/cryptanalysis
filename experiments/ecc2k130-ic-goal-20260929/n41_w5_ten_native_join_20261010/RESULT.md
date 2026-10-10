# Exact ten-source relation on the degree-41 public point

An exact native 4+6 group join found a **ten-source relation with ten
distinct signed-Frobenius columns** on the frozen degree-41 public point
`Q=(1458168294740,1672312028033)` of
`EC1N41Ckb1h7d5e80d3c4d0`. An independent checked-Sage replay verifies
the ten raw points, their sum, cofactor-four projection, and
`(1+φ)` transport to `Q`. The same relation completes and satisfies
**every clause and native XOR row** of the previously archived unpinned
public-point XCNF, whose one-worker CryptoMiniSat attempt reached its
115-second solver cap. This separates support and encoding correctness
from the observed SAT search cost on this point.

The factor base is the audited W5 ten-rotation base with `B=340` usable
projected subgroup points and `K=14` folded columns. The native program
indexed 764,544 four-state sums whose four columns are distinct, then
sampled distinct-column six-state tuples against the four exact raw
preimages of `Q'=(1496345304064,1421510518509)`. It found the first
ten-distinct-column relation after 22,708,746 accepted six-state probes.
The native group matcher encountered 28 group hits, rejected 27 for
repeated columns, and independently replayed the accepted raw sum
`(661039828953,605809857607)` at target-preimage index 1.

| Frozen one-target stage | Observation |
| --- | ---: |
| Native four-sum index | 764,544 distinct-column entries |
| Accepted six-state probes / group hits / column rejects | 22,708,746 / 28 / 27 |
| Native wall / peak RSS | 172.644 s / 45,236,224 B |
| Checked-Sage group replay | pass |
| Archived public XCNF assignment | pass, 47,462 CNF clauses and 11,249 XOR rows |
| Earlier public CryptoMiniSat attempt | `CENSORED_TIME`, 115.426 s online |

The [frozen protocol](protocol.json), [export receipt](export_receipt.json),
and committed [native input](input.txt) bind the same public point and
factor-base policy as the SAT gate. The native [result](run/result.json),
[relation](run/hits.jsonl), [checked-Sage replay](sage_hit_audit.json),
[archived-formula assignment check](formula_hit_audit.json), and
[terminal audit](terminal_audit.json) retain the source and result hashes.
The search used one native worker, a 60-million accepted-probe cap,
600-second wall cap, and 4-GiB RSS cap. Its wall time is exploratory on
an unisolated host. A first input-export attempt used a Python environment
without the imported runner's dependency; the
[pre-export failure receipt](export_failure_v1.json) is retained.

This exact join is a lower-field extraction control. On the audited N131
W14 ten-source geometry, one block has 16,440 signed states, so a literal
four-state index has `16,440^4 = 73,047,818,856,960,000` combinations.
Even eight bytes per entry would require about 584 petabytes before hash
structure, making the N41 table representation unsuitable at challenge
width. The next method gate is a compressed or algebraic decomposition
kernel that can exploit the denser W14 ten-source support without building
that table, followed by an unpinned N131 relation and useful-rank
measurement. This stage remains a `Q` proposal with `candidate_id: null`.
