# Paired hybrid versus binary-GCD U14 panel

The [manifest generator](make_isolated_manifest.py) pairs modes 123 and
124 on frozen fixture indices `0,16,32,48,64,80,96,112,128` for five
repetitions. It checks the local correctness receipt, executable, source,
input, and raw fixture outputs before emitting a manifest. Build and
verify the same source on the intended Linux host, then use that host's
actual isolated cgroup, CPUs, and NUMA node:

```sh
python3 experiments/prime-j0-binary-inverse-20261010/make_isolated_manifest.py \
  --binary /absolute/path/to/eisenstein_fixed \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /absolute/path/to/paired-manifest.json
python3 scripts/isolated_bench.py probe /absolute/path/to/paired-manifest.json
```

The CPU and NUMA IDs above are examples. The timer starts after input
loading and shared preparation, then includes scalar reduction, recoding,
lookup, point work, representation conversion, inversion, formatting,
and expected-point verification. Preserve rejected preflight and noise
gate rows. A speedup requires a strict paired run with verified outputs.
