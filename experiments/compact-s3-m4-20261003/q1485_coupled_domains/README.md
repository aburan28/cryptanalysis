# Q1485: target-coupled exact pair-domain intersection

The [pre-registered design](design_protocol.json) tests one solver change on
Q1482's exact N53/N83 window-orbit bases and byte-identical six-cell inputs.
Q1482's native theory commits to a second midpoint and then spends many
direct `S3` evaluations on right-pair completions that have no support.
Q1485 builds exact left and right midpoint domains while both leaf pairs are
still partial, intersects them under the public target, and emits guarded
clauses for empty intersections or forced midpoint bits.

Each domain enumerates at most 4,096 weight-`d` pair completions. That set is
a superset of every window-valid completion in the unchanged Q1482 CNF, so
an empty intersection is a sound rejection. The bounded domain is a local
stage mechanism; success on a planted point does not measure ordinary yield.
Both ordinary public targets remain exactly those used by Q1482.

Q1485 remains a `Q` proposal with `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. The [frozen stage protocol](protocol.json) uses Q1481's
actual usable `B` counts and Q1482's byte-identical six-cell inputs:

- `PS1N53Ckb1fb430360PDP4hybridhffb34db82440`
- `PS1N83Ckb1fb348006384PDP4hybridhb9502b103ea2`

The [small-field control](coupled_validation.json) exhausted 5,103 left
target/pair-state domains, 729 right pair-state domains, and 157,464 domain
filters under partial midpoint masks over `F_8`. It also checked 16,384
seeded coupled four-leaf guards against direct `S3` evaluation. This checks
the mathematical pruning rule at that size; the pinned public-point cells
check the native implementation at N53/N83. The complete N131 `2^x` remains
unknown.

## Frozen result

The source, binary, checked Sage runtime, inherited input hashes, limits,
and stage IDs were frozen in commit `b4252afa` before execution. The
[archive audit](archive_audit.json) rebuilt all six Q1482 inputs, checked
their receipts and source hashes, and independently replayed both pinned
models as four-distinct-column public relations. The pre-frozen `audit.py`
had an import-path collision with Q1482's runner; the independent
[`audit_v2.py`](audit_v2.py) uses explicit Q1485 protocol and binary paths
without changing any measured source.

| Frozen cell | Status | Verified relations | Coupled checks / empty intersections | Field mul / sqr / inv | `S3` root calls |
| --- | --- | ---: | ---: | --- | ---: |
| N53 planted pinned | SAT | 1 | 1 / 0 | 341 / 1,788 / 24 | 9 |
| N83 planted pinned | SAT | 1 | 1 / 0 | 365 / 2,778 / 24 | 9 |
| N53 planted unpinned | 60 s cap | 0 | 4,176 / 4,176 | 203,541,908 / 858,036,036 / 8,354 | 14,535,680 |
| N83 planted unpinned | 60 s cap | 0 | 2,240 / 2,240 | 119,998,624 / 763,105,558 / 4,482 | 8,570,128 |
| N53 ordinary | 60 s cap | 0 | 4,100 / 4,100 | 199,621,896 / 841,515,600 / 8,202 | 14,255,808 |
| N83 ordinary | 60 s cap | 0 | 2,240 / 2,240 | 119,998,624 / 763,105,558 / 4,482 | 8,570,128 |

The N83 ordinary Q1482 prefix used 317,569,291 multiplications,
80,094,454 squarings, 6 inversions, and 79,366,320 direct right `S3`
evaluations. Q1485 reduces the multiplication count but increases
squarings to 763,105,558 and inversions to 4,482. The calls are different
operations and are not interchangeable work units. Both prefixes censor at
the same 60-second cap, and neither supplies a successful decomposition
cost, natural relation yield, rank, or a complete N131 `2^x`. CPU wall
times are exploratory without an isolated-host receipt.

The next solver design should enumerate only **window-valid** pair
completions, keep target coupling, and make an unpinned known-satisfiable
N83 relation its first success gate. Q1485's weight-`d` superset still
spends millions of root calls rejecting invalid partial branches.

## Reproduce custody checks

```sh
python3 experiments/compact-s3-m4-20261003/q1485_coupled_domains/build.py --check
python3 experiments/compact-s3-m4-20261003/q1485_coupled_domains/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1485_coupled_domains/audit_v2.py --check
python3 experiments/compact-s3-m4-20261003/build_work_ledger.py
```
