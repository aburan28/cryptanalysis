# Tiered CPU benchmark service

The benchmark runner is [scripts/isolated_bench.py](../scripts/isolated_bench.py).
It accepts frozen JSON manifests, serializes every job through one persistent
SQLite queue and an exclusive worker lock, and records raw output and host
counter snapshots for each reference/candidate solve. It does **not** publish
a speedup unless every pair verifies, matches the declared input fields, and
passes the selected tier's preflight and noise gates. Tier 0 runs the service
on housekeeping CPUs; its benchmark subprocesses enter the isolated partition.
Tier 1 runs both variants on one pinned CPU exposed by the same cloud instance.

## Tier 0: host-isolated comparison

The strict preflight requires a physical Linux host with administrative
control, an empty cgroup v2 `cpuset.cpus.partition=isolated` partition whose
exclusive effective CPU and NUMA sets match the manifest, full SMT sibling
coverage, `cgroup.events populated 0` across descendants, `nohz_full` on
those CPUs, a fixed `performance` frequency, no CPU
quota, no overlapping effective IRQ affinity, a housekeeping-only service
affinity, and `numactl`. Version 1 pins each benchmark process and all its
threads to **one declared logical CPU** inside the isolated partition and
binds memory to **one declared NUMA node**. This supports the single-thread
rho comparison; multiworker experiments need an extension that proves each
worker's thread affinity. Every run is invalidated by CPU
throttling, OOM, IRQ or softirq time, interrupt-count changes, steal time,
involuntary context switches, timeout, nonzero exit, or missing
`verified=1`/`online_ms`. Raw failures are retained.

This is a deliberately stringent host gate. `cpuset` and a container's visible
CPU list alone cannot prove that other tenants have no host-level contention.
RunPod Pods use Tier 1 when they pass its separate instance-scoped gate.
[Linux's cgroup v2 documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
defines the isolated partition and exclusive CPUs. [Linux's CPU isolation
guide](https://docs.kernel.org/admin-guide/cpu-isolation.html) explains tick,
RCU, IRQ, and SMT considerations. The runner checks the effective state,
not just the requested configuration.

## Tier 1: cloud-instance comparison

Set `isolation.tier` to `tier1` and retain a sanitized, immutable provider
allocation JSON file in `artifacts`. The file and the manifest's
`isolation.allocation` must agree on nonempty `provider` and `instance_id`;
the manifest gives its absolute path as `receipt`. Do not put provider API
keys in either file. Tier 1 version 1 accepts one frozen workload case and
one pinned exposed CPU, with at least five alternating reference/candidate
pairs. Both variants use the same instance, executable limits, target, and
measurement boundary. A multiworker timing claim needs a separate extension
that records and verifies every worker's placement.

For a Pod whose visible CPU is `4`, the tier-specific manifest fields are:

```json
{
  "repetitions": 5,
  "isolation": {
    "tier": "tier1", "cpus": "4", "execution_cpu": 4,
    "mem_nodes": "0", "cgroup": "/sys/fs/cgroup",
    "allocation": {
      "provider": "runpod", "instance_id": "POD_ID",
      "receipt": "/workspace/receipts/POD_ID-allocation.json"
    }
  },
  "artifacts": ["/workspace/receipts/POD_ID-allocation.json"]
}
```

This excerpt belongs in an otherwise complete schema-1 benchmark manifest;
its allocation receipt must contain the same `provider` and `instance_id`.
Set `cgroup` to the runner's actual cgroup path from `/proc/self/cgroup`,
which may be the mounted `/sys/fs/cgroup` root inside a container. `probe`
reports any unmet Tier 1 requirement before a pair is dispatched.

The Tier 1 preflight checks Linux cgroup v2, the runner's actual cgroup,
effective cpuset and affinity for the declared CPU, allocation identity,
CPU model and topology, and availability of quota, pressure, memory, and
steal-time counters. It does not require host root, a host-isolated partition,
`nohz_full`, fixed frequency, IRQ exclusion, or `numactl`. The child inherits
the verified cgroup and is pinned with `sched_setaffinity`. Each pair records
raw counters, process CPU usage, memory events, source and binary hashes,
both answers, and exact run order. Any throttle, OOM, steal-time increment,
major fault, failed verification, timeout, changed input, or changed source
invalidates that pair. Interrupts, pressure, context switches, and frequency
readbacks remain visible in the receipt; they are not host-exclusivity proofs.

Completed Tier 1 results expose an observed median paired ratio. The
`paired_speedup` field is populated only when a deterministic 95% paired
bootstrap interval across the repeated pairs has lower bound above 1.
Report the provider, instance ID, Tier 1 label, ratio, interval, and
observable limits together. A Tier 1 receipt establishes an instance-scoped
result, while Tier 0 establishes the stronger host-isolated result.

The benchmark executable owns the `online_ms` interval. The manifest must
describe that timer's boundary; the runner cannot infer it from process
launch. The runner also records outer elapsed time, executable SHA-256,
host/kernel/CPU topology, cgroup state, raw stdout/stderr, per-CPU interrupt
and steal counters, cgroup throttle/OOM counters, and child involuntary
context switches. Benchmark children receive a fixed minimal environment;
the provisioning API key is not passed into them. A controlled result still needs source review of the
executable's timer and correctness check.

## Provisioning checklist for the host administrator

1. Use a dedicated physical Linux host or a provider contract with equivalent
   host-level CPU and memory-node exclusivity. Reserve at least one separate
   housekeeping CPU. Record CPU thread siblings and NUMA node membership.
2. Configure kernel `nohz_full` for all benchmark CPUs and move IRQs to
   housekeeping CPUs. Enable cgroup v2 `cpuset`; create an isolated partition
   with `cpuset.cpus`, `cpuset.cpus.exclusive`, and `cpuset.mems` set to the
   chosen resources. Verify the corresponding `.effective` files and
   `cpuset.cpus.isolated` readback. Keep the service outside that partition.
3. Set the selected CPUs' `performance` governor and equal minimum and
   maximum frequency. Remove CPU quotas from the benchmark cgroup and its
   ancestors. Install `numactl` and the same compiler/runtime used for both
   variants. These changes should be made by the host administrator because
   they affect all workloads on that machine.

The runner's `probe-host` command is read-only and can be run on any Linux
allocation before building binaries:

```sh
python3 scripts/isolated_bench.py probe-host
```

On a prepared host, use `probe MANIFEST.json` to see every unmet strict
condition. `run` refuses to launch a measurement when the preflight fails.

## Serial service and dispatch

Use a persistent directory, such as `/workspace/isolated-bench`, for the
queue and receipts. Start exactly one service process on housekeeping CPUs.
For example, under a service manager whose CPU affinity is set to the
housekeeping set:

```sh
python3 /workspace/cryptanalysis/scripts/isolated_bench.py --queue-root /workspace/isolated-bench serve
```

`serve` holds both a queue lock and a fixed host-wide lock under `/run/lock`
for its whole lifetime. A second server, even with a different queue
directory, or a direct run refuses to start. If the host also uses the
`exp-run` launcher, start the service with its existing serial lock:

```sh
python3 /workspace/cryptanalysis/scripts/isolated_bench.py \
  --queue-root /workspace/isolated-bench \
  --shared-job-lock /workspace/experiment-runs/.serial.lock serve
```

The service takes this shared `flock` for each complete benchmark job,
including preflight and result writing, then releases it before the next
job. A job remains `queued` while another launcher holds the lock. The
same option applies to a direct `run`. This coordinates with existing
`exp-run` jobs, including jobs queued before the service starts, because
their launch scripts already hold that file during execution. Use one
lock file on a local filesystem for every launcher on the host; a launcher
that skips it is outside the one-job guarantee. Keep the SQLite queue on a
single-host local filesystem; SQLite WAL and file locks are not a
distributed scheduler. The service marks any job left `running` after a crash
as `interrupted`; it never silently resumes a partial panel. It takes queued
jobs in submission order, runs only one subprocess at a time, and records
`runs.jsonl`, `pairs.jsonl`, `preflight.json`, `manifest.json`, and
`summary.json` under `results/<job-id>/`. The queue can be reached over SSH
without opening a public HTTP port:

```sh
ssh BENCH_HOST 'cd /workspace/cryptanalysis && python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit -' < manifest.json
ssh BENCH_HOST 'cd /workspace/cryptanalysis && python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench status JOB_ID'
```

The RunPod API key, when available, is for provisioning the Pod. It is not
stored in a manifest, queue row, result file, or repository. The long-lived
service can then be reached through SSH. [RunPod's Pod documentation](https://docs.runpod.io/runpodctl/reference/runpodctl-remove-pods)
describes CPU Pods and SSH provisioning; it does not by itself certify
host-wide CPU/NUMA isolation.

## Replaying the j=0 rho comparison

Build the two C variants on the same Linux host, with identical source,
compiler, flags, and width-2 tau setup, changing only
`CA_J0_RHO_COVARIANT_WALK`. Link
`experiments/prime-j0-tau-20260930/large-rho-20261002/bench_rho_large.c`
to each static library:

```sh
cd /workspace/cryptanalysis
cmake -S . -B /workspace/build/j0-reference -DCMAKE_BUILD_TYPE=Release -DCA_CUPQC=OFF -DCA_WERROR=ON -DCA_J0_RHO_COVARIANT_WALK=OFF -DCA_J0_TAU_RHO_WIDTH=2
cmake -S . -B /workspace/build/j0-oriented -DCMAKE_BUILD_TYPE=Release -DCA_CUPQC=OFF -DCA_WERROR=ON -DCA_J0_RHO_COVARIANT_WALK=ON -DCA_J0_TAU_RHO_WIDTH=2
cmake --build /workspace/build/j0-reference --target cryptanalysis_static
cmake --build /workspace/build/j0-oriented --target cryptanalysis_static test_curve
mkdir -p /workspace/bin
cc -O3 -std=c11 -Iinclude experiments/prime-j0-tau-20260930/large-rho-20261002/bench_rho_large.c /workspace/build/j0-reference/libcryptanalysis.a -lm -lpthread -o /workspace/bin/j0-rho-reference
cc -O3 -std=c11 -Iinclude experiments/prime-j0-tau-20260930/large-rho-20261002/bench_rho_large.c /workspace/build/j0-oriented/libcryptanalysis.a -lm -lpthread -o /workspace/bin/j0-rho-oriented
```

Build and correctness checks are outside the online timer. Generate the
exact 160-target panel from the frozen scalar law with
[make_j0_isolated_manifest.py](../scripts/make_j0_isolated_manifest.py).
The generator calls each executable's `--print-target` fixture mode, checks
that both produce the same public point, and freezes the expected scalar in
the manifest. The timed `--public-target` command receives the point
coordinates and walk seed, with no expected scalar in its arguments. Its
`online_ms` covers the rho solve and independent point replay; fixture
construction stays outside that interval:

```sh
python3 scripts/make_j0_isolated_manifest.py \
  --reference /workspace/bin/j0-rho-reference \
  --candidate /workspace/bin/j0-rho-oriented \
  --workdir /workspace/cryptanalysis \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \
  --output /workspace/isolated-bench/j0-rho-panel.json
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/j0-rho-panel.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit /workspace/isolated-bench/j0-rho-panel.json
```

CPU IDs and NUMA nodes above are examples; use the host's verified topology.
For any Sage manifest, use the absolute checked repository `sage` launcher
and save its `--runtime-info` receipt before measurement, as required by
[AGENTS.md](../AGENTS.md).
IC comparisons must also carry the candidate, workload, and run IDs and the
stage accounting required by that file; the service enforces the environment
and pairing but does not replace the IC measurement contract.

The prior [j=0 rho panel](../experiments/prime-j0-rho-coordinate-canon-20261002/README.md)
was run on a heavily loaded Mac. Its timing ratios remain exploratory until
replayed through a qualifying isolated host. Historical results elsewhere
in the repository need an isolation audit before they are treated as
controlled performance claims.

## Frozen manifest and result contract

Each `cases` entry is one previously unseen target. Freeze its exact input
point in `expected_fields`; the reference and candidate must both echo those
fields in the final timed output row. The runner rejects a pair even when
both programs report the same wrong target. The executable must print
`online_ms=<positive number> verified=1` and a result field after checking its
answer. The runner also compares that result to the frozen `expected_result`
in the manifest; keep that expected answer out of the solver command line.
The runner records the complete stdout/stderr and hashes the listed
source/build artifacts and each executable. For example:

```json
{
  "schema": 1,
  "workdir": "/workspace/cryptanalysis",
  "isolation": {
    "cgroup": "/sys/fs/cgroup/benchmark-isolated",
    "cpus": "4-5",
    "execution_cpu": 4,
    "mem_nodes": "0"
  },
  "artifacts": ["/workspace/cryptanalysis/src/solver.c"],
  "timeout_s": 120,
  "repetitions": 3,
  "measurement_boundary": "First target-dependent step through scalar replay",
  "pair_fields": ["curve", "target_x", "target_y"],
  "result_field": "scalar",
  "cases": [
    {
      "id": "target-0",
      "expected_fields": {"curve": "curve-id", "target_x": "123", "target_y": "456"},
      "expected_result": "789",
      "reference": ["/workspace/bin/reference", "--target", "target-0"],
      "candidate": ["/workspace/bin/candidate", "--target", "target-0"]
    }
  ]
}
```

The CPU and NUMA IDs above are examples; choose them from verified host
topology. All paths must be absolute paths on the benchmark host. The
benchmark's internal online timer and correctness replay need source review:
this service cannot infer their boundaries or prove `verified=1` on its own.
For Sage manifests, use the absolute checked repository `sage` launcher and
save its `--runtime-info` receipt before measurement, as required by
[AGENTS.md](../AGENTS.md).

For IC comparisons, retain candidate, workload, and run IDs plus the stage
accounting required by AGENTS.md. Report the exact paired one-target online
interval and the same target point for rho and IC. Historical CPU ratios
without an equivalent isolation receipt remain exploratory until replayed
under a qualifying host.
