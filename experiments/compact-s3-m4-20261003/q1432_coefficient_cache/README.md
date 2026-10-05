# Q1432: exact coefficient reuse in the partial-pair span solver

Q1431's guarded `S3` span test was sound and pruned the actual N53/N83 SAT
trail, but it rebuilt bilinear columns on every state. Q1432 keeps the exact
Q1431 CNF, public targets, normal-basis factor bases, decision policy,
rejection condition, and guarded clause. It changes coefficient construction
only. The [frozen protocol](protocol.json) pins the code and input hashes
before the ordinary runs.

For fixed intermediate `m`, each bilinear column
`γ_ij=(e_i e_j)²+e_i e_j m` depends only on `m` and basis indices. The
solver builds pair-basis products and squares once, then retains exact
`γ_ij` tables for at most 64 intermediates. A linear column depends on `m`,
one opposite leaf's fixed-one value, and its coordinate. It computes that
column lazily and reuses it for later partial masks with the same values.
At most 16,384 linear-value rows are retained. A full cache computes the
same coefficient without retaining it. All construction calls are included
in filter and total field-operation counters; retained payload bytes and
peak process RSS are recorded separately.

The [112-case native/Sage validation](cache_validation.json) matches rank,
span membership, and columns examined on Q1430's archived trail states,
synthetic states, and completions of independently verified four-point
witnesses. It records cache hits and zero false rejections on the witness
cases. The [four-cell verification](verification.json) independently replays
both controls and sampled emitted rejections. The factor-base comparison
uses exact `EC1` curve IDs and enumerated-set digests in the protocol:

| Degree | Curve ID | Actual usable `B` | Folded columns `K` |
| --- | --- | ---: | ---: |
| 53 | `EC1N53Ckb1hf77aab617904` | 24,062 | 227 |
| 83 | `EC1N83Ckb1h876c2921cb64` | 30,977,592 | 186,612 |

This remains proposal `Q1432`, with `candidate_id: null` and
`isogeny: "none"`. Its `PS1...PDP4theory...` IDs identify solver stages,
not complete `IC1` candidates.

## Frozen result

Both known-witness controls returned independently verified four-point
relations. Both unpinned ordinary targets remained censored at 60 seconds,
with no relation.

| Degree | Ordinary status | Span checks / rejections | Total field mul / sqr / inv calls | Matched Q1431 total mul calls | Cache payload lower bound | Peak child RSS |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 53 | 60 s cap; 0 relations | 219,179 / 211,889 | 1,457,636 / 3,732,853 / 49,397 | 68,182,727 | 2,205,936 bytes | 628,932,608 bytes |
| 83 | 60 s cap; 0 relations | 67,183 / 66,621 | 1,296,699 / 8,218,271 / 77,275 | 54,467,127 | 4,563,408 bytes | 261,685,248 bytes |

The ordinary runs each built one exact intermediate-keyed `γ` table.
The N53/N83 filter made 905,700/349,603 multiplications including pair and
intermediate table construction. Compared with Q1431's same-semantic
filter, total multiplication calls fell by factors of about 46.8 and 42.0
within the capped search prefixes. Q1432 also made fewer total field calls
than the observation-only Q1430 prefixes, but the searches visit different
numbers of states under the wall cap. Those are **stage operation counts**,
not measured work per useful relation or a controlled wall-time speedup.
The CPU host lacks an isolation receipt. The retained cache payload is a
lower bound on its memory cost; peak RSS includes the solver's other caches
and SAT state.

There is still no ordinary N53 or N83 decomposition from this solver,
natural relation yield, useful-row rate, or justified complete N131 `2^x`.
No challenge run follows from these censored cells.

## Next gate

The cached filter is cheap enough to make a longer, preregistered N53
ordinary solve attempt informative. The N53 target is known to have a
representation from Q1301. A verified return would give the first
ordinary-query solve-cost point for this solver; a new cap without a return
is another lower bound, not an extrapolated solve cost. N83 still requires
an independently verified ordinary relation and useful rank before a growth
fit. If the longer search remains censored, a stronger target-conditioned
pair-sum membership and witness procedure is needed.

## Reproduction

From the repository checkout:

```sh
python3 experiments/compact-s3-m4-20261003/q1432_coefficient_cache/build_binaries.py --rebuild
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1432_coefficient_cache/validate_span.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1432_coefficient_cache/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1432_coefficient_cache/verify_archive.py --require-complete --emit
```

`run_stage.py` refuses to overwrite archived cells. The checked Sage
runtime receipt was saved before the measured runs.
