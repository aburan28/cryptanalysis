# Paired certified versus fixed-limb U14 panel

The [manifest generator](make_isolated_manifest.py) pairs the two modes
on fixture indices `0,16,32,48,64,80,96,112,128` for five repetitions.
It verifies the candidate executable, native test receipt, frozen source
and inputs, and both 129-point fixture outputs before emitting a manifest.
Generate it on the intended Linux host after building and checking this
exact source snapshot there:

```sh
python3 experiments/prime-j0-fixed-limb-voronoi-20261010/make_isolated_manifest.py \
  --binary /absolute/path/to/eisenstein_fixed \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /absolute/path/to/paired-manifest.json
python3 scripts/isolated_bench.py probe /absolute/path/to/paired-manifest.json
```

The CPU and NUMA IDs are examples; the host receipt must provide the
actual isolated partition. The executable's `online_ms` begins after
fixture loading, scalar decoding, reciprocal and fixed-basis preparation,
and table setup. It includes scalar reduction, the two reciprocal
products, certificate and coordinate construction or fallback, recoding,
table lookup, point operations, affine conversion, and expected-point
verification. The paired host runner retains every timeout, failure,
noise rejection, and successful result. A container affinity mask alone
does not satisfy the isolation preflight.

A local structural check emitted nine cases and five repetitions with
manifest SHA-256
`147da3ac939c588742ae548f9bd404ad6c339bd3bf098e698b97dcb300d5414b`.
Its CPU, NUMA, and cgroup fields were placeholders; it is not a host
isolation receipt or a timing result.
