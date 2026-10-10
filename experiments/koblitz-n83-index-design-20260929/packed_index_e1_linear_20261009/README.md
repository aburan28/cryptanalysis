# E-1: linear lookup within 22-bit packed root buckets

The sequential early-stop lookup reduced exact-key comparisons from
9,324,648 to 6,655,806 (28.6%) on the frozen N83 target probe. It kept the
same 4,000,000 exact 18-byte records, 88,777,220-byte allocated root table,
first-witness lookup samples, and arithmetic operation counts. The paired
wall times moved in both directions on this unisolated host, so the measured
CPU speedup remains unknown.

## Frozen comparison

The curve is `EC1N83Ckb1h876c2921cb64`; the one-target workload ID is
`981ac530e67e`. The parent factor base contains 30,977,592 actual usable
points and 186,612 folded columns. Both arms index the same 2,000,000 sampled
pair states under a 1,024 MiB RSS cap. Counting scatter and local sorting
produce the same 22-bit hashed bucket directory. The only lookup change is
binary lower-bound search versus sequential search that stops at the first
key at least as large as the query. Both compare full 83-bit keys and retain
the first descriptor for duplicate roots.

| Arm | Exact comparisons | Median target stage | Median exact lookup | Allocated table |
| --- | ---: | ---: | ---: | ---: |
| Binary | 9,324,648 | 7.570 s | 2.266 s | 88,777,220 B |
| Linear | 6,655,806 | 11.480 s | 3.065 s | 88,777,220 B |

The six-run order was binary, linear, linear, binary, binary, linear. The three
adjacent target-stage pairs were 11.949/11.480 s, 14.147/7.570 s, and
6.903/7.439 s in execution order. These shifts are larger than the expected
lookup effect. The complete phase rows, peak RSS, and raw failures are in
[`summary.json`](summary.json) and the six `run_*.json` files. All six runs
ended `state_cap_no_relation` at the declared cap; the target-stage interval
is a bounded point-decomposition diagnostic.

The first-witness, miss, duplicate-key, and batched-S3 unit tests passed.
Across all six full runs, the frozen input identifiers, indexed state and key
counts, lookup sample values, target outcome, and field/group operation
counts agreed. Query preparation, S3 batch evaluation, partner processing,
canonicalization, and exact lookup have separate timers; these timers are
inside the target-stage interval and apply to both arms.

## Replay

From this directory, run `python3 run.py`. The runner archives crypto source
commit `904f0f844f3c1e69e8d22ae5e60ecd56e6648611` from the local
`/Volumes/SSD990/crypto` checkout, verifies its source-tree digest and the
frozen input hashes, builds the Rust binary with `cargo --release --locked`,
and writes each raw result before summarizing. [`protocol.json`](protocol.json),
[`stage_manifest.json`](stage_manifest.json), [`workload.json`](workload.json),
and [`build_receipt.json`](build_receipt.json) bind the source, input, order,
limits, and environment. A qualifying isolated-host replay is required for
a CPU wall-time speedup claim.
