# Exact six-pair order quotient in the N131 W15 public circuit

Ordering the two masks inside each of the six pair slots removes an
exact `2^6=64` source symmetry. The frozen N131 circuit adds only **90
CNF clauses**: it reuses mask-difference wires already present for the
twelve-column distinctness check, so its variable count, native-XOR
rows, and AND-gate count are unchanged. The constructed complete XCNF
assignment and raw group lift pass. On the same published ECC2K-130
point, the one-worker public query records `CENSORED_TIME` after
592.109 s of construction plus search under the 4-GiB cap. The quotient
is exact, while this measured encoding did not clear the ordinary
relation gate.

The curve is `EC1N131Ckb1heb5f1998f20b` over
`GF(2)[t]/(t^131+t^13+t^2+t+1)`, with subgroup order
`680564733841876926932320129493409985129`. The W15 source has
197,292 usable factor-base points and 16,381 folded columns. Two pair
mask-XOR seeds are fixed at 12004 and 9022; the remaining four pairs
are free. The full IC pipeline remains proposal-stage, so the
[frozen protocol](protocol.json) records `candidate_id: null`.

## Exact symmetry quotient

Each pair contains two distinct folded columns, hence two distinct
masks. Swapping its source masks and signs preserves its point sum,
mask XOR seed, mask product, output coordinate, and every upper S3
link. The two fixed-seed product formulas are symmetric as well:
if `s=a+b`, then `a(a+s)=ab=b(b+s)`. The six pair swaps therefore act
freely, and every valid ordered twelve-leaf relation has one
representative with all six numeric masks strictly increasing inside
their pairs.

For each pair, the [circuit](circuit.py) reuses its 15 existing XOR
difference wires. At bit `i`, one clause forbids left bit 1 and right
bit 0 if all more significant bits agree. The highest differing bit
therefore decides the order; the existing mask-inequality clause
excludes equality. The [semantic audit](lex_semantics.json) checked
all 65,536 ordered pairs at width eight, 200,000 seeded pairs at width
15, and all 64 orientations of the constructed six-pair witness. Its
exact source count is
`362600299349653173913409403528217168496640` signed tuples, or
**532.793** per uniform subgroup target before intermediate filtering.
This is one sixty-fourth of the independently audited ordered source
count, not a measured ordinary relation yield.

## Frozen control and public run

The [constructed control](control.json) passes a complete XCNF
assignment and [group lift](control_group_lift.json). The public target
is the previously published subgroup point
`(2309658012506412099988466246134815930289,
1578526100003023531340803776621036465818)`.

| Same-target public gate | Previous two-seed circuit | Pair-order quotient |
| --- | ---: | ---: |
| Variables | 117,252 | 117,252 |
| CNF clauses | 424,423 | 424,513 |
| Native-XOR rows | 42,855 | 42,855 |
| AND gates | 72,903 | 72,903 |
| Formula construction | 3.932 s | 22.044 s |
| Solver interval | 588.180 s | 570.065 s |
| Construction plus search | 592.112 s | 592.109 s |
| Query status | `CENSORED_TIME` | `CENSORED_TIME` |
| Sampled combined peak RSS | 685,441,024 B | 485,801,984 B |

Both used one CryptoMiniSat worker, the same point, the same solver
flags, a 600-s construction-plus-search cap, and 4-GiB RSS cap. The
wall and RSS differences are exploratory host diagnostics without CPU
isolation; the terminal statuses determine this gate. The constructed
control validates encoding correctness but is separate from natural
query yield.

The [terminal audit](terminal_audit.json) rehashes and recounts the
complete [public XCNF](system.xcnf.gz) and [control XCNF](control.xcnf.gz),
binds [result.json](result.json) to the [solver log](solver.stdout.txt),
and verifies that the previous formula's clauses and native-XOR rows
are byte-identical apart from exactly the 90 new order clauses. Those
clauses have SHA-256
`5d5574f5ba0ca1d323f9e1e4c66dffea42c4eea143d641806522595001d9ee60`
on both frozen inputs. Run `python3 -B audit_archive.py` from this
directory for a read-only replay using only committed artifacts.

The next full-relation solver should propagate the public target
through multiple pair-output families before mask expansion. The
existing [unpinned N41 seed-partitioned
join](../n41_seed_partition_indexless_20261010/RESULT.md) supplies an
independently replayed twelve-point control; its explicit
constrained-block Cartesian loop is the operation to replace before
another N131 public query.
