# E-1 sparse30 compact-rank root directory: full-capacity check

The 30-bit exact root directory with a compact 16-bit rank table reduced
full-key probes from **2,381,131 to 819,487** (65.6%) on the frozen N83
one-target, 29.9-million-state workload. Its root table used 1,393,073,152
bytes, 67,174,400 bytes (64.06 MiB) more than the sparse29 reference. The
full-capacity candidate result stayed below the 5,500 MiB RSS cap and matched
23 exact fields from the prior sparse29 result, including operation counts,
first-witness lookup samples, native control status, and bounded-stage outcome.
The source-bound [screen verifier](verify_screen.py) checks these receipts.

This is proposal `Q2026101134` on curve `EC1N83Ckb1h876c2921cb64` and workload
`63dd0929cf33`. The complete IC candidate ID is `null` while this bounded
point-decomposition stage is compared. Both modes use the same 16-byte root
record, SplitMix64 directory prefix, singleton tag, cached point coordinates,
exact lookup, and first-inserted witness rule. The candidate doubles the
prefix space from 29 to 30 bits and stores each bitmap word's rank as a
16-bit offset from a 1,024-word block base. At most 65,472 prior bits can be
set within such a block, so the offset fits in 16 bits.

| Observation | sparse29 prior-source reference | sparse30 compact-rank candidate |
| --- | ---: | ---: |
| Indexed pair states | 29,900,000 | 29,900,000 |
| Full-key target probes | 2,381,131 | 819,487 |
| Root table bytes | 1,325,898,752 | 1,393,073,152 |
| Recorded peak RSS bytes | 5,609,488,384 | 5,007,556,608 |
| Exact pair certificate | `083d0561e2d3f52763840c10d4c540550b71446daaf09f3d1ef50a53def81a51` | same |

The two RSS values are from separate exploratory Mac runs; the deterministic
table-size comparison is the memory cost of this directory change. The
sparse30 candidate's target-dependent wall interval was 95.399 seconds,
partitioned into 14.376 seconds of query preparation, 15.474 seconds of
partner generation, 65.490 seconds of partner checks, and 0.059 seconds of
residual overhead. Its target process CPU was 33.252 seconds. These timing
values are exploratory on a contended host. A sparse29 run from the same
prototype binary was stopped by the disk-space guard before it wrote a raw
result; [the interruption receipt](screen_sparse29_interruption.json) records
the 1 GiB threshold, signal exit, source, binary, and elapsed time.

The seven Rust release tests passed, including 50,000 randomized indexed
keys, misses, duplicate witnesses, and sparse30 first-witness parity with the
hash reference. The complete candidate's 23-field certificate, phase sum,
source/input hashes, memory cap, and interrupted reference are verified by
`python3 verify_screen.py`. The source SHA-256 is
`c563a232b0d456250b59d3e239fc7039957196a5fe7ced1d36626998bb1b1c60`.
The pinned public crypto source is restored by `restore_crypto_source.py`.

## Frozen Tier 0 host comparison

The [protocol](protocol.json) fixes four counterbalanced sparse29/sparse30
pairs on the same target and a 900-second cap per arm. `benchmark_stage.py`
checks the deterministic arm fields and independent paired certificate. Both
arms must report the new native source hash; the sparse29 expected-result file
is a preserved raw record from the preceding source, used only for exact
fields that the sparse30 change leaves invariant. The benchmark service
records the host preflight, raw failures, binary hashes, memory, phase costs,
and noise counters. The repository [CPU isolation gate](../../../docs/ISOLATED_BENCHMARKS.md)
controls any wall-time speedup result.

On a prepared physical Linux host with this experiment, shared inputs, and
isolated benchmark service under `/workspace/cryptanalysis`:

```sh
cd /workspace/cryptanalysis/experiments/koblitz-n83-index-design-20260929/packed_index_e1_sparse30_rank_20261011
python3 restore_crypto_source.py
python3 verify_screen.py
NATIVE_S3_SOURCE_SHA256=c563a232b0d456250b59d3e239fc7039957196a5fe7ced1d36626998bb1b1c60 \
NATIVE_S3_BUILD_MANIFEST_SHA256=7f3282483caf608a23850e33d845faf825a960263ea22c84ded567425860cd88 \
cargo build --release --locked --target-dir /workspace/build/n83-e1-sparse30-rank
python3 make_manifest.py \
  --workdir /workspace/cryptanalysis \
  --binary /workspace/build/n83-e1-sparse30-rank/release/native_packed_index \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 63 --execution-cpu 63 --mem-nodes VERIFIED_NODE \
  --output /workspace/sparse30-rank-paired-manifest.json
sudo taskset -c 0-62 python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe /workspace/sparse30-rank-paired-manifest.json
sudo taskset -c 0-62 python3 /workspace/cryptanalysis/scripts/isolated_bench.py run /workspace/sparse30-rank-paired-manifest.json
```

CPU and NUMA values are examples until verified against the host topology.
The service accepts a Tier 0 stage wall-time comparison only after all four
exact pairs and strict host/noise gates pass. A complete IC one-target
comparison uses the repository's separate relation and recovery accounting.

## Frozen Tier 1 instance comparison

The [Tier 1 protocol](tier1_protocol.json) binds the earlier stage protocol
by SHA-256 and keeps the same public target, source, modes, pair certificate,
and 29.9-million-state cap. It freezes eight alternating pairs and a
300-second limit per arm. The [Tier 1 generator](make_tier1_manifest.py)
checks both frozen arm receipts, restores the pinned source, verifies the
candidate screen, and writes the benchmark runner's exact expected-field and
expected-result contract. The output records the allocation receipt as a
hashed artifact. A dry-run manifest using a placeholder executable passed
`require_manifest` against the Tier 1 runner; it is a schema check, not a
timing receipt.

Run this protocol from a checkout containing both the sparse30 experiment
and the merged Tier 1 runner from [PR #759](https://github.com/aburan28/cryptanalysis/pull/759).
On a separate, otherwise idle Linux Pod, first save an operator allocation
receipt as JSON with `provider` and `instance_id` fields matching the
arguments below. Include the provider's image, CPU and memory allocation,
and creation time when available; omit API credentials. Choose a CPU from
`probe-host` that is present in the Pod affinity mask. After building the
same release binary described above, run:

```sh
python3 /workspace/cryptanalysis/experiments/koblitz-n83-index-design-20260929/packed_index_e1_sparse30_rank_20261011/make_tier1_manifest.py \
  --workdir /workspace/cryptanalysis \
  --binary /workspace/build/n83-e1-sparse30-rank/release/native_packed_index \
  --provider runpod --instance-id POD_ID \
  --allocation-receipt /workspace/receipts/runpod-allocation.json \
  --cpus SELECTED_CPU --execution-cpu SELECTED_CPU \
  --output /workspace/sparse30-rank-tier1-manifest.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe /workspace/sparse30-rank-tier1-manifest.json
timeout 6600 python3 /workspace/cryptanalysis/scripts/isolated_bench.py \
  run /workspace/sparse30-rank-tier1-manifest.json
```

The wrapper reports verified bounded-stage work. Preserve all eight pair
records, source and input hashes, native phase timings, process CPU and
memory observations, and any timeout or invalid row. A Tier 1 stage speedup
requires complete exact pairs, stable artifacts, no observed cgroup throttle
or memory-failure event, and the runner's 95% paired bootstrap lower bound
above 1. Report its provider and instance ID with the ratio. The separate
one-target IC comparison retains the relation and recovery accounting in
`AGENTS.md`.
