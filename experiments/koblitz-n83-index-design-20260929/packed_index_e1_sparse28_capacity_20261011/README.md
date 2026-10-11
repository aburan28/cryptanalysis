# E-1 sparse28 root-directory capacity result

The sparse28 exact root directory reduced full-key probes from **69,190,310
to 7,415,319** on the frozen N83 one-target, 29.9-million-state workload.
In an A–B–B–A local panel, target-process CPU medians were **45.440 s for
sparse26** and **35.591 s for sparse28**; sparse28 was lower in both adjacent
pairs. The root table grew by **37,748,736 bytes (36 MiB)**. All four runs
completed under the 5,500 MiB RSS cap with the same exact behavior and
`state_cap_no_relation` status. This is an exploratory CPU result pending a
physical-host isolation receipt.

This is proposal `Q2026101132`, curve `EC1N83Ckb1h876c2921cb64`, workload
`63dd0929cf33`, and source SHA-256
`9969359d0605bdc8ef1a5f8ef2e3d204055ae391e14ff6f5bec3c0bdcca1463f`.
The full IC candidate ID remains `null` for this bounded point-decomposition
stage. The one public subgroup target, 30,977,592 usable factor-base points,
186,612 folded columns, 29,900,000 sampled pair states, one orientation per
state, and 5,500 MiB cap are frozen in [the workload](workload.json) and
[stage manifest](stage_manifest.json). Both arms use the same cached x/y roots,
point-partner generator, exact 16-byte root keys, singleton tags, first-witness
rule, and compiled binary. Only the SplitMix64 bucket prefix grows from 26 to
28 bits.

## Paired exploratory panel

| Run | Mode | Target CPU (s) | Target wall (s) | Full-key probes | Peak RSS (bytes) |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | sparse26 | 46.715 | 63.530 | 69,190,310 | 5,449,351,168 |
| 2 | sparse28 | 37.770 | 111.147 | 7,415,319 | 3,823,042,560 |
| 3 | sparse28 | 33.412 | 78.049 | 7,415,319 | 5,433,032,704 |
| 4 | sparse26 | 44.165 | 166.246 | 69,190,310 | 4,198,727,680 |

The exact root-table allocations were 1,237,818,368 bytes for sparse26 and
1,275,567,104 bytes for sparse28. The large wall-time and RSS variation
records host contention; the CPU comparison is a stage diagnostic, not a
controlled wall-time claim. [summary.json](summary.json) and the four raw
run records retain index-build CPU, target CPU, target query preparation,
partner generation, partner checking, phase residual, memory, status, and
source/input hashes. The exclusive target phase clocks sum to each charged
target-stage wall interval. Index construction and cached-coordinate
preparation occur before that interval.

## Exactness and replay

The four capacity runs agree on 15 exact invariants, including every indexed
state and root count, operation counts, lookup first-witness sample, target
outcome, and relation status. A separate
[full audit](audit_sparse28.json) on frozen one-target workload `981ac530e67e`
compared all 4,000,000 generated partner pairs after Frobenius rotation with
the original S3 evaluator; all 8,000,000 roots agreed. That 2-million-state
workload is a correctness control. The capacity comparison above retains its
own workload ID and accounting.

Run `python3 verify.py --inputs-root PATH` from this directory to check the
source, binary and input receipts, canonical workload IDs, raw-run hashes,
phase sums, memory cap, exact invariants, and audit. `PATH` is the
`adaptive_all_orientations_20261004/inputs` directory. In a full checkout it
is the default. A fresh checkout can restore the pinned public crypto source
with `python3 restore_crypto_source.py` and then rebuild with Cargo; the source
tree and Rust source digests are checked before use. To reproduce the paired
panel in an isolated copy, run `python3 run.py --binary PATH --inputs-root PATH`
with a binary built from this source. The runner refuses to overwrite raw
results and freezes the input protocol before the first run.

The 2-million-state sparse28 screen in the parent exploration had similar
target CPU to sparse26; this capacity result answers the larger-index question.
The repository [CPU isolation gate](../../../docs/ISOLATED_BENCHMARKS.md)
remains required for a controlled wall-time comparison.

## Tier 1 instance replay

The [Tier 1 protocol](tier1_protocol.json) binds the capacity protocol by
SHA-256 and keeps the same frozen public point, 29.9-million-state cap,
5,500 MiB RSS cap, exact lookup, and first-witness rule. It fixes eight
alternating sparse26/sparse28 pairs with a 300-second limit per arm. This
comparison is prioritized because sparse28 used less target process CPU in
both adjacent full-capacity pairs, while the existing Mac wall times vary
strongly with host load.

The [Tier 1 manifest generator](make_tier1_manifest.py) verifies the four
preserved capacity rows and full partner audit, checks the pinned public
source, and freezes the benchmark runner's expected fields and result. It
also hashes an allocation receipt whose `provider` and `instance_id` match
the supplied arguments. A dry-run manifest passed the Tier 1 runner's input
contract; this establishes the replay wiring, not a timing result.

Run on a separate idle Linux instance from a checkout containing the merged
Tier 1 runner. Save a JSON allocation receipt containing `provider` and
`instance_id`, plus the provider's image, CPU and memory allocation, and
creation time when available. Keep API credentials out of the receipt.
After building the pinned binary as above, select one CPU shown by
`probe-host` within the instance's affinity mask:

```sh
python3 /workspace/cryptanalysis/experiments/koblitz-n83-index-design-20260929/packed_index_e1_sparse28_capacity_20261011/make_tier1_manifest.py \
  --workdir /workspace/cryptanalysis \
  --binary /workspace/build/n83-e1-sparse28-capacity/release/native_packed_index \
  --provider runpod --instance-id POD_ID \
  --allocation-receipt /workspace/receipts/runpod-allocation.json \
  --cpus SELECTED_CPU --execution-cpu SELECTED_CPU \
  --output /workspace/sparse28-capacity-tier1-manifest.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe /workspace/sparse28-capacity-tier1-manifest.json
timeout 6600 python3 /workspace/cryptanalysis/scripts/isolated_bench.py \
  run /workspace/sparse28-capacity-tier1-manifest.json
```

Preserve every valid and invalid pair, including raw stdout/stderr, source
and input hashes, memory, phase sums, process CPU time, and observed
throttling or memory failures. A Tier 1 stage speedup requires eight exact
same-target pairs and a paired bootstrap 95% lower bound above 1. The full
one-target IC comparison also requires relation collection, rank, recovery,
and matched-rho accounting under the repository contract.

## Physical-host replay

`benchmark_stage.py` runs either frozen arm and checks the exact result fields,
including operation counts, first-witness lookup sample, control status, and
bounded-stage outcome. It emits the raw native JSON in base64 alongside the
native target-stage interval for the isolated benchmark service. Its wrapper
checks and process startup are outside that interval. The service retains raw
stdout, host counters, and the preflight receipt for every run.

On a Linux host with this checkout, build the pinned source once before
timing. The checked-in Cargo lockfile and the restored crypto source are part
of the build inputs:

```sh
cd /workspace/cryptanalysis/experiments/koblitz-n83-index-design-20260929/packed_index_e1_sparse28_capacity_20261011
python3 restore_crypto_source.py
python3 verify.py
NATIVE_S3_SOURCE_SHA256=9969359d0605bdc8ef1a5f8ef2e3d204055ae391e14ff6f5bec3c0bdcca1463f \
NATIVE_S3_BUILD_MANIFEST_SHA256=7f3282483caf608a23850e33d845faf825a960263ea22c84ded567425860cd88 \
cargo build --release --locked --target-dir /workspace/build/n83-e1-sparse28-capacity
```

Create a manifest with the host's actual isolated partition, execution CPU,
and NUMA node. The values below are examples; `probe` must accept the physical
host before `run` or queue submission:

```sh
python3 make_manifest.py \
  --workdir /workspace/cryptanalysis \
  --binary /workspace/build/n83-e1-sparse28-capacity/release/native_packed_index \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \
  --output /workspace/n83-e1-sparse28-capacity-manifest.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe /workspace/n83-e1-sparse28-capacity-manifest.json
```

The manifest builder verifies the frozen inputs and raw results before writing
the comparison. Its default four pairs alternate A–B and B–A, using the same
public target in each arm. The service's `online_ms` refers only to the
bounded point-decomposition stage; index construction and factor-base setup
remain separate in the raw phase record. A container allocation without the
required host-level isolation remains an exploratory replay.
