# Q1487: inverse S3 partner support

The [pre-registered design](design_protocol.json) tests an exact alternative
to Q1486's bounded pair enumeration. In characteristic two,
`S3(x,y,u)=0` is symmetric. Once a midpoint `u` and one nonzero leaf `x`
are fixed, there are at most two possible partner `y` values. Q1487 will
scan the smaller partial leaf domain and test those roots against the other
leaf's complete cyclic-window membership rule. The zero-midpoint case has
one partner, `y=1/x`.

This can check a much larger pair domain while enumerating at most 4,096
anchor values. The experiment must show whether the improved support test
changes the unpinned and ordinary N53/N83 outcomes; no relation recovery
or scaling improvement is assumed. The six CNFs, public targets, actual
factor bases, and window maps are inherited byte for byte from Q1482/Q1486.
The proposal keeps `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. Its exact stage IDs use actual usable point counts,
not nominal window dimensions:

- `PS1N53Ckb1fb430360PDP4hybridh2a52e8f4da45` (`B=430360`, `K=4060`)
- `PS1N83Ckb1fb348006384PDP4hybridhdc30312c79f8`
  (`B=348006384`, `K=2096424`)

The [frozen protocol](protocol.json) binds the source and binary, the
checked Sage runtime, both exact curve/field records, inherited target
and CNF hashes, window selector maps, decision policy, and time limits.
The [small-field control](small_field_validation.json) compared 326,432
ordered domain-pair/midpoint states with direct `S3` evaluation over
`F_32`, including the zero-midpoint reciprocal. The
[native control](native_validation.json) compared direct and inverse
support in 16 N53 and 20 N83 domain/midpoint cases, including partner
domains larger than the 4,096-anchor cap and assigned nonzero leaf bits.
These are equivalence checks; they do not measure ordinary-query yield.
No complete N131 `2^x` follows from the protocol.

## Frozen result

Commit `c4566b75` froze the native solver and both stage IDs before any
measured cell. The [archive audit](archive_audit.json) checked all six
source-bound receipts, rebuilt the inherited inputs and selector maps,
and independently replayed both pinned public-point relations.

| Cell | Status | Verified relations | Inverse checks / right supports | Field mul / sqr / inv | `S3` roots |
| --- | --- | ---: | ---: | --- | ---: |
| N53 planted pinned | SAT | 1 | 0 / 0 | 209 / 1,236 / 18 | 5 |
| N83 planted pinned | SAT | 1 | 0 / 0 | 227 / 1,926 / 18 | 5 |
| N53 planted unpinned | 60 s cap | 0 | 4,810 / 0 | 191,912,000 / 808,688,142 / 6,692 | 13,700,558 |
| N83 planted unpinned | 60 s cap | 0 | 20,474 / 0 | 81,966,962 / 521,893,194 / 2,884 | 5,861,504 |
| N53 ordinary | 60 s cap | 0 | 4,832 / 0 | 193,168,040 / 814,005,856 / 6,736 | 13,790,664 |
| N83 ordinary | 60 s cap | 0 | 20,470 / 0 | 81,738,144 / 520,434,452 / 2,876 | 5,845,120 |

Q1487 lowers actual N83 ordinary `S3` root evaluations from Q1486's
8,456,687 to 5,845,120, but performs 83,778,452 membership checks and
finds **zero** right-pair supports. These are censored prefixes; neither
ratio is a cost per relation or a controlled CPU speedup. Q1484's N131
base census ran concurrently and this host has no CPU-isolation receipt.

The fixed-midpoint branch is sparse even before target coupling. With a
single positive window selector per right leaf, at most `2^d-1` nonzero
field values fit each leaf. After the 4,096-anchor cap, a fixed domain
pair has at most `2 * 4096 * (2^d-1)` possible midpoint roots. Thus a
**uniformly sampled** midpoint has support probability at most
`2 * 4096 * (2^d-1) / 2^n`: below `2^-26` at N53 (`d=14`) and below
`2^-47` at N83 (`d=23`). This is a counting bound for one fixed pair of
partial domains under a uniform midpoint; the SAT choices here are
target-dependent, so it is not a measured yield or a probability bound
for the search. It explains why making a local fixed-midpoint test faster
did not recover a relation.

The next solver gate needs **four-leaf coupling with the midpoint left
existential** across many windows. The first result that would change the
assessment is an independently verified, fully unpinned N83 planted
relation on this exact base, followed by an ordinary N83 relation and a
frozen query panel for yield and novel rank. The successful PDP cost,
natural relation yield, target descent, final matrix work, and complete
N131 `2^x` remain unknown.

## Reproduce custody checks

```sh
python3 experiments/compact-s3-m4-20261003/q1487_inverse_partner/build.py --check
python3 experiments/compact-s3-m4-20261003/q1487_inverse_partner/validate_native.py --check
python3 experiments/compact-s3-m4-20261003/q1487_inverse_partner/freeze_protocol.py --check
```

After the six frozen runs, replay the public-point checks and archive
audit with the checked Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1487_inverse_partner/audit.py --check
```
