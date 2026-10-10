# Exact W15 pair-output prefix filter for the N131 six-pair circuit

The first two fixed-seed pair blocks admit only 7,661 and 7,828 of the
65,536 possible 16-bit output prefixes. Complete enumeration of their
pair outputs and an independent bit-field replay certify this support.
Adding its 37,366 forbidden-prefix clauses to the frozen six-pair circuit
preserves every valid relation in the declared source. The constructed
XCNF witness and exact group lift pass. On the published ECC2K-130 point,
the one-worker, 4-GiB public search records `CENSORED_TIME` at 592.074 s
of construction plus search. The exact filter is reusable; this CNF
encoding did not clear the ordinary-relation gate at the frozen cap.

## Source and filter

The curve is `EC1N131Ckb1heb5f1998f20b` over
`GF(2^131)` with modulus `t^131+t^13+t^2+t+1`. The six-pair source has
W15 reciprocal-coordinate masks, two target-independent fixed pair seed
sums 12004 and 9022 at Frobenius rotations 0 and 13, and ten remaining
free masks. The source has 16,441 usable masks and 16,381 folded columns.
Its independently audited exact signed-tuple mean is 34,098.768 per
uniform subgroup target before intermediate filtering; this is a source
count, not an observed relation rate. The full pipeline remains a proposal,
so `candidate_id` is `null`.

For each fixed seed, [derive_prefix.py](derive_prefix.py) enumerates all
valid unordered mask pairs, solves both roots of the exact pair-output
quadratic, and records the first 16 bits of the reciprocal output. It
finished in 6.513 s of target-independent precomputation with
260,472,832 B sampled process RSS. [audit_prefix.py](audit_prefix.py)
independently replays every pair and root in bit-field arithmetic and
checks the full prefix complement.

| Pair seed, rotation | Valid unordered pairs | Full roots checked | Allowed prefixes | Excluded signatures | Minimal CNF clauses |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12004, 0 | 4,088 | 8,176 | 7,661 | 57,875 | 18,570 |
| 9022, 13 | 4,170 | 8,340 | 7,828 | 57,708 | 18,796 |

The clauses constrain only the corresponding pair-output wires. They do
not fix a target-dependent pair choice. The [producer receipt](prefix_table.json),
[independent audit](prefix_audit.json), [frozen protocol](protocol.json),
and [checked Sage runtime](sage_runtime_info.json) bind the enumeration
and run inputs. The exhaustive [pair identity check](identity.json)
and [source count audit](support_audit.json) are retained beside them.

## Frozen public gate

The [constructed control](control.json) passes a complete XCNF
assignment and [group lift](control_group_lift.json). The control is a
correctness check for the circuit and filter, not a natural-query yield
measurement. The target is the previously published subgroup point
`(2309658012506412099988466246134815930289,
1578526100003023531340803776621036465818)`.

| Public formula / run | Previous two-seed circuit | Prefix-filter circuit |
| --- | ---: | ---: |
| Variables | 117,252 | 117,252 |
| CNF clauses | 424,423 | 461,789 |
| Native-XOR rows | 42,855 | 42,855 |
| AND gates | 72,903 | 72,903 |
| Target formula construction | 3.932 s | 14.131 s |
| Solver time | 588.180 s | 577.944 s |
| Construction plus search | 592.112 s | 592.074 s |
| Query status | `CENSORED_TIME` | `CENSORED_TIME` |
| Sampled combined peak RSS | 685,441,024 B | 463,192,064 B |

Both runs used the same target, one CryptoMiniSat worker, 4-GiB RSS cap,
and 600-s construction-plus-search cap. The prefix run's solver log reached
628,000 conflicts versus about 3,049,000 in the earlier run; the extra
CNF work reduced conflict throughput on this host. These are unisolated
diagnostics, not a wall-time speedup comparison. A censored run gives no
measured relation yield, useful rank, target log, or online speedup.

The [terminal audit](terminal_audit.json) rehashes and recounts the exact
[public formula](system.xcnf.gz) and [control formula](control.xcnf.gz),
checks their appended trace constraints and the 37,366-clause difference,
binds [result.json](result.json) to the [solver log](solver.stdout.txt),
and verifies the terminal status. The raw formula SHA-256 is
`c23ffef8cea7a17faddfb88f75177f85f43923a4db431c72359346be6a648ce5`.
Run `python3 -B audit_archive.py` from this directory to replay the hash
and formula checks using the committed archive alone.

The next method gate should act on target-coupled S3 and pair-product
constraints before expanding a large SAT formula. First recover and
independently replay an ordinary N41 relation with a multi-block inverse
or factored bucket norm. Then count its operations and peak memory against
the N131 600-s/4-GiB gate before another challenge-width search.
