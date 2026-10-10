# E-1: sparse 26-bit packed root directory on the frozen N83 target stage

A bitmap and rank directory stores offsets only for occupied 26-bit hash
buckets. On the frozen one-target stage, it reduces table allocation from
206,217,732 to 101,360,128 bytes and full-key probes from 131,309 to 35,837
against the dense 25-bit directory. Exact keys, duplicate first witnesses,
arithmetic counts, and the target outcome match. Median peak RSS falls from
870,203,392 to 726,466,560 bytes, below the 1,024 MiB cap.

## Frozen comparison

The curve is `EC1N83Ckb1h876c2921cb64`, workload ID `981ac530e67e`.
The parent factor base has 30,977,592 usable points and 186,612 folded
columns. Both arms index the same 2,000,000 sampled pair states and 4,000,000
exact 18-byte root records, use zero-gap canonicalization and eight-bit
singleton tags, and query one frozen public point. The comparison changes
only the directory layout and hash width. The clock begins after index
construction and includes target query preparation, batched S3 roots,
partner canonicalization, exact lookup, and relation checks.

| Arm | Median target stage | Median exact lookup | Median index build | Full-key probes | Table bytes | Median peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense 25-bit tagged | 10.988 s | 2.317 s | 3.649 s | 131,309 | 206,217,732 | 870,203,392 |
| Sparse 26-bit tagged | 10.041 s | 2.229 s | 4.375 s | 35,837 | 101,360,128 | 726,466,560 |

The six-run order was dense, sparse, sparse, dense, dense, sparse.
Adjacent target-stage pairs were 10.988/20.328 s, 11.692/10.041 s, and
7.558/4.776 s, listed as dense/sparse. These CPU times are exploratory:
the local host lacks the required isolation receipt, and the paired spread
is large. The raw rows and exclusive phase costs are in [`summary.json`](summary.json)
and the six `run_*.json` files. Each run recorded `state_cap_no_relation`
at the declared cap.

The sparse directory uses one bit per possible bucket, a rank prefix per
64-bit bitmap word, and one 32-bit offset per occupied bucket plus a sentinel.
Singleton offsets retain the same exact-key fingerprint as the dense arm;
an exact key comparison follows every surviving tag. Occupied buckets are
sorted by exact key and descriptor, preserving the first-inserted witness
when duplicate keys occur. The bitmap also rejects empty buckets before
touching the offset or record arrays. The table byte figure includes the
bitmap, ranks, offsets, and records; peak RSS includes temporary index-build
storage.

Four Rust tests passed, covering exact hits, misses, duplicate first-witness
behavior, zero-gap canonicalization, and batched S3 roots. All six full runs
matched frozen identifiers, state and key counts, lookup samples, target
status, and noncanonical arithmetic counts. The replay wrapper verified
both arms against their frozen fixtures and emitted the same pair certificate
`4d6ff730d8cb35b5ba851be41b047850300253857e3a877bc360a52f325da947`.
The wrapper receipt is in [`replay_check.json`](replay_check.json).

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
CRYPTO_REPO=/workspace/crypto N83_E1_TARGET_DIR=/workspace/build/n83-e1-sparse26 \
  python3 -c 'import json,run; run.ensure_crypto_snapshot(); run.build(json.load(open("protocol.json")))'
python3 make_manifest.py \
  --workdir /workspace/cryptanalysis \
  --binary /workspace/build/n83-e1-sparse26/release/native_packed_index \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \
  --output /workspace/isolated-bench/n83-e1-sparse26.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe \
  /workspace/isolated-bench/n83-e1-sparse26.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py \
  --queue-root /workspace/isolated-bench submit \
  /workspace/isolated-bench/n83-e1-sparse26.json
```

The adapter verifies each native result and emits the native target-stage
interval and paired correctness certificate. The isolated receipt can decide
the dense versus sparse stage timing. The complete single-target IC online
metric also requires target recovery and a matched rho reference under the
repository measurement contract.
