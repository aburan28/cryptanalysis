# Split-terminal full scalar multiplication benchmark

This harness exposes the fixed-limb four-corner selector and its direct-gauge
reference through the same secp256k1 fixed-generator executable. Each command
warms its reusable table and decodes the scalar before `online_ms`; the timed
interval includes decomposition, all recodings and selection, point operations,
affine conversion, and the expected-point assertion. The output reports the
public scalar, base point, resulting point, table preparation time, retained
bytes, and `verified=1` after the point assertion succeeds. The selector is a
variable-time research implementation.

The [native patch](native.patch) applies to the source-pinned fixed-limb crate.
Run [materialize.py](materialize.py) with that parent crate to recreate the
source and [native-materialization.json](native-materialization.json) receipt.
Build the resulting crate with `cargo build --release --bin eisenstein_fixed`.
The benchmark commands are:

```sh
eisenstein_fixed --benchmark-scalar-unit-orbit-u256-tau-dual-rho0-direct-gauge-xyzz-tau-fixed-case FIXTURE INDEX
eisenstein_fixed --benchmark-scalar-unit-orbit-u256-tau-split-terminal-fixed-case FIXTURE INDEX
```

After this source is committed, [make_holdout.py](make_holdout.py) draws nine
new scalars disjoint modulo the group order from the 4,096-scalar development
panel, and independently computes their expected points. It requires the exact
clean frozen commit and refuses to overwrite the fixture. The fixture is then
committed before timing. [make_manifest.py](make_manifest.py) binds the native
source, executable, runner, fixture, expected inputs and outputs, complete
online boundary, resource partition, and allocation receipt into one immutable
paired manifest. It supports the host-isolated and instance-observed tiers in
[the runner protocol](../../docs/ISOLATED_BENCHMARKS.md).

The preexisting 4,096-scalar panel is a path and correctness control. The
prospective fixture and matched complete-operation run are the performance
experiment. A passing `probe` plus the runner's noise, correctness, and paired
uncertainty gates are required before a timing ratio becomes a measured result.

The existing RunPod pod was probed on 2026-10-11 with runner SHA-256
`f17ac062246de7bd68f0e8e94d941ee25cffb7a06d8d846700dc754403f39bc4`.
Its [raw host probe](runpod-probe.json) records a Docker cgroup-v1 process,
no visible isolated CPU partition, and no `nohz_full` CPUs. A separate
CryptoMiniSat solve was active on the pod during inspection. The scalar
benchmark was therefore not submitted there; the prospective fixture remains
unused for performance tuning.
