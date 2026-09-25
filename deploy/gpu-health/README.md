# gpu-health: a one-to-two-minute GPU check built on the ECC2K-130 rho walk

A container that loads every GPU it can see with the ECC2K-130 Pollard rho
walk from [`ecc2k130/`](../../ecc2k130/README.md) for 60-120 seconds. It
checks every result the GPUs produce and returns one verdict. It is built to
run as a Kubernetes init container, or as a gate on new GPU nodes, so work
lands only on GPUs that have just computed correctly at their expected speed.

```sh
docker build -f deploy/gpu-health/Dockerfile -t gpu-health .     # from the repository root
docker run --rm --gpus all gpu-health                             # 60 s on every GPU
docker run --rm --gpus all -e GPU_HEALTH_SECONDS=120 gpu-health   # a longer soak
```

Exit status 0 means every GPU passed. 1 means at least one failed, and the
reason is in the last log line and the termination message. 2 means the check
could not run as configured.

## Is this a good way to check a GPU's health?

**It is a good check of one thing: can this GPU's SMs compute correctly at
their expected speed under sustained load?** It is not a complete health
check, and it does not max out every part.

What it is good at:

- **Silent data corruption.** Every point the walk reports is checked on the
  host, and the checks are cheap enough to cover every report. The core check
  is that the point lies on the curve. A flipped bit anywhere in a walk's
  state (a register, shared memory, L2, an ALU or multiplier result) puts the
  point off the curve with probability 1 - 2^-131. The addition law never
  brings it back, so one test at the end checks every step of the trail
  behind it. A lane reports every 2^14.86 steps, every few seconds, so most
  of the work in a run is covered; `checkedFraction` in the report gives the
  measured share. A sample of reports is also re-walked from its seed on the
  golden model in [`fpga/model`](../../fpga/model), which shares no code with
  the GPU kernel. That catches faults that keep a point on the curve, such as
  a wrong branch. Most burn-in tools compare runs against each other or skip
  the check entirely; this one checks against an independent reference.
- **A throughput number you can trust.** The walk is deterministic and
  compute-bound, and its rate barely moves between runs (measurements below).
  A GPU a few percent slower than its peers or its model's baseline is
  therefore really slower. The usual causes are clocks held down by heat or
  power, a lowered power limit, locked clocks, fewer SMs than expected, or
  another process on the GPU.
- **Hardware protection events.** nvidia-smi is sampled during the load.
  Hardware slowdown, hardware thermal slowdown or a power-brake event fails
  the GPU. Thermal throttling warns.
- **The failures that happen before any math.** A missing GPU
  (`GPU_HEALTH_EXPECT_GPUS`), a driver too old for CUDA 13.3, a GPU that
  faults (a CUDA error, usually with an Xid in the host's log), a GPU that
  hangs (killed after `--seconds` plus two minutes), uncorrectable ECC errors,
  and pending or failed row remapping.

What it does not check:

- **Tensor cores, and the FP32/FP64/FP16 pipes.** The walk is pure integer
  and carry-less-multiply work. Tensor cores are where ML workloads spend
  most of their time and most of a datacenter GPU's power, and a fault there
  goes unseen.
- **Memory.** The walk state is a few hundred MB and mostly served from L2
  (the client asks for a persisting-L2 window). HBM bandwidth, and nearly all
  of its capacity, go untested.
- **Interconnect.** NVLink, NVSwitch, PCIe bandwidth and the network are
  unused. Only small report transfers cross PCIe.
- **Heat soak.** 60-120 s catches a GPU that cannot hold its clock at all. It
  misses one that fails after ten minutes; in the tree's measurements an RTX
  PRO 6000 took an hour of sweeping to go from 47 to 79 °C.
- **Pre-Ampere GPUs.** The walk's products are `clmad` carry-less multiplies,
  which exist from sm_80. T4 and V100 are reported as unsupported.

So use it as the fast gate, and run tests that cover the rest beside it:
NVIDIA's DCGM diagnostics (`dcgmi diag`) for memory, PCIe/NVLink bandwidth
and targeted power, and NCCL's `all_reduce_perf` on multi-GPU nodes. For a
full-power burn-in on a datacenter part, use a tensor-core GEMM load; on the
one datacenter part measured (a B200), this walk drew about half the board's
power limit.

## Does it max out the GPU?

It saturates one integer pipe on every SM, and nothing else. Which pipe
depends on the chip, and whether that reaches the power limit depends on the
part:

| part (power limit) | measured under this walk | what binds | source (github.com/aburan28/crypto, `ecc2k130/`) |
|---|---|---|---|
| RTX PRO 6000 Blackwell Server (600 W) | 567 W, 2422 MHz held (sigma walk, 14.47 B/s); 562-596 W across the kernel's builds | the carry-less multiply unit | POWER-BOUND.md §3, TWO-CHAINS.md, this repo's `ecc2k130/README.md` |
| RTX PRO 4500 Blackwell (165 W) | pinned at 165 W, 1.92-1.97 GHz (sigma walk, 5.107 B/s) | power | RTX-PRO4500.md |
| B200 (1000 W) | **420-524 W**, 1965 MHz held (table-walk builds of the same kernel) | the integer logic pipe at 86-100%; the carry-less unit idle 91-96% of the time | TWO-CHAINS.md §6.2 |
| L4 (72 W) | no power log. Per-SM rate is 42.9 M/s against 62.2 on the same-architecture L40S, which the note puts down to the 72 W limit | power (inferred) | ADA-L4-L40S.md |
| H100, H200, A100, L40S | rates only; power not measured in this tree | on an H100, likely the logic pipe as on the B200: a `clmad` costs 2 logic slots there, against 38 on the 6000 | benchmarks/modal-gpus/SURVEY.md, TWO-CHAINS.md §6 |

Where the power limit is modest relative to the SMs (RTX PRO 4500, L4, and
nearly the RTX PRO 6000), the walk drives the card to its power limit, so it
is also a power and thermal test. On a B200 it draws about half the board's
power limit, a budget sized for tensor-core and HBM traffic that this walk
leaves idle. A check whose job is to prove that cooling and power delivery
hold at full board power on those parts needs a tensor-core load.

The report tells you where your own fleet falls: each GPU's mean and maximum
power against its enforced limit, its SM clock against its maximum, and its
peak temperature.

## Can throughput tell you the GPU is ready?

Yes, if it is compared against the right thing. On builds of this kernel,
the rate is stable enough to act on:

- one RTX PRO 6000, 5 × 64 launches: 20.077-20.080 B/s (this repo's
  `ecc2k130/README.md`);
- one RTX PRO 6000 over five repetitions while it warmed from 47 to 79 °C:
  19.93-19.99 B/s at a constant 2422 MHz (AUTOSWEEP.md §4);
- the same build on two RTX PRO 6000s in two sessions: 20.095 and
  20.045 B/s, 0.25% apart, while their power draws differed by 3.4%
  (POWER-BOUND.md §3-4);
- one B200: two passes of 21 builds agreed to 0.05% on every build
  (AUTOSWEEP.md §3.1);
- one RTX PRO 4500, held at its 165 W limit, sigma walk: 5.069-5.151 B/s over
  three repetitions, a 1.6% spread (RTX-PRO4500.md).

The first four are table-walk builds, on cards whose clocks never moved. The
last shows what a power limit does: at a fixed power, the clock follows each
chip's leakage and temperature, so power-limited parts spread more. And two
cards are not a fleet. So the check compares each GPU three ways, and never
against a number from another model or build:

| comparison | fails below | warns below | needs |
|---|---|---|---|
| steady rate / this model's calibrated baseline | 0.90 | 0.95 | a baseline for this GPU name, SM count and build |
| steady rate / median of the node's other GPUs of the same model | 0.90 | 0.95 | two or more of the same GPU in the node |
| last rate window / first, after a warm-up | 0.85 | 0.95 | nothing |

Thresholds can be overridden with `--threshold baseline_fail=0.93` and the
like, and `--strict` turns warnings into failures. Set them from your own
fleet's distribution once you have one.

For scale, a survey of the source tree's packed build of this walk
(`ecc2k130 --packed --bench`: automatic workers, CUDA 13.3.1, Modal, 2026-09;
[SURVEY.md](https://github.com/aburan28/crypto/blob/main/ecc2k130/benchmarks/modal-gpus/SURVEY.md))
measured these rates in billions of iterations per second:

| GPU | B/s | GPU | B/s |
|---|---:|---|---:|
| RTX PRO 6000 | 14.47 | B300 (148 SMs) | 7.57 |
| B200 | 8.84 | H100 80GB HBM3 | 7.54 |
| L40S | 8.70 | A100 (40 or 80 GB) | 4.62-4.63 |
| H200 | 7.63 | L4 | 2.56 |
| A10 | 2.42 | T4 (no `clmad`, other build) | 0.54 |

They show how the rate scales with the part. **They are not baselines for
this check.** `ec2k-gpu health` is a different binary running a different
mode (it reports and checks points, revives lanes and syncs with the host
every launch). Its rate on each model has to be measured with the image you
deploy. That is why [`baselines.json`](baselines.json) ships empty.

## What the check does

### The load: `ec2k-gpu health`

The client's `health` command ([`src/ec2k_gpu.cu`](../../ecc2k130/src/ec2k_gpu.cu),
checks in [`src/healthcheck.h`](../../ecc2k130/src/healthcheck.h)) walks the
campaign's sigma walk, `R' = R + σ^j(R)`, from Certicom's challenge points.
It uses distinguished-point weight 42, so a lane reports every 2^14.86
steps, and 4096-step launches over one wave of resident threads (1,540,096
lanes on an RTX PRO 6000). It runs for `--seconds` (60 by default). While
the GPU runs each launch, the host checks every report of the previous one:

| check | catches |
|---|---|
| seed: run id 65535, a lane index the launch has | a corrupted or invented report |
| sequence: the lane's restart counter is exactly one more than at its last report | a lost, repeated or foreign report |
| iterations: the lane's start step plus its count lands inside the reporting launch | corrupted bookkeeping |
| weight: HW(x) ≤ 42 | a wrong distinguished-point test |
| on the curve: y² + xy = x³ + 1 | any corruption of a point's coordinates, anywhere in its trail (0.3 µs per report) |
| re-walk, on the golden model and on background threads, of the longest report of each launch up to 512 steps | faults that keep the point on the curve: a wrong branch, a wrong start point |

The first 10 s are left out of the steady rate as warm-up. The rest is cut
into 10 s windows, which is where a card that slows under load shows. Nothing
is written to disk.
`ec2k-gpu health` runs on its own too and prints one JSON object. It exits 0
if every check passed, 1 if a report failed one (`faults` in the output says
which), 4 if the run was too short to prove anything, and 3 on a CUDA error.

### The verdict: `gpu-health`

[`gpu_health.py`](gpu_health.py) (Python 3.8+, standard library) is the
image's entry point. In order, it:

1. runs `ec2k-gpu check`, the host's own arithmetic against the golden
   model (0.2 s), because the checks run on the host;
2. lists the CUDA devices, and fails if there are none or not
   `GPU_HEALTH_EXPECT_GPUS` of them;
3. records nvidia-smi's view of each GPU: ECC counters, row remapping, power
   limit, maximum clocks, PCIe link and any other compute processes;
4. runs `ec2k-gpu health` on every GPU at once, one process each, sampling
   nvidia-smi every 2 s (temperature, power, clocks, utilisation, clock event
   reasons, PCIe link, ECC);
5. reads nvidia-smi again, and gives each GPU a verdict:

| fails the GPU | warns |
|---|---|
| any report failing a check, or a failed re-walk | thermal throttling (sw_thermal_slowdown) |
| the load died (CUDA error) or hung | rate 85-95% of the first window by the last |
| a run too short to check anything | rate 90-95% of baseline or of peers |
| rate < 90% of the model's baseline, or of the node's other GPUs of that model | correctable ECC errors during the load |
| rate < 85% of the first window by the last | PCIe link narrower than the GPU's |
| hw_slowdown, hw_thermal_slowdown or hw_power_brake_slowdown during the load | mean GPU utilisation under 90% |
| an uncorrectable ECC error since the driver loaded, or during the load | another process on the GPU before the load |
| a pending row remap or page retirement, or a failed row remap | MIG enabled |
| compute capability below 8.0 | a baseline measured with another build (the comparison becomes advisory) |

sw_power_cap is only noted: it is how a power-limited part normally runs.

## Running it in Kubernetes

The image needs the NVIDIA container runtime. It sets
`NVIDIA_DRIVER_CAPABILITIES=compute,utility`: `utility` is what puts
nvidia-smi in the container, and without it the telemetry checks are
skipped. It wants about a CPU per GPU, because the host checks every report.
The example manifests set no CPU limit, so it can use cores the node has
idle. They keep its requests small, because an init container's requests
count toward its pod's for as long as the pod exists.

**As an init container** ([k8s/init-container.yaml](k8s/init-container.yaml)).
The init container requests the same `nvidia.com/gpu` count as the workload.
The kubelet hands an init container's devices on to the pod's containers, so
it checks exactly the GPUs the workload gets. If a GPU fails, the workload
does not start, and the reason is in the pod's
`.status.initContainerStatuses[0].state.terminated.message` (`lastState`
once the kubelet has restarted the container). The limit is that the pod
stays on that node and retries there.

**As a gate on new nodes** ([k8s/node-gate.yaml](k8s/node-gate.yaml)), for
"check GPUs when they are provisioned". Register GPU nodes with the taint
`gpu-health/pending=true:NoSchedule`. A DaemonSet that tolerates the taint
runs the check (120 s here) as its init container, with `--node-gate`. On a
pass it labels the node `gpu-health/verdict=pass` and lifts the taint; on a
failure it labels it `fail`, keeps the taint, and exits 1. The kubelet then
retries with backoff, so a node that recovers is released later. The verdict
line is also written to an annotation on the node. The DaemonSet sees the
GPUs through `NVIDIA_VISIBLE_DEVICES=all` rather than a `nvidia.com/gpu`
request, as the NVIDIA GPU Operator's own validator does. Otherwise its
long-lived pod would hold every GPU on the node. A node that has already been
released is never loaded again, so a rollout does not disturb running work.
To re-check a node, drain it, taint it and delete its gpu-health pod.

| setting (flag / environment) | default | |
|---|---|---|
| `--seconds` / `GPU_HEALTH_SECONDS` | 60 | load per GPU; the run takes 10-30 s more |
| `--expect-gpus` / `GPU_HEALTH_EXPECT_GPUS` | 0 (any) | fail unless exactly this many GPUs are visible |
| `--baselines` / `GPU_HEALTH_BASELINES` | `/etc/gpu-health/baselines.json` in the image | per-model rates; mount your own |
| `--threshold NAME=VALUE` | see above | `baseline_fail`, `baseline_warn`, `peer_fail`, `peer_warn`, `trend_fail`, `trend_warn`, `utilization_warn` |
| `--strict` / `GPU_HEALTH_STRICT=1` | off | warnings fail |
| `--calibrate` / `GPU_HEALTH_CALIBRATE=1` | off | print baseline entries instead of rating throughput |
| `--node-gate` / `GPU_HEALTH_NODE_GATE=1` | off | label NODE_NAME and lift `--gate-taint` on a pass |
| `--gate-taint`, `--gate-label` | `gpu-health/pending`, `gpu-health/verdict` | |
| `--rewalk-threads` / `GPU_HEALTH_REWALK_THREADS` | from the CPUs, 1-4 per GPU | golden-model re-walk threads per GPU |
| `--kat` / `GPU_HEALTH_KAT` | off | also replay the campaign's 48 known answers (13 s of a core; the image build already ran them) |
| `--json-out` / `GPU_HEALTH_JSON_OUT` | | also write the report, indented, to a file |
| `--termination-log` | `/dev/termination-log` | the one-line verdict |

The JSON report on stdout contains, per GPU: the device (name, UUID, PCI
bus id, SMs, compute capability); the workload's own result (rates, windows,
checks, faults, re-walks); the throughput comparisons; the summarised
telemetry; nvidia-smi's rows from before and after the load; and the
failures, warnings and notes.

## Calibrating baselines

Run the check on a few nodes you trust, with the image you will deploy:

```sh
docker run --rm --gpus all -e GPU_HEALTH_CALIBRATE=1 -e GPU_HEALTH_SECONDS=120 gpu-health \
    | tail -1 | jq .calibration
```

Each GPU model seen gets an entry: the median steady rate over its GPUs,
their minimum and maximum, the power limit, the driver, and the binary's
SHA-256. Merge the entries into a baselines file, from several nodes and
not just one, and mount it with `GPU_HEALTH_BASELINES` (a ConfigMap in
Kubernetes). A baseline is matched on the GPU name and SM count. If its
`binarySha256` is not the running binary's, the comparison only warns: a new
build can move the rate, so recalibrate when you change the image. A GPU
whose power limit was lowered on purpose needs its own entry, or it will fail
as slow.

## What has been validated, and what has not

- **Validated here, without a GPU:** the kernel builds for sm_80 to sm_120
  with CUDA 13.3 (90-104 registers, no spills), inside the image as in CI.
  The host test holds the health checks to a model of the device's launch
  loop on the golden model: every report of a correct run passes, and each
  kind of corruption fails the check that is meant to catch it
  (`ecc2k130/src/hosttest.cpp`). The orchestrator's 42 tests run it against
  scripted stand-ins for `ec2k-gpu` and nvidia-smi: healthy nodes, silent
  corruption, crashes, hangs, missing GPUs, slow GPUs against baselines,
  peers and their own first window, hardware slowdown, ECC errors, row
  remapping, calibration and the node gate
  (`python3 -m unittest discover -s deploy/gpu-health/tests`). The image is
  built and smoke-run by `.github/workflows/gpu-health.yml`.
- **Not yet done:** a run of `ec2k-gpu health` on a card. The walk kernel is
  the one measured throughout this tree, but the health command's launch
  loop, its rates and its coverage on real GPUs are unmeasured. The first run
  on each model is also its calibration:

  ```sh
  docker run --rm --gpus all -e GPU_HEALTH_CALIBRATE=1 gpu-health
  # or the bare command, from this repository with Modal credentials:
  cloud/modal_run.py run --image cuda --gpu L40S -- 'make -C ecc2k130 gpu \
      NVCC=$CUDA13_HOME/bin/nvcc ARCH="-gencode arch=compute_89,code=sm_89" \
      && ecc2k130/build/ec2k-gpu health --seconds 60'
  ```

## Files

| file | |
|---|---|
| [`Dockerfile`](Dockerfile) | two stages: build and self-check `ec2k-gpu`, then a Debian slim runtime with Python, non-root |
| [`gpu_health.py`](gpu_health.py) | the orchestrator and entry point |
| [`baselines.json`](baselines.json) | per-model rates; empty until calibrated |
| [`k8s/init-container.yaml`](k8s/init-container.yaml) | a pod whose workload waits for its GPUs to pass |
| [`k8s/node-gate.yaml`](k8s/node-gate.yaml) | a DaemonSet that releases new GPU nodes after they pass |
| [`tests/`](tests/) | the orchestrator's tests and the stand-ins they drive |
