# Cloud compute for agents

A cloud-agent VM has 4 CPUs, 15 GB and no GPU. This directory provides two
larger places to run work, and one runner shared by both:

| Need | Use | Billing |
| --- | --- | --- |
| An agent that *lives* on a big CPU or GPU box: long interactive work, CUDA development, warm build trees | a **Cursor worker on a Runpod pod** (`fleet.py`) | per hour while the pod runs; stops itself when idle |
| One heavy command from a small VM, run next to an agent's session | `fleet.py run rp-cpu-1 -- CMD` | the pod's hourly rate (already running) |
| Burst or fan-out: 1-100 containers, any core count, any GPU type, then back to zero | **Modal** (`modal_run.py`) | per second of container time |

Everything here is Python standard library plus the `modal` client, and needs
no local GPU or Docker.

## Credentials

Add these in **Cursor Dashboard -> Cloud Agents -> Secrets** so that every
cloud agent receives them as environment variables:

| Secret | For | Where to get it |
| --- | --- | --- |
| `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | `modal_run.py` | [modal.com/settings/tokens](https://modal.com/settings/tokens) |
| `RUNPOD_API_KEY` | `fleet.py` | [Runpod console -> Settings -> API keys](https://console.runpod.io/user/settings) |
| `CURSOR_API_KEY` | `fleet.py up`, `rekey`, `agent` | [cursor.com/dashboard -> API keys](https://cursor.com/dashboard) (a *user* key) |
| `RUNPOD_SSH_PRIVATE_KEY` | `fleet.py ssh`, `logs`, `run`, `jobs` | the private half of an SSH key registered in the Runpod console |
| `GITHUB_TOKEN` (optional) | lets agents on the pods push branches | a fine-grained token with contents and pull-request write on this repo |

Install the Modal client with `pip install modal`.

## Cursor workers on Runpod

[`fleet.json`](fleet.json) defines the pods:

| Worker | Hardware | $/hr | Stops after | Extras |
| --- | --- | --- | --- | --- |
| `rp-cpu-1` | 32 vCPU (compute-optimized), 64 GB | 1.12 | 240 idle minutes | SageMath 10.9, msolve 0.10.1 |
| `rp-gpu-1` | 1x RTX PRO 4500 Blackwell (sm_120, 32 GB), 8 vCPU, 62 GB | 0.72 | 60 idle minutes | CUDA 12.8 and the CUDA 13.3 compiler at `$CUDA13_HOME` |

Both pods also have gcc 13, cmake, Rust stable, Go, clang-tidy, cppcheck,
valgrind, iverilog, verilator, yosys, and a Python venv with pycryptosat,
python-sat, numpy, sympy and modal.

Each pod runs a Cursor self-hosted ("My Machines") worker named after the pod,
with this repository checked out at `/workspace/cryptanalysis`. To put an agent
on one:

- **cursor.com/agents**: pick the machine (for example `rp-gpu-1`) in the
  environment dropdown.
- **Slack or GitHub**: `@Cursor worker=rp-cpu-1 <task>`.
- **From another agent or a script**:
  `cloud/fleet.py agent rp-cpu-1 "run the pdp-scaling m=5 grid and commit the CSVs" --wait`.

A worker belongs to the Cursor user whose `CURSOR_API_KEY` registered it, and
only that user's agents can target it. To move the workers to another
account, set that account's key and run `cloud/fleet.py rekey rp-cpu-1 rp-gpu-1`.

Agents on the pods push with `GITHUB_TOKEN` when it was set at `up` or `rekey`
time. Without it they can commit, but they cannot push.

### Lifecycle

```sh
cloud/fleet.py status                  # pods, $/hr, Cursor connection, balance and runway
cloud/fleet.py up rp-gpu-1 --wait      # create or start, and wait until the worker connects
cloud/fleet.py stop rp-gpu-1           # stop billing compute
cloud/fleet.py down rp-gpu-1 --yes     # terminate (the volume is deleted)
cloud/fleet.py logs rp-gpu-1 --file worker   # or boot, toolchain, idle; --state for status files
cloud/fleet.py ssh rp-gpu-1 -- nvidia-smi
cloud/fleet.py up --update rp-cpu-1    # re-apply fleet.json and cloud/ changes (resets the pod)
cloud/fleet.py up --recreate rp-gpu-1  # a stopped pod whose machine has no free GPU: rent a new one
```

On every container start, the pod fetches `cloud/` from GitHub (the
`fleetRef` branch in `fleet.json`, else `fallbackRef`) and runs
[`worker/boot.sh`](worker/boot.sh). The boot script:

1. installs the Cursor CLI;
2. starts `agent worker` in a restart loop (tmux session `cursor-worker`);
3. starts the idle watchdog;
4. installs the rest of the toolchain in the background
   (`/workspace/fleet/toolchain.json` records what is installed).

The worker connects within about a minute of the pod starting. The full
toolchain needs a few more minutes.

The idle watchdog ([`worker/idle.py`](worker/idle.py)) stops a pod after
`idleStopMinutes` with no CPU or GPU load, no SSH session, no running `run`
job, no recent edits in the checkout, and no Cursor agent in use. Start it
again with `up`.

The GPU pod keeps `/workspace` on a volume across stops. Runpod CPU pods have
no volume, so stopping `rp-cpu-1` resets its disk and the next boot rebuilds
the toolchain. For that reason its watchdog never stops the pod while the
checkout has uncommitted or unpushed work.

Layout on a pod:

| Path | Contents |
| --- | --- |
| `/workspace/cryptanalysis` | the checkout agents work in |
| `/workspace/fleet/{logs,secrets,src}` | fleet logs, credentials (mode 600), and the `cloud/` source it booted from |
| `/workspace/fleet/{machine,toolchain,idle}.json` | hardware, installed tools, watchdog state |
| `/workspace/venv`, `/workspace/opt/{msolve,sage,cuda-13.3}`, `/workspace/home` | tools (`/root/.cargo` and the like link into `/workspace/home`) |
| `/workspace/jobs/<id>` | `fleet.py run` jobs |

### Running one command on a pod

```sh
cloud/fleet.py run rp-cpu-1 --out build-test.log -- 'cmake -B build -G Ninja && cmake --build build && ctest --test-dir build -j32 > build-test.log'
cloud/fleet.py run rp-cpu-1 --dir pdp --changed -- 'cd experiments/pdp-scaling && python3 run.py --engine sat --m 3 --ns 17,31 --ls 3,4,5 --seeds 2 --threads 32 --out results/sat_m3.csv'
cloud/fleet.py run rp-gpu-1 --detach -- 'make -C ecc2k130 gpu NVCC=$CUDA13_HOME/bin/nvcc && make -C ecc2k130 bench'
cloud/fleet.py jobs rp-gpu-1
cloud/fleet.py job rp-gpu-1 <job-id> --logs     # --fetch copies results back, --kill stops it
```

`run` ships the working tree, including uncommitted edits and untracked files
that are not ignored, and runs the command in a fresh copy of it. With
`--dir NAME` it runs in `/workspace/scratch/NAME` instead, which persists
between jobs so builds stay warm. When the command finishes, `run` copies back
the paths named by `--out`, plus every file it wrote when `--changed` is set.

## Modal jobs

```sh
# 32 cores for the C library's tests; the log comes back with the exit code
cloud/modal_run.py run --cpu 32 --memory 64 -- 'cmake -B build -G Ninja && cmake --build build && ctest --test-dir build -j32'

# a sharded sweep: 16 containers, each told SHARD_INDEX/SHARD_COUNT
cloud/modal_run.py run --image sage --shards 16 --cpu 4 --timeout 7200 --changed \
  -- 'cd experiments/volcano-ic && sage run.sage census $SHARD_INDEX $SHARD_COUNT'

# a GPU: an L4 by default with --image cuda; H100, B200, RTX-PRO-6000 and others by name
cloud/modal_run.py run --image cuda --gpu RTX-PRO-6000 --out ecc2k130/build/bench.txt \
  -- 'make -C ecc2k130 gpu NVCC=$CUDA13_HOME/bin/nvcc && make -C ecc2k130 bench > ecc2k130/build/bench.txt'

# long jobs: detach, then check back
cloud/modal_run.py run --detach --timeout 43200 --cpu 64 --memory 128 -- 'python3 long.py'
cloud/modal_run.py status <job>; cloud/modal_run.py logs <job> -f; cloud/modal_run.py fetch <job>
cloud/modal_run.py list; cloud/modal_run.py kill <job>; cloud/modal_run.py gc --days 14
```

Images are built on first use (a few minutes) and cached afterwards:

- `cpu`: Ubuntu 24.04 with the pod toolchain, minus Sage.
- `cuda`: the same on `nvidia/cuda:12.8.1-devel`, plus CUDA 13.3.
- `sage`: SageMath 10.9.

`--apt` and `--pip` add packages, `--env KEY=VALUE` sets variables, and
`--secret NAME` attaches a Modal secret. A job's source, logs and results stay
in the `cryptanalysis-remote-jobs` volume until `gc` removes them. Sandboxes run
in the Modal app `cryptanalysis-remote`, apart from the ECC2K-130 apps.

## Recording runs

Every job shard writes a `status.json` with its exit code, wall time, host,
CPU count and GPU names (`modal_run.py status`, `fleet.py job`). Copy the
hardware into the run record that [AGENTS.md](../AGENTS.md) asks for.
Inside a Modal sandbox, `/proc` shows the host's memory, so quote the
`--memory` you requested instead. On pods, `FLEET_CPUS`, `FLEET_MEM_GB` and
`FLEET_GPU` hold the pod's own allocation.

## Tests

```sh
python3 -m unittest discover -s cloud/tests -v
shellcheck -x cloud/job_runner.sh cloud/worker/*.sh
```

The tests talk to no service. They run `job_runner.sh` locally and check the
pod request `fleet.py` would send.
