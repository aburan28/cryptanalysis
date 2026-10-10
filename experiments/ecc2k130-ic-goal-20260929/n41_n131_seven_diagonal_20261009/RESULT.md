# Seven Frobenius-diagonal blocks: exact public-point relations and transfer gate

Seven same-sign Frobenius pairs reduce fourteen raw summands to seven rational
diagonal outputs. For a source parameter `w`, each output has transformed
coordinate `z = w/(w+1)`. On the frozen N41 public point, a complete 3+4 group
join found **three** distinct-column relations. The checked Sage build replayed
all fourteen leaves, every intermediate group sum, and the public target for
each row. After signed-Frobenius folding, the three rows have rank three with
the target column; their differences give **two** independent factor-base
relations. This establishes both geometric support and useful rank for the
seven-block construction on the ordinary N41 query.

| Quantity | Frozen N41 result |
| --- | ---: |
| Field, subgroup | `GF(2^41)` with `t^41+t^3+1`; `r=549756390943` |
| Public target `Q` | `(1458168294740, 1672312028033)` |
| Source masks / signed states per block | 32 / 64 |
| Actual subgroup-usable factor-base points `B` / folded columns `K` | 812 / 26 |
| Seven-block projected group hits | 10 |
| Folded-column rejects / verified relations | 7 / 3 |
| Augmented row rank / factor-base-only difference rank | 3 / 2 |
| Complete right-side probes | 16,777,216 |
| Native join wall / peak RSS | 2.539 s / 25,526,272 bytes |
| SAT ordinary query | `CENSORED_TIME`, 115.114 s online, 0 model lines |

The native join's clock includes its 262,144-entry left-table construction and
the target-dependent scan; input export and process launch are outside it.
Its 2.539-second wall time is a stage diagnostic on an unisolated ARM64 host,
not a calibrated IC comparison. The SAT online interval includes target
preimages, formula construction, and the one-worker CryptoMiniSat search. Its
frozen 120-second online, 115-second solver-parent, and 4-GiB RSS limits are in
[`protocol_v2.json`](protocol_v2.json); the unmodified terminal records are in
[`public/result.json`](public/result.json) and the
[`terminal audit`](terminal_audit.json). The solver was searching an XCNF with
28,480 variables, 50,195 CNF clauses, 11,795 native XOR rows, and 16,147
AND gates. The [`public XCNF audit`](full_formula_join_audit.json) completed
each of the three relations to a full assignment satisfying all 50,195 CNF
clauses and 11,795 native XOR rows. Thus the timed-out ordinary query has
three explicit admissible assignments in its exact saved formula.

The source, public-point input, 300-second/4-GiB join policy, and executable
hashes were committed before the native query in `af8226abdb212e76be08a869b1c88588f9508266`.
The [`join receipt`](join_result.json) records exhaustive completion and the
[`checked-Sage replay`](sage_join_audit.json) checks the raw group chain.
The [`rank audit`](sage_rank_audit.json) derives the Frobenius eigenvalue on
the subgroup, replays each folded row as a group equation, and computes rank
modulo `r`. The earlier planted full-formula assignment and group control are
in [`preflight/receipt.json`](preflight/receipt.json) and
[`sage_preflight_audit.json`](sage_preflight_audit.json).

The exact N131 W19 source geometry gives 262,390 rational source masks and
524,780 signed states per diagonal block. A literal 3+4 join would have
144,521,288,719,352,000 left triples; **eight bytes per left key alone**
requires 1,156,170,309,754,816,000 bytes, before point values and index
overhead. Its unrestricted right side has 75,841,881,894,141,542,560,000
probes. The uniform-group count `524780^7/r` is about 16.1054 raw tuples,
an input-law heuristic rather than a measured N131 relation yield. Exact
seven-rotation factor-base union size and folded column count remain to be
enumerated. These boundaries and source hashes are in the
[`transfer audit`](transfer_result.json).

**Next method gate:** derive a target-coupled seven-block elimination or
implicit completion oracle that avoids materializing the N131 cubic table and
scanning the quartic side. On this frozen N41 point it must recover a row with
an independently replayed group equation and report full work, memory, and
rank. Advance to the published N131 point only after a source-bound N131
projection fits 600 seconds and 4 GiB, then charge relation collection,
final matrix solve, target descent, and a matched one-target rho reference
under the project measurement contract. The seven-block method remains a
`Q` proposal with `candidate_id: null` until that complete pipeline is fixed.
