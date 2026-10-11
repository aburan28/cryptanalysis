# N83 sorted-leaf ordinary S3 result

Q20261010180700 adds an exact four-leaf ordering constraint to Q1408's
archived balanced S3 formula. The comparator passed all 64 three-bit
truth-table cells. The existing N83 normal-x weight≤5 base supplies
`B=30,977,592` actual usable points and `K=186,612` folded columns on
`EC1N83Ckb1h876c2921cb64`, with ordinary workload `Wbab50a1e5f66`.
The base, public point, and original formula bytes are SHA-256 pinned.

| N83 formula | Variables | CNF clauses | Native XOR rows | AND gates added |
| --- | ---: | ---: | ---: | ---: |
| Q1408 archived | 65,221 | 189,928 | 1,245 | — |
| Sorted leaves | 65,710 | 190,906 | 1,491 | 0 field gates; 243 comparator gates |

The new formula adds 489 variables, 978 CNF clauses, and 246 XOR rows.
Its initial 100,001-conflict solver cell returned `INDETERMINATE` after
20.36 wall seconds and 15.09 child CPU seconds, with 272.3 MB peak child
RSS. The solver ended at its conflict limit, not the 300-second wall cap.
The receipt auditor passed; there was no SAT model or verified relation
under this cap. Q1408's unsorted N83 ordinary cell reached 1,000,001
conflicts without a model, so these unequal conflict caps do not establish
an improvement or regression in relation-finding cost. Shared-host wall
time is exploratory.

Q20261010181200 replayed the identical sorted formula with a
one-million-conflict solver limit. Host contention caused the **600.15-second
external wall cap** to fire after 89.44 child CPU seconds. The last archived
restart line displays about `705K` conflicts; the solver did not print an
exact final conflict count before being killed, so `conflicts_reported` is
null in the run receipt. Peak child RSS was 269.5 MB. The independent
receipt auditor passed. This row remains `BOUNDED_UNKNOWN` and does not
provide a matched one-million-conflict outcome against Q1408.

The next discriminating cell needs enough allocated child CPU on a less
contended host to reach a model or the declared one-million-conflict limit.
If a verified relation appears, repeat on independent ordinary public
points and measure rank novelty before projecting a degree-131 `2^x`
total. A complete projection must also charge base construction, all
failed PDP calls, relation checking, final relation-matrix algebra, target
descent, and recovery verification.
