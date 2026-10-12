# One-target paired-lattice rho startup result

## Correctness gate

The frozen public `glv-j0-32` target is `(2931638641, 2937820554)`;
the independent fixture construction gives scalar `9654443` relative to
base `(481899190, 1998487369)`. The rho seed is
`7442274709634911821`. Only the public target coordinates and seed are
passed to the solver. Each invocation creates an empty distinguished-point
table and recovers and replays the scalar for this one target.

Release and UBSan ABBA panels both passed all four serial solves.
The raw records are `panel_local.json` and `panel_ubsan.json`. Both arms
returned scalar `9654443`, independently replayed it, and had the same
rho trajectory counters: 4,371 reference-equivalent group operations,
231 distinguished-point table entries, eight multiplier-table evaluations,
three restart evaluations, and 789 reference-equivalent startup operations.
The budget count maintains the reference cap and is **not** candidate
physical point work.

The candidate prepared one target-specific 1,104-byte joint point table:
two τ maps, ten doublings, eight mixed additions, and one inversion.
Across the 11 startup evaluations, it performed 147 τ steps, 84 mixed
additions, 50 rotations, and 11 output inversions, with 44 recodings and
44 pair scores. These are observed point-work diagnostics, not a complete
operation-equivalent speedup model for the rho solve.

## Local timing status

The two Release reference `online_ms` values were 0.487 and 0.509;
the two paired2 values were 0.532 and 0.430. Candidate preparation was
0.057 and 0.005 ms in those trials, respectively. The UBSan timing values
are retained in `panel_ubsan.json` for correctness diagnostics only.
The first and second candidate runs differ materially even though their
trajectory counters match. This host has no qualifying CPU isolation
receipt, so the CPU speedup and its uncertainty are **unknown**. The raw
panel files deliberately set `cpu_speedup_claim` and `isolation_receipt`
to `null`.

For a controlled one-target timing study, build the same Release binary
on a qualifying physical Linux host, then use `make_isolated_manifest.py`
with that host's absolute binary, repository, cgroup, CPU, and NUMA paths.
The manifest binds the exact fixture and its independently expected scalar
to the serial runner in `scripts/isolated_bench.py`. The runner must pass
its strict preflight and per-run noise gates before any CPU ratio is
reported. Its repetitions replay the **same one target** with an empty
table each time; they are not a batch-throughput workload. Even a passing
one-target receipt gives run-to-run uncertainty for that point, not
variation over a population of targets.

No automatic rho routing change is warranted by this gate. The paired2
path remains opt-in. Academic novelty of the underlying scalar scheme is
unproved.
