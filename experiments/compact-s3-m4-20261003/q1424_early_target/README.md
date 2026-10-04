# Q1424: activate target-coupled roots earlier

Q1423's exact final-S3 root rule is sound, but it activated only once during
each ordinary N53/N83 query while the solver generated over 62,000 pair-root
assignments. Q1424 changes only the decision order of the same exact-root
solver and adds separate counters for the two leaf-pair links. The frozen
policies are:

- `target_first`: decide the target-preimage selector, the first leaf pair,
  its intermediate, then the second leaf pair.
- `target_mid_first`: decide the target-preimage selector and first-pair
  intermediate before any leaf, then decide the first and second leaf pairs.

Both policies keep Q1422's exact leaf-lift gate, Q1420's two external pair
S3 root links, Q1423's exact final S3 root rule, and Q1420's Boolean final
link. Decisions select SAT branches; they add no exclusions. Thus a valid
four-point decomposition remains in the formula under either policy. The
known-witness controls are correctness checks, not natural-yield samples.

The [frozen protocol](protocol.json) pins the Q1420 CNFs and target-preimage
lists and pairs every cell with its Q1423 receipt. The exact curves are
`EC1N53Ckb1hf77aab617904` and `EC1N83Ckb1h876c2921cb64`. Q1301 N53
W≤3 has actual `B=24,062`, folded `K=227`; Q1325 N83 W≤5 has actual
`B=30,977,592`, folded `K=186,612`. The protocol carries their enumerated
base digests. The stage IDs are `PS1...PDP4theory...`; `candidate_id` remains
null and `isogeny` is `none`. Target-preimage values are workload data and
are excluded from the Q1424 method hash.

Each policy runs one `free_mids` known-witness control and one ordinary
unpinned public target at each degree. Caps are one million conflicts, 60
seconds inside CaDiCaL, and a 75-second outer safeguard. Preserve failures,
timeouts, field operations, memory, and raw output. CPU walls on this host
are exploratory. An ordinary relation is a solver gate; it is not a natural
relation-yield estimate or a complete degree-131 `2^x` projection.

## Reproduction

Use the checked Sage launcher for all Sage jobs:

```sh
python3 experiments/compact-s3-m4-20261003/q1424_early_target/build_binaries.py --rebuild
python3 experiments/compact-s3-m4-20261003/q1424_early_target/build_binaries.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1424_early_target/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1424_early_target/run_stage.py --degree 53 --cell free_mids --policy target_first
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1424_early_target/run_stage.py --degree 53 --cell ordinary --policy target_first
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1424_early_target/run_stage.py --degree 83 --cell free_mids --policy target_first
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1424_early_target/run_stage.py --degree 83 --cell ordinary --policy target_first
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1424_early_target/verify_archive.py --require-complete --emit
```

Run `target_mid_first` for the same degree/cell combinations in the frozen
protocol. The runner refuses to overwrite any completed row. The protocol
was committed and published in draft PR #246 before ordinary runs began.

## Frozen outcomes

The [eight-cell archive verifier](verification.json) passed. All four
known-witness controls produced verified exact-base relations. All four
ordinary queries reached the internal 60-second wall cap without a model;
the outer safeguard did not fire.

| Degree | Policy | Pair-0 roots | Pair-1 roots | Final-root calls | Field mul/sqr/inv | Peak RSS |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| 53 | `target_first` | 1 | 58,514 | 1 | 1,895,858 / 10,889,360 / 141,899 | 626 MB |
| 53 | `target_mid_first` | 225,790 | 0 | 1 | 6,746,854 / 38,322,434 / 476,463 | 2,293 MB |
| 83 | `target_first` | 1 | 65,289 | 1 | 3,197,391 / 27,274,570 / 260,958 | 1,205 MB |
| 83 | `target_mid_first` | 135,141 | 0 | 1 | 6,622,968 / 56,498,534 / 540,681 | 2,496 MB |

Moving the target selector earlier does not by itself increase final-root
activation. The two orders move the large enumeration between the two pair
links. Q1423's combined pair count did not identify which link dominated;
these new separate counters do. The `target_mid_first` order spends more
field calls and memory within the same cap, and neither policy recovers an
ordinary relation. Counts are stage diagnostics, not a wall-time speedup or
natural-yield estimate. The complete degree-131 `2^x` remains unknown.

The next solver should test **bidirectional pair feasibility**: given a
target and an intermediate, reject a branch before enumerating many full
two-leaf pairs, while proving that no valid factor-base decomposition is
lost. A matched pair-index method is the natural comparator. A successful
N53 control must recover the archived ordinary witness without its pins;
N83 then needs a verified ordinary relation or a preregistered fresh panel
that measures nonrepresentable targets and natural yield.
