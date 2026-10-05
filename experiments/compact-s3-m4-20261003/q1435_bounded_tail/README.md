# Q1435: bounded exact completion with one or two weight units left

Q1434 tested exact second-pair `S3` membership only after each leaf had one
normal-basis Hamming-weight unit left. Q1435 extends the same
solution-preserving check to one or two units per leaf. The matched N53/N83
curves, exact factor bases, public targets, CNF, decision policy and
60-second/one-million-conflict limits are unchanged. The
[protocol](protocol.json) and its source and input hashes were committed
before the four solver runs.

For a partial leaf with `k` free coordinates and slack `s` of one or two,
the allowed completion count is `Σ(i=0..s) C(k,i)`. Q1435 checks a state
only when the product of the two leaf counts is at most **4,096**. It uses
the exact cached bilinear expansion of `S3(a,b,m)` to evaluate every
candidate pair; it records both field operations and expansion XORs. A
zero-solution domain produces a clause guarded by every fixed leaf bit and
all bits of `m`. A unique solution forces the remaining leaf bits under the
same guard. Larger domains and multiple-solution domains leave SAT
unchanged.

The [103-case validation](tail_validation.json) compares native counts and
unique coordinates with direct Sage `S3` enumeration. It covers all four
slack patterns (1/1, 1/2, 2/1 and 2/2), archived partial trails, synthetic
states and independently verified witness completions. It found 73
zero-solution cases, 30 unique-solution cases and zero false witness
rejections. The [archive verifier](verification.json) independently checks
both returned witness relations and sampled emitted zero-solution claims.
The solver retained its first 16 zero-claim snapshots per ordinary run;
those samples are all 1/1 states. The 1/2, 2/1 and 2/2 arithmetic checks
are covered by the separate native/Sage validation, while individual
ordinary 1/2 and 2/1 clauses were not archived for independent replay.

| Degree | Curve ID | Actual usable base points `B` | Folded columns `K` |
| --- | --- | ---: | ---: |
| 53 | `EC1N53Ckb1hf77aab617904` | 24,062 | 227 |
| 83 | `EC1N83Ckb1h876c2921cb64` | 30,977,592 | 186,612 |

The protocol retains each base's enumerated-set digest and the exact
field, curve, subgroup and target. This is proposal `Q1435`, with
`candidate_id: null` and `isogeny: "none"`. Its `PS1...PDP4theory...`
labels identify solver stages, not complete `IC1` pipelines.

## Frozen result

Both known-witness controls returned independently verified four-point
relations. Both unpinned ordinary queries reached the 60-second cap with
zero verified relations. CPU wall times are exploratory because the host
lacks an isolation receipt.

| Ordinary query | Span checks / rejects | Bounded tail eligible / skipped | Checked / zero | Candidate pairs / expansion XORs | Total field mul / sqr / inv | Peak child RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | 385,616 / 56,182 | 329,434 / 1,026 | 328,408 / 328,408 | 110,100,907 / 354,587,110 | 3,455,974 / 4,835,104 / 51,087 | 896,008,192 bytes |
| N83 | 78,588 / 75,400 | 3,188 / 121 | 3,067 / 3,067 | 1,405,528 / 4,152,415 | 1,349,966 / 8,168,150 / 76,517 | 313,884,672 bytes |

At N53 the checked states comprised 301,761 with slack 1/1, 13,531 with
1/2 and 13,116 with 2/1. All 1,026 observed 2/2 states exceeded the
4,096-candidate limit and were skipped. At N83, 3,049 1/1, three 1/2 and
15 2/1 states were checked; 121 larger 1/2 or 2/1 domains were skipped,
and no 2/2 state was observed in this capped prefix. Every checked
ordinary domain had zero `S3` completions. No unique ordinary completion
or full second-pair assignment occurred.

Q1435's N53 prefix explored more decisions and conflicts than Q1434's
matched 60-second prefix, but also spent more arithmetic and 354 million
expansion XORs. The paths differ and the CPU was not isolated, so this is
neither a controlled speedup nor a cost per successful query. N83 also
remained censored. There is still no measured ordinary solver cost,
natural relation yield, useful-row rate, or complete N131 `2^x`.

## Decision

Further increases to this leaf-completion cap would enumerate increasingly
large domains without addressing the main search structure. The next goal
is a **target-conditioned, sublinear membership and witness procedure for
the fixed-intermediate sparse-pair equation**. It must reject or recover a
pair before nearly complete leaf assignments, avoid materializing the full
pair index, and be measured on ordinary N53/N83 queries with its
target-dependent work and memory charged. An independently verified N53
ordinary decomposition is the first acceptance gate; N83 and fresh target
yield/rank measurements follow before any complete N131 projection.

## Reproduction

From the repository checkout:

```sh
python3 experiments/compact-s3-m4-20261003/q1435_bounded_tail/build_binaries.py --rebuild
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1435_bounded_tail/validate_tail.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1435_bounded_tail/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1435_bounded_tail/verify_archive.py --require-complete --emit
```

The checked Sage runtime receipt was saved before the measured cells, and
`run_stage.py` refuses to overwrite archived runs.
