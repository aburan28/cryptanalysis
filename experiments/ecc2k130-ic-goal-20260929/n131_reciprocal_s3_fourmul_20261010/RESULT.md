# Four-multiplication reciprocal S3 circuit

Computing the second elementary symmetric sum as `uv+w(u+v)` reduces each
degree-131 reciprocal S3 link from five field multiplications to four. The
eight-pair, seven-link circuit on the exact ECC2K-130 challenge field drops
from 602,369 to 517,242 live Boolean IR operations, with the same source
masks and public target. This is an exact circuit-size improvement: the Sage
symbolic identity and 18 full-field input checks pass, as do the constructed
curve row and a complete independent XCNF model audit.

The field is `GF(2^131)` with modulus `t^131+t^13+t^2+t+1`; the curve is
`y^2+xy=x^3+1`, and the prime subgroup order is
`680564733841876926932320129493409985129`. The source is the fixed-seed
W18 pair policy with seed 212 and eight rotations used in the
[baseline experiment](../n131_fixed_seed_eight_pair_circuit_20261010/RESULT.md).
The single public target has workload ID `cc09e7eb202a`; both circuits fix
preimage index 0 of that exact target.

Writing `s1=u+v+w`, `s2=uv+uw+vw`, and `t=uvw`, the reciprocal link is

```text
G(u,v,w) = (t+s1)^2 + t(s2+s1+1).
s2 = uv + w(u+v).
t  = (uv)w.
```

The four field multiplications are `uv`, `w(u+v)`, `(uv)w`, and
`t(s2+s1+1)`. Squaring and addition are GF(2)-linear. The revised
[fourmul.py](fourmul.py) leaves the eight pair equations, BDD membership,
Frobenius rotations, six intermediate coordinates, and target input unchanged.
The [link equivalence receipt](link_equivalence_result.json) checks the
identity as a polynomial over GF(2), then compares both IR circuits with a
direct degree-131 field evaluation on two edge cases and 16 seeded triples.

| Identical source and target configuration | Five-product links | Four-product links |
| --- | ---: | ---: |
| Field multiplications per S3 link | 5 | 4 |
| Live IR operations, all seven links | 542,871 | 457,744 |
| Live IR operations, full 16-summand circuit | 602,369 | 517,242 |
| Ordinary-target XCNF variables | 889,295 | 811,425 |
| Ordinary-target CNF clauses | 763,388 | 688,202 |
| Ordinary-target native XOR rows | 633,524 | 580,716 |
| Constructed relation XCNF | SAT, independently audited | SAT, independently audited |

The full IR operation reduction is 85,127 (14.1%). The four-product
ordinary-target formula has 77,870 fewer variables, 75,186 fewer CNF
clauses, and 52,808 fewer native XOR rows. These exact counts come from the
[baseline build](../n131_fixed_seed_eight_pair_circuit_20261010/full_ordinary_build.json)
and [new build](fourmul_ordinary_build.json). The constructed formula solved
in 1.855 seconds on this exploratory host; its
[audit](constructed_audit_result.json) independently checked all 690,172
clauses and 581,210 XOR rows and recovered the frozen source masks and
intermediate values. The old constructed formula's 2.020-second timing is a
separate correctness diagnostic, not a controlled CPU performance ratio.

The four-product chain's ordinary-target run used the same CryptoMiniSat5
binary, one thread, 600-second solver cap, 615-second parent cap, and 4 GiB
RSS cap as the baseline. It entered search and reached `PARENT_TIMEOUT` at
615.060 seconds with about 879,000 logged conflicts and peak RSS of 552.8 MB.
The [protocol](ordinary_solver_protocol.json), [solver result](ordinary_solver_result.json),
and raw stdout preserve its censored `BOUNDED_UNKNOWN` status. The higher
conflict count than the larger circuit is a search diagnostic, not a recovered
relation or a controlled wall-time speedup.

## Balanced link topology

The same four-product links can be wired as four first-level pair sums, two
second-level sums, and one root link, reducing S3 depth from seven to three.
The [balanced IR receipt](balanced_result.json) checks the exact constructed
group row and gives the same 517,242 live operations as the chain. Exact Sage
group replay supplies its six intermediate coordinates in
[balanced_planted_result.json](balanced_planted_result.json). The balanced
ordinary formula has the same variable, clause, and XOR counts as the chain,
with a different formula hash. Its constructed model solved and independently
passed all 1,271,382 constraints in
[balanced_constructed_audit_result.json](balanced_constructed_audit_result.json).
The balanced ordinary-target run also entered search and reached
`PARENT_TIMEOUT` at 615.041 seconds, with about 405,000 logged conflicts and
peak RSS of 536.4 MB. Its
[protocol](balanced_ordinary_solver_protocol.json),
[result](balanced_ordinary_solver_result.json), and raw stdout preserve the
censored `BOUNDED_UNKNOWN` status. The two topologies have identical formula
counts and resource caps, but their conflict counts are search diagnostics on
this unisolated host; neither provides an ordinary relation at the recorded
limit. Balancing alone did not clear this gate.

The candidate ID remains `null`: these are point-decomposition circuit stages.
The next pipeline gates are an ordinary verified relation, measured relation
yield and rank novelty, factor-log recovery, and matched single-target rho
accounting. A concrete next point-decomposition gate is a seven-pair W20
source: it would use six S3 links and 133 free source-selector bits rather
than seven links and 136 bits here. Its W20 rational support, folded columns,
cross-slot distinctness, and actual factor-base cost must be enumerated first;
the wider base may increase sparse LA cost. Freeze the same public point and
resource cap before comparing its ordinary search with these receipts.
