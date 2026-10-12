# E-1: 24-bit packed root buckets on the frozen N83 target stage

A 24-bit hashed bucket directory reduces full-key probes from 4,943,112 to
471,510 while preserving the exact 4,000,000 root records and the first
descriptor for every duplicate key. On the frozen one-target N83 stage, all
three adjacent local pairs favored the 24-bit arm. These CPU timings are
exploratory because this host has no isolation receipt.

## Frozen comparison

The curve is `EC1N83Ckb1h876c2921cb64` and the workload ID is
`981ac530e67e`. The parent factor base has 30,977,592 usable points and
186,612 folded columns. Both arms index the same 2,000,000 sampled pair
states under a 1,024 MiB peak-RSS cap, use zero-gap canonicalization and
eight-bit singleton tags, and query one frozen public target point. The only
algorithmic variable is the hashed bucket directory width: 22 versus 24
bits. Each bucket retains sorted full 83-bit keys and exact comparison after
the tag filter. The target clock begins after index construction and the
lookup control, then includes query preparation, batched S3 evaluation,
partner conversion and canonicalization, exact lookup, and relation checks.

| Arm | Median target stage | Median exact lookup | Full-key probes | Table bytes | Median peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| 22-bit tagged | 6.457 s | 1.861 s | 4,943,112 | 88,777,220 | 635,273,216 |
| 24-bit tagged | 5.786 s | 1.479 s | 471,510 | 139,108,868 | 735,952,896 |

The 24-bit directory spends 48 MiB more on the table and about 96 MiB more
at peak RSS. Its larger directory produced 3,151,898 tagged singleton
buckets versus 1,541,485. The six-run order was 22, 24, 24, 22, 22, 24.
The adjacent target-stage pairs were 8.977/6.420 s, 5.939/5.635 s, and
6.457/5.786 s, each listed as 22-bit/24-bit. The complete phase costs, memory, and raw
statuses are in [`summary.json`](summary.json) and the six `run_*.json`
files. All runs reached the declared `state_cap_no_relation` status.

The four Rust tests passed, including full-key hits, misses, duplicate
first-witness behavior, zero-gap canonicalization, and batched S3 roots.
All six full runs matched the frozen input identifiers, state and key
counts, lookup samples, target outcome, and noncanonical arithmetic counts;
[`summary.json`](summary.json) records no invariant mismatches. The first
24-bit attempt tripped a constructor bound that allowed at most 22 bits.
Its raw exit statuses and stderr are retained in
[`precondition_failure`](precondition_failure). The bound was corrected
before the complete paired panel. A prior successful panel using the same
native source is retained in [`pre_runner_portability`](pre_runner_portability);
the final panel binds receipts to a runner with a configurable build path.

## Reproduce and replay

From this directory, run `python3 run.py`. The runner archives crypto source
commit `904f0f844f3c1e69e8d22ae5e60ecd56e6648611` from the local
`/Volumes/SSD990/crypto` checkout by default, verifies source and input
digests, builds the Rust binary with `cargo --release --locked`, and records
each result before summarizing. Set `CRYPTO_REPO` for another local crypto
checkout and `N83_E1_TARGET_DIR` for another build location. The default
build location is `/tmp/n83-packed-index-e1-bucket24-target`.

On a qualifying isolated Linux host, first build the native binary from the
frozen source. For example, from this experiment directory:

```sh
CRYPTO_REPO=/workspace/crypto N83_E1_TARGET_DIR=/workspace/build/n83-e1 \
  python3 -c 'import json,run; run.ensure_crypto_snapshot(); run.build(json.load(open("protocol.json")))'
```

Then generate an isolated-service manifest, replacing the CPU, NUMA, and
cgroup values with the verified host configuration:

```sh
python3 make_manifest.py \
  --workdir /workspace/cryptanalysis \
  --binary /workspace/build/n83-e1/release/native_packed_index \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \
  --output /workspace/isolated-bench/n83-e1-bucket24.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe \
  /workspace/isolated-bench/n83-e1-bucket24.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py \
  --queue-root /workspace/isolated-bench submit \
  /workspace/isolated-bench/n83-e1-bucket24.json
```

The adapter verifies each native result against its frozen arm and emits the
same paired correctness certificate. The service records the native target
stage interval with code, input, isolation, and noise receipts. That receipt
can promote a controlled *stage* timing comparison; the full single-target
IC online metric additionally requires the complete target recovery and its
matched rho reference under the repository's measurement contract.
