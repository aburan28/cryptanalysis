# Affine shear reduces the target-coupled N41 quartic circuit

The exact substitution `T=S+Z` reduces the complete unpinned N41 public
formula to **141 quartic field multiplications and 97,994 AND gates**, from
165 and 120,929 in the prior shared-Horner emitter. The public relation
satisfies every clause and native-XOR row, and direct bit-field evaluation
replays the emitted `A,B` outputs. The frozen one-worker search is
`BOUNDED_UNKNOWN` at the 60-second solver cap. The smaller formula advances
the point-decomposition encoding but leaves the ordinary public relation
search as the algorithmic bottleneck.

## Exact transformation

For the single-branch norm `H=A²+AB+(Z+S)B²`, write `T=S+Z`. The
[compiler](circuit.py) substitutes `S=T+Z` into the original 60-term `A`
and 16-term `B`, cancelling duplicate GF(2) monomials. The transformed
polynomials have **40 and 16 terms**. It feeds `(a,T,Z,P,Q)` to a shared
sparse-Horner DAG in order `(T,Q,a,Z,P)`; the extra `wB` multiplication in
each block brings the 46-multiplication `A,B` emitter to 47 per block and
141 across the three-block public circuit. Frobenius squares remain linear.

The [transform search](transform_search.json) checks each of the 20 directed
single-variable GF(2) shears, all 120 Horner axis orders for each, and exact
involution back to the original polynomials. `S -> T+Z` has the lowest
field-multiplication count in this declared search, versus 54 per block
without a shear. The [arithmetic replay](audit_result.json) checks emitted
wires against direct monomial evaluation on the zero and unit vectors plus
fourteen fixed-seed uniform field inputs. The [complete public assignment](control_result.json)
checks all 300,683 CNF clauses and 61,612 native-XOR rows on the independently
replayed twelve-point N41 relation.

## Frozen public query and encoding variants

The exact curve is `y²+xy=x³+1` over `GF(2)[t]/(t^41+t³+1)`, with subgroup
order `549756390943`, public point `(1458168294740,1672312028033)`, actual
factor base `B=384`, and 26 signed-Frobenius columns. Twelve source masks,
three four-atom outputs and their branch choices, both target joins, all
distinct-column checks, and both raw target-lift choices are unpinned in
every search below. Each [protocol](protocol.json) fixes the same source,
public point, one CryptoMiniSat worker, 60-second solver flag with a
five-second parent margin, 120-second construction cap, and 4 GiB RSS.

| Exact public circuit | Quartic field muls | AND gates | Variables | Native-XOR rows | Query status |
| --- | ---: | ---: | ---: | ---: | --- |
| [Shared Horner](../n41_single_branch_horner_20261011/RESULT.md) | 165 | 120,929 | 196,923 | 75,634 | `BOUNDED_UNKNOWN` |
| `T=S+Z` shear | **141** | **97,994** | 159,966 | 61,612 | `BOUNDED_UNKNOWN` |
| [Half-trace branch bit](../n41_single_branch_halftrace_20261011/RESULT.md) | 141 | 97,994 | 159,783 | 61,549 | `BOUNDED_UNKNOWN` |
| [Derived output `Z`](../n41_single_branch_zelim_v2_20261011/RESULT.md) | 141 | **97,565** | **159,242** | **61,440** | `BOUNDED_UNKNOWN` |

The shear [query receipt](query_result.json) records 65.073 seconds from
solver launch through parent stop, a 7,493,192-byte XCNF with SHA-256
`5f63bc339813f8f025ef9b1337aa1b84039653ca3dbb84d283119e1eea94af25`,
and 389 logged restart rows. [Stdout](solver.stdout.gz) shows active search
through approximately 278,000 conflicts and no terminal SAT or UNSAT line;
[stderr](solver.stderr.gz) is empty. These wall intervals are exploratory on
an unisolated host. The [cross-variant audit](variant_audit.json) checks all
source hashes, matched target/resource protocols, raw log hashes, exclusive
phase sums, solver activity, formula counts, and the separately classified
derived-output producer failure.

The preceding [factored-coefficient experiment](../n41_single_branch_factored_20261011/RESULT.md)
exactly reconstructed the same polynomials but emitted at least 57 field
multiplications and 48,770 AND gates per block across all twelve of its
coefficient/product orders, so it was not promoted to a public search.
Eliminating either the 41-bit branch witnesses by half-trace or the 41-bit
output vectors by `Z=S+w²+w` changes the Boolean search representation, but
each parsed unpinned query remained active to the declared cap. The first
derived-output serialization attempt is preserved as
[`PRODUCER_FAILURE`](../n41_single_branch_zelim_20261011/RESULT.md), distinct
from the corrected bounded search.

These results direct the next method step to a target-conditioned generator
or elimination that rejects whole N131 seed/product families before their
source-mask expansion. A complete N131 public query should be promoted only
after an unpinned smaller-field relation and a source-bound one-worker,
600-second, 4-GiB projection. Relation yield, useful rank, factor logs,
fresh-target scalar recovery, and paired one-target rho online time remain
the active end-to-end gates; `candidate_id` remains `null` here.

Reproduce this non-Sage artifact from this directory with
`python3.12 -B search_transforms.py`, `python3.12 -B audit_horner.py`, and
`python3.12 -B audit_variants.py`. The frozen query commands were
`python3.12 -B run.py freeze`, then `control`, then `query`.
