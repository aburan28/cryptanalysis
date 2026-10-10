# Paired online U14 unit-gauge panel

The [manifest generator](make_isolated_manifest.py) pairs mode 126's
per-addend unit actions with mode 127's grouped accumulator gauge on
frozen fixture indices `0,16,32,48,64,80,96,112,128`, five repetitions.
Both arms use the same executable, U14 table, scalar, field backend, and
expected point. Its timer includes scalar reduction, digit staging,
lookup, unit or gauge operations, mixed additions, inversion, formatting,
and expected-point verification. Table preparation is reported separately.

Build and verify the exact source on the qualifying Linux host, then
generate a new receipt for that host's executable and raw outputs. Use
that receipt and the host's actual isolated CPU partition:

```sh
python3 experiments/prime-j0-u14-gauge-20261010/make_isolated_manifest.py \
  --binary /absolute/path/to/eisenstein_fixed \
  --receipt /absolute/path/to/host-verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /absolute/path/to/paired-manifest.json
python3 scripts/isolated_bench.py probe /absolute/path/to/paired-manifest.json
```

The CPU and NUMA values above are examples. The archived macOS receipt
binds a different binary and must not be presented as a Linux receipt.
Preserve rejected preflights, raw failures, noise-gate results, and both
verified output points. Report a CPU ratio only when the strict host
isolation and every paired correctness gate pass.
