# j=0 rho orbit reducer results

Both reducers are experimental CMake options and are **off by default**.
The legacy hash-minimum rho walk remains the library default.

## Frozen one-target workload

The primary point and expected scalar are in `rho-orbit-primary-target.json`.
It fixes `j0-56`, a point of order 53,624,256,071,278,747, a previously
generated target `Q=(282423703968320088,2098065311724316995)`, and walk
seed 20,261,008. The benchmark source contains `G` and `Q` but not the
expected scalar. The reported online
interval starts immediately before `ca_curve_solve`, charges its
target-dependent setup, walk, collision recovery, and independent `x*G=Q`
replay, and ends only after that replay. Curve construction and point loading
precede the interval. The separate Python manifest generator independently
reconstructs `Q` from the frozen scalar and checks `order*G` is infinity.

The [serial large-target smoke record](rho-orbit-primary-smoke.json) retains
the two full solve outputs, exit codes, and source/build hashes. Both arms
verified the same scalar and used exactly 255,104,119 group operations and
80 replay operations. Its raw local wall times are exploratory; the record
sets `cpu_speedup_claim` and `isolation_receipt` to `null`.

## Correctness and operation evidence

The smaller target in `rho-orbit-one-target.json` fixes `glv-j0-32`,
`Q=(11525401,2537560930)`, and walk seed 20,261,007. It gives fast
operation diagnostics across walk seeds:

| Arm | Default? | 32-seed verified replays | Median group operations | Seeds with fewer operations than legacy |
| --- | --- | ---: | ---: | ---: |
| Legacy hash | Yes | 32/32 | 4,343 | — |
| Coordinate minimum | No | 32/32 | 5,354 | 14/32 |
| Factored hash | No | 32/32 | 4,343 | 0/32; exactly equal in 32/32 |

The [coordinate operation rows](rho-orbit-ops-coordinate.json) and
[factored operation rows](rho-orbit-ops-factored.json) retain each exit code,
raw stdout/stderr, binary/build hashes, and `cpu_speedup_claim: null`.
These are 32 independent rho solves of **the same small public target** under
different walk seeds, a secondary operation-count diagnostic. They are not
32 distinct targets, a throughput result, or controlled CPU timing.
The coordinate reducer changes the walk function, so one paired seed need
not have the same group-operation count. The factored reducer preserves the
exact legacy representative and walk trajectory.

Direct tests compare all four output words and the exponent-correction
power `k` against the legacy hash loop for all six rotations of 128
deterministic subgroup points on each of three named j=0 curves. They also
cover identity, x=0, and y=0. The coordinate reducer is checked by applying
`psi^k` and `lambda^k` independently. The `curve` and `rho` C tests passed
in release and warnings-as-errors UBSan builds for each experimental arm.
The full remaining test suite is left to CI; this result makes no claim for
x86-64 or any untested hardware backend.

Local wall times are retained in raw rows solely to audit the timer and are
exploratory on this contended host. **CPU speedup is unknown.** The factored
hash saves arithmetic within a walk step, but no host-isolated measurement
has established a lower one-target solve time. The coordinate result does
not justify making that arm the default.

## Reproduction on an isolated host

Build both executables from the same source revision with identical compiler
and optimization flags. The relevant CMake choices are:

```sh
cmake -S . -B /workspace/rho-hash -DCMAKE_BUILD_TYPE=Release -DCA_WERROR=ON -DCA_BUILD_SHARED=OFF -DCA_BUILD_TOOLS=OFF -DCA_BUILD_TESTS=OFF -DCA_BUILD_RHO_ORBIT_BENCH=ON -DCA_RHO_J0_COORDINATE_ORBIT=OFF -DCA_RHO_J0_FACTORED_HASH=OFF
cmake -S . -B /workspace/rho-factored -DCMAKE_BUILD_TYPE=Release -DCA_WERROR=ON -DCA_BUILD_SHARED=OFF -DCA_BUILD_TOOLS=OFF -DCA_BUILD_TESTS=OFF -DCA_BUILD_RHO_ORBIT_BENCH=ON -DCA_RHO_J0_COORDINATE_ORBIT=OFF -DCA_RHO_J0_FACTORED_HASH=ON
cmake --build /workspace/rho-hash --target ca_rho_orbit_bench
cmake --build /workspace/rho-factored --target ca_rho_orbit_bench
```

On the prepared Linux host, generate the manifest with its **actual** CPU,
NUMA node, and isolated cgroup. For the factored arm:

```sh
python3 experiments/prime-j0-cost-aware-chain/make_rho_orbit_manifest.py --reference /workspace/rho-hash/ca_rho_orbit_bench --candidate /workspace/rho-factored/ca_rho_orbit_bench --candidate-kind factored --cgroup /sys/fs/cgroup/benchmark-isolated --cpus 4-5 --execution-cpu 4 --mem-node 0 --output /workspace/rho-orbit-manifest.json
python3 scripts/isolated_bench.py probe /workspace/rho-orbit-manifest.json
```

The CPU/node values above are examples and **must be replaced** from the
host topology. Submit the manifest to the persistent serial service only
after its strict preflight passes. The service runs one benchmark process at
a time; `docs/ISOLATED_BENCHMARKS.md` defines its receipt and noise gates.
The same generator accepts `--candidate-kind coordinate` with a matching
coordinate build; `--case glv-j0-32` selects the small diagnostic point.
Manifest generation on macOS validated schema and file
custody only; it was not a Linux host-isolation receipt.
