# Q1486: exact cyclic-window pair domains

The [pre-registered design](design_protocol.json) tests an exact
window-aware replacement for Q1485's loose weight-bound leaf completion.
Q1485 rejected many unsupported partial states but did not find an
unpinned relation on either ordinary N53/N83 query. Its N83 ordinary
prefix made 8.57 million `S3` root calls and censored at 60 seconds.

Q1486 uses Q1482's exact six CNFs and public points without changing any
clause or target. The native variable map additionally exposes the
already-existing cyclic-window selectors and their ONB coordinate masks.
A leaf completion must be extendable to those selector assignments. This
lets the target-coupled pair domains enumerate the actual factor-base
shape while retaining the full Q1481 orbit-union base.

The first empirical gate is a fully unpinned known-satisfiable N83
decomposition, independently checked on the public point. The ordinary
N83 cell follows under the same frozen limits. A planted success alone is
not a natural-yield estimate. Q1486 remains a `Q` proposal with
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`; its stage IDs
use Q1481's actual `B` values in the [frozen protocol](protocol.json):

- `PS1N53Ckb1fb430360PDP4hybridh5029e04bb3bb`
- `PS1N83Ckb1fb348006384PDP4hybridh55d5e1e8904f`

The [window-map receipts](inputs/) verify that all four selector rows and
the outside-window zero clauses already exist in each reused Q1482 CNF.
The [small-field control](window_validation.json) matched 59,049 partial
leaf/selector states to the original existential window clauses over
`F_32`, including overlapping and multiple selected windows. It checked
2,048 coupled guards against direct `S3` evaluation. The native source,
binary, input and map hashes, checked Sage runtime, limits, and stage IDs
were frozen before the six runs. No complete N131 `2^x` is implied.

## Frozen result

Commit `c2bbdc58` froze the binary, checked Sage runtime, Q1482 CNF and
target hashes, six selector-map sidecars, limits, and stage IDs before any
solver cell. The [archive audit](archive_audit.json) rebuilt all six CNFs
and sidecar maps, checked the source-bound receipts, and independently
replayed both pinned public-point models.

| Cell | Status | Verified relations | Coupled checks / empty intersections | Field mul / sqr / inv | `S3` roots |
| --- | --- | ---: | ---: | --- | ---: |
| N53 planted pinned | SAT | 1 | 213 / 0 | 341 / 1,788 / 24 | 9 |
| N83 planted pinned | SAT | 1 | 333 / 0 | 365 / 2,778 / 24 | 9 |
| N53 planted unpinned | 60 s cap | 0 | 3,552 / 3,552 | 202,265,414 / 852,510,014 / 7,106 | 14,443,932 |
| N83 planted unpinned | 60 s cap | 0 | 2,088 / 2,088 | 119,819,029 / 761,732,914 / 4,178 | 8,554,991 |
| N53 ordinary | 60 s cap | 0 | 3,524 / 3,524 | 200,659,838 / 845,740,582 / 7,050 | 14,329,244 |
| N83 ordinary | 60 s cap | 0 | 2,064 / 2,064 | 118,442,341 / 752,979,922 / 4,130 | 8,456,687 |

Q1485's matched N83 ordinary prefix used 8,570,128 `S3` roots,
119,998,624 multiplications, 763,105,558 squarings and 4,482 inversions;
it also censored. Q1486's exact window completion makes a small reduction
in the operation vector but still evaluates about four thousand right-pair
roots per eligible partial state. No complete midpoint intersection was
found in either ordinary prefix. Neither prefix is a successful relation
cost, and the counts cannot establish a CPU speedup. Q1484's N131 census
is still running separately; exact `B`/`K`, natural yield, novel rank,
final matrix cost, target descent, and complete N131 `2^x` remain unknown.
The Q1484 census was concurrent with these Q1486 runs; all wall times are
exploratory and have no host-isolation receipt.

The next solver needs a mechanism that reasons about many leaf-pair
completions together. Merely pruning the same 4,096-completion local
domains did not cross the unpinned N83 correctness gate.

## Reproduce custody checks

```sh
python3 experiments/compact-s3-m4-20261003/q1486_window_aware_pair/build.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1486_window_aware_pair/prepare_window_maps.py --check
python3 experiments/compact-s3-m4-20261003/q1486_window_aware_pair/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1486_window_aware_pair/audit.py --check
```
