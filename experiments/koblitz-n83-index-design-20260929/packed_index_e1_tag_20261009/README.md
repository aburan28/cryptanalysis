# E-1: singleton fingerprints in packed bucket offsets

The N83 directory encoded eight key-fingerprint bits and a singleton flag in
otherwise unused bits of each 32-bit offset. On the frozen one-target probe,
1,541,485 buckets were singletons and the tags rejected 2,912,395 queries
before loading an exact record. Full 83-bit key comparisons fell from
9,324,648 to 4,943,112 (47.0%) with the same 88,777,220-byte root table,
index keys, first witnesses, and arithmetic operation counts.

For 4,000,000 records, an offset occupies 22 bits, leaving room for an
eight-bit fingerprint and a flag. A singleton-tag mismatch proves that the
full key differs. A tag match still performs an exact full-key comparison;
multi-record buckets use the previous binary search. The implementation
derives offset width from the record count and falls back to plain offsets
when there are too few spare bits. No record or bucket is discarded.

## Frozen measurement

The curve is `EC1N83Ckb1h876c2921cb64`; the one-target workload ID is
`981ac530e67e`. The factor base has 30,977,592 actual usable points and
186,612 folded columns. Both arms use exact zero-gap canonicalization,
index the same 2,000,000 sampled pair states, and obey a 1,024 MiB RSS cap.
The six-run order was plain, tagged, tagged, plain, plain, tagged.

| Measure | Plain offsets | Singleton tags |
| --- | ---: | ---: |
| Target full-key comparisons | 9,324,648 | 4,943,112 |
| Tagged singleton buckets | 0 | 1,541,485 |
| Target tag rejections | 0 | 2,912,395 |
| Allocated root table | 88,777,220 B | 88,777,220 B |
| Median target stage on this host | 12.579 s | 17.471 s |

The adjacent target-stage pairs were 12.185/17.471 s, 18.450/15.999 s,
and 12.579/6.958 s in execution order. Query preparation, S3, and
canonicalization times also shifted sharply, so these unisolated CPU times
do not establish a wall-time gain. The raw phases, RSS, and pair order are
in [`summary.json`](summary.json) and the six `run_*.json` files. All runs
ended `state_cap_no_relation` at the declared cap.

Four Rust tests passed, including exact hits, misses, duplicate first
witnesses, and exercising singleton-tag rejection. Across all six full runs,
the frozen input identifiers, indexed states and keys, lookup sample values,
target outcomes, and field/group operation counts agreed. The exact-key
comparison count and tag-rejection count are recorded separately.

## Replay

Run `python3 run.py` from this directory. The runner archives frozen crypto
commit `904f0f844f3c1e69e8d22ae5e60ecd56e6648611` from the local
`/Volumes/SSD990/crypto` checkout, checks source and input digests, builds
with `cargo --release --locked`, and preserves each raw row. The
[`protocol.json`](protocol.json), [`stage_manifest.json`](stage_manifest.json),
[`workload.json`](workload.json), and [`build_receipt.json`](build_receipt.json)
bind the complete local experiment. A qualifying isolated-host replay is
needed to promote a CPU timing ratio.
