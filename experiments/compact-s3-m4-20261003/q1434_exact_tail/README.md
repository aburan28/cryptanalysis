# Q1434: exact sparse-tail membership after cached S3 span

Q1433 left both ordinary N53 and N83 target queries censored after 300
seconds. Q1434 changes the Q1432 solver rather than extending its cap. It
keeps the same CNF, public targets, curves, normal-basis factor bases, and
decision policy, and adds an exact test to partial second-pair leaves. The
[protocol](protocol.json) was frozen before all four solver runs.

When a leaf has one remaining Hamming-weight unit, its possible completion
is its fixed-one mask or that mask plus one free basis bit. With `k_a` and
`k_b` free bits, the second pair has exactly `(1+k_a)(1+k_b)` candidate
completions. Q1434 runs the exact test only after Q1432's necessary span test
accepts, with `k_a,k_b <= 14` at N53 or `<= 20` at N83. Thus it tests at
most 225 or 441 pairs per eligible state. For fixed second intermediate
`m`, it evaluates each pair using Q1432's exact expansion

`S3(a,b,m) = c + Σ u_i α_i + Σ v_j β_j + Σ u_i v_j γ_ij`.

The cached coefficients are charged to the field-operation counters. If no
candidate satisfies `S3=0`, the solver rejects the state under every fixed
leaf bit and all bits of `m`. If exactly one candidate satisfies it, the
solver forces every remaining leaf bit to that candidate under the same
guard. Multiple candidates leave the state unchanged. These clauses are
solution-preserving because every weight-allowed continuation is enumerated;
the test does not assume that `S3` alone proves a four-point relation.

The [60-case validation](tail_validation.json) compares native counts and
unique coordinates with direct Sage `S3` enumeration on archived ordinary
trails, synthetic states, and completions of independently verified N53/N83
witnesses. It found 44 zero-completion and 16 unique-completion cases, with
zero false rejections of verified witnesses. The [archive verifier](verification.json)
replays both complete controls and samples emitted zero-completion claims
from the solver trails using direct Sage arithmetic.

| Degree | Curve ID | Actual factor-base points `B` | Folded columns `K` |
| --- | --- | ---: | ---: |
| 53 | `EC1N53Ckb1hf77aab617904` | 24,062 | 227 |
| 83 | `EC1N83Ckb1h876c2921cb64` | 30,977,592 | 186,612 |

Exact field, curve, subgroup, base digest, target, and stage configuration
are in the protocol. This remains proposal `Q1434`, with
`candidate_id: null` and `isogeny: "none"`; its `PS1...PDP4theory...` labels
are stage IDs, not complete `IC1` candidates.

## Frozen result

Both known-witness controls returned independently verified four-point
relations. Both unpinned ordinary queries were censored at the frozen
60-second cap, with no verified relation. The host lacked an isolation
receipt, so wall times are exploratory.

| Ordinary query | Span checks / rejects | Exact tail checks / rejects | Exact candidate pairs | Total field mul / sqr / inv | Peak child RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| N53 | 318,949 / 262,098 | 42,903 / 42,903 | 8,538,981 | 2,036,720 / 4,062,950 / 50,071 | 723,238,912 bytes |
| N83 | 83,682 / 80,344 | 3,180 / 3,180 | 1,390,796 | 1,372,405 / 8,190,348 / 76,631 | 588,398,592 bytes |

Every ordinary exact-tail check found zero completions; none emitted a
unique-completion clause. The exact-tail field multiplication counts were
171,612 at N53 and 12,720 at N83, including construction work charged by
the check. The cached span checks used another 1,305,687 and 420,478 field
multiplications. Q1432's matched 60-second prefixes used 1,457,636 and
1,296,699 total multiplications, but the prefixes differ. Q1434 makes more
search decisions and costs more arithmetic in its capped prefixes; those
facts do not establish an isolated wall-time speedup or a solved-query cost.

There is still no measured ordinary decomposition at N53 or N83 from this
solver, no natural relation yield or useful-row rate, and no justified
complete N131 `2^x`. These censored rows give lower bounds only for the
specific attempts and caps.

## Next gate

The exact test is effective once both leaves are nearly complete, but it
acts late. A useful next goal is **earlier target-conditioned sparse-pair
membership with witness recovery**. The immediate Q1435 experiment should
extend exact completion to states with one or two weight units left on each
leaf, using a preregistered candidate-count cap and charging all coefficient
construction, enumeration, clauses, and memory. It should report how often
the new gate runs before the reverse-root loop and whether it reaches an
independently verified ordinary N53 relation. If it remains censored, the
next design must couple both pair constraints through the public target
before late leaf enumeration. Another longer cap on the unchanged Q1434
search would add a lower bound without a measured cost per successful query.

The N83 gate is a verified ordinary relation on the exact N83 base, followed
by fresh frozen queries to estimate natural yield and useful rank. Only then
can query cost be combined with factor-base construction, relation
collection, final matrix work, target descent, and scalar replay for a
complete N131 work projection.

## Reproduction

From this repository checkout:

```sh
python3 experiments/compact-s3-m4-20261003/q1434_exact_tail/build_binaries.py --rebuild
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1434_exact_tail/validate_tail.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1434_exact_tail/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1434_exact_tail/verify_archive.py --require-complete --emit
```

The checked Sage runtime receipt was saved before the runs. `run_stage.py`
refuses to overwrite archived cells.
