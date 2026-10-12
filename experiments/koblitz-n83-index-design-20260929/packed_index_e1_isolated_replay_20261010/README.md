# Isolated replay of the N83 E-1 canonical root stage

This adapter runs the exact full-scan and zero-gap canonicalization arms on
one frozen public N83 target through the repository's isolated CPU benchmark
service. It verifies each native result against the published stage row and
emits the native target-stage interval as `online_ms`. The service then binds
paired timings to its host isolation, code, input, and noise receipts.

The benchmarked stage is the target-dependent point-decomposition probe after
the reusable root index is ready. Its clock includes query preparation,
batched S3 roots, root conversion and canonicalization, exact lookup, and
native relation checks. The wrapper's result comparison and native fixture
checks stay outside that native interval. The workload, pair-state cap, and
status are frozen by the [canonicalization experiment](../packed_index_e1_canonical_20261009/README.md).

## Prepare on a qualifying Linux host

Use a checkout containing the merged N83 experiment files and a local crypto
checkout containing commit `904f0f844f3c1e69e8d22ae5e60ecd56e6648611`.
Build the native binary on that host from the frozen source. For example,
from `experiments/koblitz-n83-index-design-20260929/packed_index_e1_canonical_20261009`:

```sh
CRYPTO_REPO=/workspace/crypto python3 -c 'import json,run; run.ensure_crypto_snapshot(); run.build(json.load(open("protocol.json")))'
```

Generate the manifest from this adapter directory, replacing CPU, NUMA, and
cgroup values with the verified host configuration:

```sh
python3 make_manifest.py \
  --workdir /workspace/cryptanalysis \
  --binary /tmp/n83-packed-index-e1-target/release/native_packed_index \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \
  --output /workspace/isolated-bench/n83-e1-canonical.json
```

From the repository root, inspect the strict preflight before submitting:

```sh
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/n83-e1-canonical.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit /workspace/isolated-bench/n83-e1-canonical.json
```

The service writes raw stdout/stderr, per-run host counters, pairs, and a
summary under its `results/<job-id>/` directory. The wrapper's stdout embeds
each complete native JSON result as base64, followed by a compact line with
the measured interval and a paired correctness certificate. A result gets
`verified=1` only when its frozen identifiers, status, first-witness samples,
operation counts, and native control match the published row. The service
requires every pair and host noise gate to pass before publishing its timing
ratio. This receipt addresses stage performance; the single-target IC metric
still uses a complete verified target solve and matched rho reference.
