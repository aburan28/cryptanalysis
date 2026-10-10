# Paired fixed-limb versus hybrid U14 panel

The [manifest generator](make_isolated_manifest.py) pairs modes 122 and
123 on frozen fixture indices `0,16,32,48,64,80,96,112,128` for five
repetitions. It checks the local correctness receipt, executable, source,
input, and raw fixture outputs before emitting a manifest. Build and
verify the same source on the intended Linux host, then use the host's
actual isolated cgroup, CPUs, and NUMA node:

```sh
python3 experiments/prime-j0-hybrid-finalize-20261010/make_isolated_manifest.py \
  --binary /absolute/path/to/eisenstein_fixed \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /absolute/path/to/paired-manifest.json
python3 scripts/isolated_bench.py probe /absolute/path/to/paired-manifest.json
```

The CPU and NUMA IDs above are examples. The timer starts after input
loading and shared preparation, then includes all scalar-dependent work
through expected-point verification. Preserve rejected preflight and
noise-gate rows; report a speedup only when the strict paired run passes.
