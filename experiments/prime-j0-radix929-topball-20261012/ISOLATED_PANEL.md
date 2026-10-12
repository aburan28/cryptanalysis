# Paired radix-929 versus radix-943 isolated CPU panel

The panel pairs the native format-174 radix-943 path with the opt-in
radix-929 bounded top-state path on exactly the same secp256k1 public point.
The default workload fixes 32 indices `0,16,...,496` from the independently
generated 512-case holdout, with seven alternating repetitions per index.
Both arms use the same binary, generator, scalar and expected point. The
single-case entrypoints assert the independently supplied result within
their reported online interval.

`make_isolated_manifest.py` first runs the full native atlas and 512-point
replay against the exact binary and overlay record. It then pins the binary,
source, proof, fixture, runner and plan artifacts in the manifest and
validates the manifest's schema and pair fields. It does not start a timed
job. On the qualifying host, build the disposable native crate from the
accepted source snapshot, then generate a host-specific manifest:

```sh
cd /workspace/cryptanalysis
export CARGO_TARGET_DIR=/workspace/build/radix929-native
cargo fetch --locked --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml
python3 experiments/prime-j0-radix929-topball-20261012/native_overlay.py \
  /workspace/build/radix929-overlay --build
python3 experiments/prime-j0-radix929-topball-20261012/make_isolated_manifest.py \
  --repo-root /workspace/cryptanalysis \
  --binary "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --overlay-record /workspace/build/radix929-overlay/overlay.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus HOST_ISOLATED_CPU_SET --execution-cpu HOST_EXECUTION_CPU \
  --mem-node HOST_NUMA_NODE \
  --output /workspace/isolated-bench/radix929-vs-943.json
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/radix929-vs-943.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench \
  submit /workspace/isolated-bench/radix929-vs-943.json
```

Replace the uppercase placeholders with the host administrator's verified
isolated partition, selected logical CPU and NUMA node. The benchmark service
must be running on housekeeping CPUs and serializes the submitted job with
its host-wide lock. The fixture and table preparation occur before the
binary's online timer; recoding, lookup, unit action, point work, affine
conversion and point verification are inside it. The runner's preflight and
noise gates decide whether the timing rows qualify. Preserve raw rejections,
interrupts, throttling, setup memory, and every paired case in the service
receipt. Compare verified online intervals only when all required gates pass.

The current Runpod Pod probe found a container without the required
host-level isolated partition. This protocol is ready for a physical host
with administrator-controlled CPU, NUMA, frequency and IRQ configuration;
no benchmark timing from that Pod is promoted.
