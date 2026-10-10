# E-1: 25-bit packed root bucket width on the frozen N83 target stage

A 25-bit hashed directory reduces full-key root probes from 471,510 to
131,309 compared with the 24-bit directory on the same frozen one-target
stage. Exact keys, duplicate first witnesses, arithmetic counts, and the
target outcome match. The extra 64 MiB of table space keeps peak RSS below
the 1,024 MiB cap. Local wall times were mixed under visible host contention,
so bucket-width selection by CPU time awaits an isolated replay.

## Frozen comparison

The curve is `EC1N83Ckb1h876c2921cb64`, workload ID `981ac530e67e`.
The parent factor base has 30,977,592 usable points and 186,612 folded
columns. Both arms index the same 2,000,000 sampled pair states and the same
4,000,000 exact 18-byte root records, use zero-gap canonicalization and
eight-bit singleton tags, and query one frozen public point. Only the hashed
bucket directory width changes from 24 to 25 bits. The clock begins after
index construction and includes target query preparation, batched S3 roots,
partner canonicalization, exact lookup, and relation checks.

| Arm | Median target stage | Median exact lookup | Full-key probes | Table bytes | Median peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| 24-bit tagged | 20.615 s | 4.368 s | 471,510 | 139,108,868 | 735,887,360 |
| 25-bit tagged | 16.834 s | 4.213 s | 131,309 | 206,217,732 | 870,105,088 |

The table grows by 64 MiB and median peak RSS by 128 MiB. The six-run order
was 24, 25, 25, 24, 24, 25. Adjacent target-stage pairs were
25.933/22.292 s, 20.615/11.604 s, and 15.769/16.834 s, each listed as
24-bit/25-bit. Exact-lookup timing favored 25 bits in one of those three
pairs. These times are exploratory because other native compilations were
active on this host. The raw rows and exclusive phase costs are in
[`summary.json`](summary.json) and the six `run_*.json` files. All runs
reached the declared `state_cap_no_relation` status.

The four Rust tests passed, covering exact hits, misses, duplicate
first-witness behavior, zero-gap canonicalization, and batched S3 roots.
All six full runs matched frozen identifiers, state and key counts, lookup
samples, target status, and noncanonical arithmetic counts; the summary has
no invariant mismatches. The replay wrapper verified both arms against
their frozen fixtures and emitted the same paired certificate.

## Reproduce and replay

From this directory, `python3 run.py` archives crypto source commit
`904f0f844f3c1e69e8d22ae5e60ecd56e6648611` from the local
`/Volumes/SSD990/crypto` checkout by default, checks source and input
digests, builds with `cargo --release --locked`, and saves each raw row.
Set `CRYPTO_REPO` for another local crypto checkout and `N83_E1_TARGET_DIR`
for a different build location.

On a qualifying isolated Linux host, build the frozen binary from this
directory and generate the benchmark-service manifest with the verified
CPU, NUMA, and cgroup configuration:

```sh
CRYPTO_REPO=/workspace/crypto N83_E1_TARGET_DIR=/workspace/build/n83-e1-25 \
  python3 -c 'import json,run; run.ensure_crypto_snapshot(); run.build(json.load(open("protocol.json")))'
python3 make_manifest.py \
  --workdir /workspace/cryptanalysis \
  --binary /workspace/build/n83-e1-25/release/native_packed_index \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \
  --output /workspace/isolated-bench/n83-e1-bucket25.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe \
  /workspace/isolated-bench/n83-e1-bucket25.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py \
  --queue-root /workspace/isolated-bench submit \
  /workspace/isolated-bench/n83-e1-bucket25.json
```

The adapter verifies each native result and emits the native target-stage
interval and paired correctness certificate. A qualifying service receipt
can decide the 24-bit versus 25-bit stage timing. The complete single-target
IC online metric additionally includes target recovery and a matched rho
reference under the repository's measurement contract.
