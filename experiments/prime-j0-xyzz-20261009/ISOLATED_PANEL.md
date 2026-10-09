# Isolated U14 XYZZ comparison panel

Compare deferred XYZZ separately with the U14 Jacobian path and the balanced
XYZZ path. Each comparison uses one Linux release binary, the same nine
public scalar fixtures (`0,16,32,48,64,80,96,112,128`), five repetitions,
and the serial runner's alternating AB/BA order. The executable timer starts
after fixture parsing, scalar decoding, lattice and table preparation; it
includes recoding, additions, affine conversion, and the expected-point
assertion. The service retains preparation cost, raw outcomes, counters, and
the strict isolation preflight alongside online timing.

On a prepared Linux host, build the standalone package from one immutable
repository snapshot and run `check_deferred_xyzz.py` there. Its receipt binds
the executable and all executed source files. Build both manifests from that
receipt and the same binary. The CPU IDs and cgroup below are examples; use
the host's verified isolated partition and NUMA node.

```sh
cd /workspace/cryptanalysis
CARGO_TARGET_DIR=/workspace/build/xyzz cargo build --locked --release \
  --manifest-path experiments/prime-j0-xyzz-20261009/Cargo.toml
python3 experiments/prime-j0-xyzz-20261009/check_deferred_xyzz.py \
  --binary /workspace/build/xyzz/release/prime-j0-xyzz-experiment \
  --output /workspace/isolated-bench/xyzz-native-check.json
python3 experiments/prime-j0-xyzz-20261009/make_deferred_isolated_manifest.py \
  --repo-root /workspace/cryptanalysis \
  --binary /workspace/build/xyzz/release/prime-j0-xyzz-experiment \
  --checker-receipt /workspace/isolated-bench/xyzz-native-check.json \
  --reference-mode jacobian --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /workspace/isolated-bench/xyzz-jacobian-deferred.json
python3 experiments/prime-j0-xyzz-20261009/make_deferred_isolated_manifest.py \
  --repo-root /workspace/cryptanalysis \
  --binary /workspace/build/xyzz/release/prime-j0-xyzz-experiment \
  --checker-receipt /workspace/isolated-bench/xyzz-native-check.json \
  --reference-mode balanced --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /workspace/isolated-bench/xyzz-balanced-deferred.json
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/xyzz-jacobian-deferred.json
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/xyzz-balanced-deferred.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit \
  /workspace/isolated-bench/xyzz-jacobian-deferred.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit \
  /workspace/isolated-bench/xyzz-balanced-deferred.json
```

Submit only after both probes pass. The long-running service executes one
subprocess at a time and records failed, timed-out, and noise-rejected pairs.
Report the paired online intervals and uncertainty for both comparisons,
with table preparation separate. A rejected preflight or incomplete pair
keeps the controlled speedup unknown. The current RunPod CPU Pod is a Docker
allocation with cgroup v1 and fails the strict host preflight; regenerate
these manifests on a qualifying host rather than reusing its absolute paths.
