# Ordered free leaves in the N83 width-18 five-summand circuit

The Q64 circuit orders the four interchangeable free leaves by their unsigned
raw x coordinates. A locked five-point control remains SAT and passes group
replay in an independent Sage polynomial field. The ordinary public-target
attempt reached its 600-second wall cap with stage status `bounded_unknown`.
The constraint added 243 AND gates and 978 CNF clauses to Q54's exact
width-18 formula; it did not yield a verified ordinary relation under the
frozen cap.

| Same base, target, Karatsuba links, solver and caps | Q54 | Q64 ordered x |
| --- | ---: | ---: |
| Usable subgroup points before folding, `B` | 21,714,958 | 21,714,958 |
| Signed-Frobenius columns, `K` | 130,813 | 130,813 |
| AND gates | 12,174 | 12,417 |
| CNF clauses | 105,251 | 106,229 |
| Native XOR rows | 62,937 | 63,183 |
| Ordinary target stage | `bounded_unknown` | `bounded_unknown` |
| Solver stop | 5,000,001 conflicts | 600-second external timeout |
| Local solver interval | 336.204 s | 599.622 s |

The exact comparison variable is three lexicographic comparators on free
leaves 1–4. Each comparator examines the 83 raw x bits from most to least
significant and forbids a first differing bit of `1 > 0`. The first leaf
remains normalized to an affine seed. Sorting cannot remove a group solution:
the free leaves draw from the same factor base, and adjacent swaps preserve
their sum. [FreeLeafSymmetry.lean](FreeLeafSymmetry.lean) checks the three
adjacent-swap equations under explicit associativity and commutativity
hypotheses. [Lean output](lean-build.txt) reports no axioms for those
declarations. The exact curve/factor-base closure and circuit encoding are
validated by the locked control and independent Sage replay; their bridge to
the generic Lean laws is not formalized here.

The [protocol](protocol.json) fixes the Q54 public workload
`df4396f4d8fc`, shifted width-18 base and canonical-x cache, CryptoMiniSat
binary, one thread, five-million-conflict cap, 600-second wall cap, and 4 GiB
sampled solver RSS stop. Its target-generation scalar appears only as a hash
commitment. The [attempt receipt](width18_ordinary.json) preserves the
`external_timeout` status, compressed XCNF, solver stdout/stderr, memory
sample, and exclusive target-dependent phases. The solver progress log reached
about 4.856 million conflicts near the timeout; `conflicts_reported` remains
null because the process did not print a terminal total. The 336- and
600-second local runs lack host isolation, so their wall-time ratio is
exploratory and no controlled speedup is inferred.

[Independent Sage replay](sage_relation_replay.json) checked the planted
relation and records `no_relation_to_replay` for the ordinary attempt. The
checked local Sage launcher saved [runtime identity](sage_runtime_info.json)
before execution. Run the read-only receipt audit from the repository root:

```sh
python3 experiments/n83-geometric-m5-ordered18-20261012/verify.py
```

The result discourages raw-x comparators as the next solver variant. A
cheaper symmetry constraint can compare the 18 affine seed bits directly;
that preserves the same interchangeability while placing clauses on primary
choice variables. It needs its own planted control and ordinary-query run.
