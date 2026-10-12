# Paired Eisenstein versus four-limb U14 point panel

The [manifest generator](make_isolated_manifest.py) pairs modes 125 and
126 on frozen fixture indices `0,16,32,48,64,80,96,112,128` for five
repetitions. It checks the local correctness receipt, executable, source,
input, and raw fixture outputs before emitting a manifest. Build and
verify the same source on the intended Linux host, then use that host's
actual isolated cgroup, CPUs, and NUMA node:

```sh
python3 experiments/prime-j0-u256-point-20261010/make_isolated_manifest.py \
  --binary /absolute/path/to/eisenstein_fixed \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /absolute/path/to/paired-manifest.json
python3 scripts/isolated_bench.py probe /absolute/path/to/paired-manifest.json
```

The CPU and NUMA IDs above are examples. Both point-table representations
are prepared before the online interval. The timer then includes scalar
reduction, Voronoi selection, recoding, lookup, point work, affine
finalization, and expected-point verification. Preserve rejected host
preflight and noise-gate rows. Report a wall-time improvement only when
both outputs verify under the strict paired run.
