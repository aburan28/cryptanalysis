# Exact six-pair public-point decomposition on N41 W8

A native three-pairs-against-three-pairs group join found an **unpinned
six-pair decomposition** of the frozen N41 transported public point. The
[independent Sage replay](audit_result.json) verifies twelve distinct folded
columns, the raw group sum, the cofactor-four projection, and a nonzero
12-term relation row of rank one against an empty matrix. The join's reusable
table preparation ended at 16.915 seconds; its target-dependent probe found
the first hit 3.781 seconds later on this unisolated host.

## Exact source and target

The curve is `y^2+xy=x^3+1` over `GF(2)[t]/(t^41+t^3+1)`, curve ID
`EC1N41Ckb1h7d5e80d3c4d0`, subgroup order `549756390943`, cofactor four.
The W8 source has 125 rational masks and 117 signed-Frobenius columns. Fixed
source-mask XOR seed 184 gives 35 pair edges whose 70 folded columns are
mutually distinct. Each edge has four signed point choices. Six slots use
Frobenius rotations `0,7,14,21,28,35`. The public input to this control is
the previously frozen transported point
`Q'=(920359962848,755404565011)`; all four of its raw preimages are
available to the join. No source masks or pair states were pinned to a known
witness.

The [Sage preparation protocol](prepare_protocol.json) hashes the geometry,
public-point fixture, checked Sage runtime, and producer before generating
the 840 signed and rotated pair states in [join_input.tsv](join_input.tsv).
It also supplies 128 independently computed group-addition checks. The
[native protocol](protocol.json) freezes that input, compiler, executable
hash, one worker, 120-second wall cap, and 4-GiB combined RSS cap before the
public query. The native code constructs the exact left and right triple
lists, excluding repeated pair edges within each triple; each list contains
2,513,280 entries. A point match is accepted only after excluding edge reuse
across both halves and checking the full raw group sum.

| Phase or check | Recorded result |
| --- | ---: |
| Native-versus-Sage group additions | 128/128 passed |
| Left triple list | 2,513,280 entries; 11.420 s cumulative |
| Right triple list | 2,513,280 entries; 16.915 s cumulative |
| Raw preimage 0 target probe | Hit after 1,136,882 right-list probes; 20.696 s cumulative |
| Target-dependent probe interval | 3.781 s exploratory native time |
| Full parent wall and sampled combined peak | 23.833 s; 372,736,000 bytes |
| Independent source, raw-sum, projection, and row replay | `PASS_INDEPENDENT_N41_PUBLIC_SIX_PAIR_RELATION` |
| Distinct folded columns / rank from empty matrix | 12 / 1 |

The exact six state IDs are `75,6,99,63,44,106`; their source masks, signs,
rotations, and relation coefficients modulo the subgroup order are in the
[audit](audit_result.json). The [query receipt](query_result.json) preserves
exclusive native phase lines, process limits, stdout/stderr hashes, and the
solver input hash. The query is a point-decomposition and relation stage;
factor-base logs, matrix rank beyond this row, target scalar recovery, and
matched rho timing remain subsequent pipeline stages. `candidate_id` remains
`null` until the complete pipeline is specified.

## Degree-131 transfer boundary

The [exact source projection](projection_result.json) counts 2,339,923,058,062,080
distinct-column ordered three-pair states for the N131 W18 seed-212 source.
Storing only a 16-byte key for each would need more than 37 PB, before hash
and witness overhead. Its six-pair uniform raw-point mean upper ceiling is
about `2.01e-9`; eight pairs reach about 35.43 but require an even larger
explicit half-list. Thus this exact join establishes an ordinary N41
decomposition and a small-field full-pipeline building block, while the
N131 step requires an implicit or algebraically compressed family join.

The next small-field experiment should retain the reusable triple table,
collect independently verified known-scalar relation rows until the 117
folded-column log system reaches full rank, solve those logs, and recover a
new public target scalar. For N131, a candidate family operator must avoid
materializing the three-pair table and still produce verified ordinary rows
under the frozen one-worker budget.
