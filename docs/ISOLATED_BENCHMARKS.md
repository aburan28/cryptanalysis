# Tiered CPU benchmark service

The benchmark runner is [scripts/isolated_bench.py](../scripts/isolated_bench.py).
It accepts frozen JSON manifests, serializes every job through one persistent
SQLite queue and an exclusive worker lock, and records raw output and host
counter snapshots for each reference/candidate solve. Every receipt names its
measurement tier. Both tiers require verified matching answers, frozen inputs,
stable source and binary hashes, and complete paired runs. Tier 0 runs the
service on housekeeping CPUs; its benchmark subprocesses enter the isolated
partition. Tier 1 runs in a recorded cloud instance, including a RunPod Pod,
with a narrower, explicit claim.

## Measurement tiers and claim language

| Tier | Environment | Result the receipt can support |
| --- | --- | --- |
| `tier0_host` | Physical Linux host with audited exclusive CPU and NUMA partition, fixed frequency, and IRQ routing | Host-isolated paired wall-time result. |
| `tier1_instance` | Linux cloud instance or Pod with one pinned exposed CPU, recorded allocation receipt, observable cgroup throttle and memory-failure counters, and repeated matched pairs | Instance-scoped paired wall-time result, qualified by the recorded confidence interval. Host exclusivity remains unverified. |

Legacy schema-1 manifests without `measurement_tier` remain Tier 0. Tier 1
must be requested explicitly; failure of a Tier 0 preflight never silently
downgrades a run. For a Tier 1 speedup claim, the full panel must complete,
there must be at least eight alternating paired repetitions, and the 95%
bootstrap lower bound for the paired median ratio must exceed 1. With one
target, the interval resamples its paired repetitions; with at least five
targets, it resamples per-target medians. Other completed panels retain their
measured ratio but set `speedup_claim_eligible=false`. Name a qualifying
result a **Tier 1 instance-scoped paired speedup** and report the provider,
instance ID, ratio, interval, exact workload, timer boundary, and observed
throttling, memory failures, CPU steal and scheduling counters. A Tier 1
receipt cannot establish host-wide exclusivity or transfer its timing ratio
to another host. The allocation identity is backed by a hashed operator
receipt and is labeled self-reported; provider verification is a separate
audit.

Both tiers still require source review of the benchmark's internal timer and
correctness check. A stage benchmark can support a stage speedup; a complete
one-target IC speedup additionally requires the recovered scalar, independent
replay, the same public point and resource envelope for rho, and the phase
accounting in [AGENTS.md](../AGENTS.md).

## Tier 0 host-isolated result

The strict preflight requires a physical Linux host with administrative
control, an empty cgroup v2 `cpuset.cpus.partition=isolated` partition whose
exclusive effective CPU and NUMA sets match the manifest, full SMT sibling
coverage, `nohz_full` on those CPUs, a fixed CPU frequency, no CPU
quota, no overlapping effective IRQ affinity, a housekeeping-only service
affinity, and `numactl`. Version 1 pins each benchmark process and all its
threads to **one declared logical CPU** inside the isolated partition and
binds memory to **one declared NUMA node**. This supports the single-thread
rho comparison; multiworker experiments need an extension that proves each
worker's thread affinity. Every run is invalidated by CPU
throttling, OOM, IRQ or softirq time, interrupt-count changes, steal time,
involuntary context switches, timeout, nonzero exit, or missing
`verified=1`/`online_ms`. Raw failures are retained.

`cpuset` and a container's visible CPU list alone cannot prove that other
tenants have no host-level contention. A RunPod Pod that lacks the Tier 0
host controls can use Tier 1 instead. [Linux's cgroup v2 documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
defines the isolated partition and exclusive CPUs. [Linux's CPU isolation
guide](https://docs.kernel.org/admin-guide/cpu-isolation.html) explains tick,
RCU, IRQ, and SMT considerations. The runner checks the effective state,
not just the requested configuration.

Frequency is established either by an exposed `cpufreq` policy with the
`performance` governor and equal minimum and maximum frequencies, or by the
specific AWS `g5g.metal` hardware whose [Graviton processor frequency is fixed](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/processor_state_control.html).
The latter path requires an ARM64 host, no `cpufreq` policy directory, and
an exact `g5g.metal` instance-type response from IMDSv2. The preflight receipt
records which path passed. A missing metadata response or a partially exposed
`cpufreq` policy fails the gate; other isolation and noise checks still apply.

The benchmark executable owns the `online_ms` interval. The manifest must
describe that timer's boundary; the runner cannot infer it from process
launch. The runner also records outer elapsed time, executable SHA-256,
host/kernel/CPU topology, cgroup state, raw stdout/stderr, per-CPU interrupt
and steal counters, cgroup throttle/OOM counters, and child involuntary
context switches. Tier 0 invalidates every noise event listed above. Tier 1
invalidates observed cgroup throttling or memory failures and retains the
other counters as noise evidence; its repeated-pair interval limits timing
claims when that noise affects results. Benchmark children receive a fixed minimal environment;
the provisioning API key is not passed into them. A controlled result still needs source review of the
executable's timer and correctness check.

## Tier 1 cloud instance

Use one RunPod Pod or comparable Linux instance for both variants. Keep the
allocation metadata returned by the provider in a local JSON receipt, with
its instance ID, image, advertised CPU and memory allocation, and creation
time. Do not put API tokens in it. Supply that receipt in `artifacts`; the
runner hashes it before and after the panel. The `allocation` section gives
the provider, instance ID, and absolute receipt path. An example Tier 1
manifest fragment is:

```json
{
  "schema": 1,
  "measurement_tier": "tier1_instance",
  "allocation": {
    "provider": "runpod",
    "instance_id": "POD_ID",
    "receipt": "/workspace/receipts/runpod-allocation.json"
  },
  "isolation": {"cpus": "4", "execution_cpu": 4},
  "artifacts": ["/workspace/receipts/runpod-allocation.json", "/workspace/src/solver.c"],
  "repetitions": 8
}
```

Fill in the remaining common manifest fields shown below. Choose an exposed
CPU from `probe-host`. The runner requires Linux, CPU affinity, per-CPU
statistics, and readable container CPU throttling and memory-failure
counters. It reads the current cgroup v2 hierarchy or the common cgroup v1
CPU and memory mounts; when counters are unavailable, preflight rejects the
measurement. Tier 1 does not require root, `numactl`, a fixed frequency,
`nohz_full`, host IRQ routing, or a manually created cgroup. Pinning affects
placement of the measured process, not other tenants. Keep unrelated jobs
off the instance during the panel and record any observable co-runners.

## Tier 0 provisioning checklist for the host administrator

1. Use a dedicated physical Linux host or a provider contract with equivalent
   host-level CPU and memory-node exclusivity. Reserve at least one separate
   housekeeping CPU. Record CPU thread siblings and NUMA node membership.
2. Configure kernel `nohz_full` for all benchmark CPUs and move IRQs to
   housekeeping CPUs. Enable cgroup v2 `cpuset`; create an isolated partition
   with `cpuset.cpus`, `cpuset.cpus.exclusive`, and `cpuset.mems` set to the
   chosen resources. Verify the corresponding `.effective` files and
   `cpuset.cpus.isolated` readback. Keep the service outside that partition.
3. Where `cpufreq` is available, set the selected CPUs' `performance` governor
   and equal minimum and maximum frequency. On `g5g.metal`, keep IMDSv2
   available so the runner can attest the fixed-frequency hardware. Remove
   CPU quotas from the benchmark cgroup and its
   ancestors. Install `numactl` and the same compiler/runtime used for both
   variants. These changes should be made by the host administrator because
   they affect all workloads on that machine.

The runner's `probe-host` command is read-only and can be run on any Linux
allocation before building binaries:

```sh
python3 scripts/isolated_bench.py probe-host
```

On a prepared host or instance, use `probe MANIFEST.json` to see the unmet
conditions for its declared tier. `run` refuses to launch a measurement when
that tier's preflight fails.

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
directory, or a direct run refuses to start. Keep the SQLite queue on a
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
exact 160-target panel from the
frozen scalar law with [make_j0_isolated_manifest.py](../scripts/make_j0_isolated_manifest.py):

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
replayed under a qualifying tier. Historical results elsewhere in the
repository need a tier audit before they are cited as measured speedups.

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
without a qualifying tier receipt remain exploratory until replayed under a
qualifying environment.
