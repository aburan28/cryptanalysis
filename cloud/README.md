# Cloud compute for agents

A cloud-agent VM has 4 CPUs, 15 GB and no GPU. This directory provides larger
places to run work:

| Need | Use | Billing |
| --- | --- | --- |
| An agent that *lives* on a big CPU or GPU box: long interactive work, CUDA development, warm build trees | a **Cursor worker on a Runpod pod** (`fleet.py`) | per hour while the pod runs; stops itself when idle |
| The same, when Runpod is out of credit or more machines are needed at once | a **Cursor worker on Modal** (`modal_worker.py`) | per second at Modal's function rates; stops itself when idle |
| One heavy command from a small VM, run next to an agent's session | `fleet.py run rp-cpu-1 -- CMD` | the pod's hourly rate (already running) |
| One index-calculus run or benchmark on a GPU of a chosen type | `runpod_pod.py run NAME -- CMD`: a pod rented for the command and deleted after it | the pod's hourly rate while it exists |
| A queue of GPU jobs, run one at a time on a runner, each to a receipt | **cairn's host agent on a Runpod pod** (`cairn_queue.py`) | the pod's hourly rate; stops itself when idle |
| Burst or fan-out: 1-100 containers, any core count, any GPU type, then back to zero | **Modal** (`modal_run.py`) | per second of sandbox time (3x the function rate) |

Everything here is Python standard library plus the `modal` client, and needs
no local GPU or Docker.

## Credentials

Add these in **Cursor Dashboard -> Cloud Agents -> Secrets** so that every
cloud agent receives them as environment variables:

| Secret | For | Where to get it |
| --- | --- | --- |
| `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | `modal_run.py`, `modal_worker.py` | [modal.com/settings/tokens](https://modal.com/settings/tokens) |
| `RUNPOD_API_KEY` | `fleet.py`, `runpod_pod.py`, `cairn_queue.py` | [Runpod console -> Settings -> API keys](https://console.runpod.io/user/settings) |
| `CURSOR_API_KEY` (optional) | `fleet.py up`, `rekey`, `agent`; without it workers wait for a sign-in link | [cursor.com/dashboard -> API keys](https://cursor.com/dashboard) (a *user* key) |
| `RUNPOD_SSH_PRIVATE_KEY` | `fleet.py ssh`, `logs`, `run`, `jobs`; optional for `runpod_pod.py` and `cairn_queue.py`, which otherwise use a key of their own and reach only pods made from the same machine | the private half of an SSH key registered in the Runpod console |
| `GITHUB_TOKEN` (optional) | lets agents on the pods push branches | a fine-grained token with contents and pull-request write on this repo |

Install the Modal client with `pip install modal`.

## Cursor workers on Runpod

[`fleet.json`](fleet.json) defines the pods:

| Worker | Hardware | $/hr | Stops after | Extras |
| --- | --- | --- | --- | --- |
| `rp-cpu-1` | 32 vCPU (compute-optimized), 64 GB | 1.12 | 240 idle minutes | SageMath 10.9, msolve 0.10.1 |
| `rp-gpu-1` | 1x RTX PRO 4500 Blackwell (sm_120, 32 GB), 8 vCPU, 62 GB | 0.72 | 60 idle minutes | CUDA 13 hosts only (`allowedCudaVersions: ["13.0"]`); CUDA 13.3 compiler at `$CUDA13_HOME` |

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

A worker belongs to the Cursor user who signed it in, and only that user's
agents can target it. `fleet.py up` with `CURSOR_API_KEY` set signs in with
that key. Without it, the worker runs `agent login` and waits;
`cloud/fleet.py login NAME` prints the link, and whoever opens it owns the
worker. To move a keyed worker to another account, either run
`cloud/fleet.py login --switch NAME` and open the link as that account, or set
that account's key and run `cloud/fleet.py rekey NAME`.

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
| `/workspace/jobs/<id>` | `fleet.py run` logs, status and outputs |
| `/scratch` (`$FLEET_SCRATCH`) | local disk for job trees and builds; a stop wipes it |

### Running one command on a pod

```sh
cloud/fleet.py run rp-cpu-1 --out build-test.log -- 'cmake -B build -G Ninja && cmake --build build && ctest --test-dir build -j32 > build-test.log'
cloud/fleet.py run rp-cpu-1 --dir pdp --changed -- 'cd experiments/pdp-scaling && python3 run.py --engine sat --m 3 --ns 17,31 --ls 3,4,5 --seeds 2 --threads 32 --out results/sat_m3.csv'
cloud/fleet.py run rp-gpu-1 --detach -- 'make -C ecc2k130 gpu NVCC=$CUDA13_HOME/bin/nvcc && make -C ecc2k130 bench'
cloud/fleet.py jobs rp-gpu-1
cloud/fleet.py job rp-gpu-1 <job-id> --logs     # --fetch copies results back, --kill stops it
```

`run` ships the working tree, including uncommitted edits and untracked files
that are not ignored, and runs the command in a fresh copy of it under
`/scratch`, on the pod's local disk. With `--dir NAME` it runs in
`/scratch/NAME` instead, which is kept between jobs so builds stay warm until
the pod stops. When the command finishes, `run` copies back the paths named by
`--out`, plus every file it wrote when `--changed` is set.

Measured on these pods:

- On `rp-cpu-1`, configuring, building and running the C library's 15 tests
  took 5.5 s; the whole `run` took 18 s.
- On `rp-gpu-1`, building the ECC2K-130 client with CUDA 13.3 and running
  `bench` gave 6.48 G iterations/s.

On `rp-gpu-1`, `nproc` reports the host's 64 cores; the pod's share is
`$FLEET_CPUS` (8), so use `make -j$FLEET_CPUS`. Its `/workspace` is a network
filesystem: unpacking there is about 40x slower and building about 2x slower
than on `$FLEET_SCRATCH`, so build out of tree there
(`cmake -B $FLEET_SCRATCH/build`).

## A Runpod GPU pod for one command

[`runpod_pod.py`](runpod_pod.py) rents a pod, runs one command on this
checkout there, and gives the pod back. It is the default way to put an
index-calculus run on a GPU ([AGENTS.md](../AGENTS.md#run-index-calculus-on-a-gpu)):

```sh
cloud/runpod_pod.py run ic-gpu --out results/run.json -- \
  'mkdir -p results && cd suite && cargo run --release --bin ca-ic -- run --degree 23 --curve-a 1 --out ../results/run.json'
cloud/runpod_pod.py run f4 --gpu "NVIDIA GeForce RTX 5090" --keep -- 'nvidia-smi'
cloud/runpod_pod.py ssh f4 -- 'nvidia-smi'      # or sync, fetch NAME REMOTE LOCAL_DIR
cloud/runpod_pod.py list
cloud/runpod_pod.py down f4
```

`run NAME` creates the pod unless one of that name exists and makes
`/root/cryptanalysis` this checkout, uncommitted edits included. It then
installs Rust and NVRTC when they are missing
([`pod_env.sh`](pod_env.sh)) and runs the command there with `CA_NVRTC_LIB`
set. Afterwards it copies each `--out` path back into the checkout and deletes
the pod it created, unless `--keep`. Its exit status is the command's.

**Getting the checkout there.** This VM uploads to a pod at about 0.8 MB/s, so
the 288 MB checkout would take six minutes. Instead:
- [`ship.py`](ship.py) has the pod fetch the newest commit of the checkout that
  GitHub has (HEAD's merge base with its upstream), and sends only the changed
  and untracked files. The pod checks the result against this checkout's file
  names and sizes.
- Every pod starts that fetch when its container starts, while it is still
  coming up, and keeps a ref, so a later fetch takes about a second.
- A checkout without an upstream on GitHub is sent whole.
- [`install_tree.py`](install_tree.py) then rewrites only the files whose
  content differs and removes the rest, keeping `suite/target`. Cargo
  therefore rebuilds only what changed.

Without `--gpu`, a pod takes the first type in stock from the RTX 5090, RTX
4090, RTX PRO 6000 and H100, with at least `--min-vcpu` (16) vCPUs and
`--min-ram` (32) GB per GPU; `--cpu N` asks for a CPU pod instead. The pod
receives the public half of the SSH key `fleet.py` uses
(`RUNPOD_SSH_PRIVATE_KEY` or `RUNPOD_SSH_KEY`) when one is set, or else of
this machine's `~/.ssh/id_ed25519` (created if missing), beside the account's
registered keys. So `RUNPOD_API_KEY` is the only secret it needs, and with the
fleet key a pod made in one session is reachable from the next. The image is
`runpod/base` (`--image` names another). Every pod stops itself after
`--max-hours` (6), in case nobody deletes it. Creating a pod prints its rate.

## A cairn job queue on Runpod GPU runners

[`cairn_queue.py`](cairn_queue.py) queues commands on *runners*: Runpod GPU
pods running [cairn](https://github.com/aburan28/cairn)'s host agent, which
runs the jobs in its spool one at a time. Use it for a series of GPU jobs
that should wait their turn on one machine, with a receipt for each:

```sh
Q=cloud/cairn_queue.py
$Q up gpu-1                                    # a runner: a GPU pod as runpod_pod.py rents one
$Q submit gpu-1 --out results/a.json -- \
  'mkdir -p results && cd suite && cargo run --release --bin ca-ic -- run --degree 23 --curve-a 1 --out ../results/a.json'
$Q submit gpu-1 --only suite --out results/b.json -- '...'   # a tree of suite/ alone
$Q jobs gpu-1                                  # queued, running, done, with receipts
$Q wait gpu-1 JOB...                           # exit 0 all succeeded, 1 one failed, 3 one could not run
$Q fetch gpu-1 JOB... [--into DIR]             # outputs into the checkout; records under .cairn-jobs/
$Q hosts gpu-1                                 # what registered with the runner's node
$Q logs gpu-1 [agent|node|boot|prefetch]
$Q list
$Q down gpu-1                                  # refuses while jobs are queued, running or unfetched
```

How a runner works:

- **Boot.** [`cairn_runner.sh`](cairn_runner.sh) runs at every container start
  and installs a pinned cairn release, checked against its sha256. It then
  runs `cairn agent run --sandbox none --parallel 1`. The agent registers the
  machine with a cairn node every minute: a private node on the pod's
  loopback, unless `up --node URL` names others (the HTTP side is plaintext;
  see cairn's `docs/fleet.md`).
- **Submit.** `submit` puts this checkout on the runner as a tree, once per
  distinct tree, as `runpod_pod.py` does. It then queues a cairn job spec
  with `cairn agent submit`. The spec's command installs the tree into the
  runner's checkout, sources `pod_env.sh`, and runs your command under
  [`job_runner.sh`](job_runner.sh). Each job gets a timeout (`--timeout`,
  default 4 hours) and an id (`--id`, default a timestamp); cairn runs an id
  only once.
- **Fetch.** `fetch` merges each job's `--out` paths into the checkout. It
  keeps the receipt, spec, stdout, stderr, `log.txt` and `status.json` under
  the ignored `.cairn-jobs/RUNNER/JOB`; copy what a run record needs into its
  experiment directory.
- **Idle stop.** A runner stops itself after `--idle-minutes` (60) with
  nothing queued, running or unfetched and nobody logged in, and after
  `--max-hours` (24) regardless. A stopped pod loses its disk; `up` starts it
  again.
- **Leases.** `--objective ID --task T` makes the agent lease the task on the
  node while the job runs; the node must hold that objective.

**Limitations.**

- **Jobs declare no GPU.** A Runpod pod is a container with no engine or KVM
  inside, so a job runs unconfined there and the pod is its only jail. cairn
  1.17.0 hands a GPU only to a job a container engine runs, and refuses an
  unconfined GPU job. Each spec therefore asks for `gpus: 0` and says why in
  its `note`. The job uses the pod's GPU anyway; its `status.json` and IC
  report record which GPU.
- **The roster overstates the hardware.** cairn's probe reads the host's PCI
  bus and memory, so the node's roster can list GPUs and memory the pod does
  not have.
- **Large output is stopped.** cairn stops a job whose stdout or stderr passes
  64 MiB.

[`experiments/cairn-runpod-queue-20261006`](../experiments/cairn-runpod-queue-20261006/README.md)
is a run of all of this on an RTX 5090.

## Cursor workers on Modal

[`modal_worker.py`](modal_worker.py) runs the same kind of Cursor worker as
the pods, as a call of a Modal function in the app `cryptanalysis-workers`.
Each call does three things:

1. clones this repository into `/root/cryptanalysis`, in an image with the
   `cpu` or `cuda` toolchain of `modal_run.py`;
2. signs in and runs `agent worker --name NAME`;
3. returns after `--idle-minutes` without an agent session, CPU or GPU load,
   or edits, or after `--hours` (at most 24).

```sh
cloud/modal_worker.py up modal-cpu-1 modal-cpu-2 --cpu 16 --memory 64 --idle-minutes 120
cloud/modal_worker.py up modal-gpu-1 --gpu RTX-PRO-6000 --cpu 4 --memory 32 --idle-minutes 60
cloud/modal_worker.py status           # sign-in state, each worker's state and $/hr
cloud/modal_worker.py login            # the sign-in page
cloud/modal_worker.py logs modal-cpu-1
cloud/modal_worker.py down modal-gpu-1 # or --all, which also ends a pending sign-in
```

At Modal's list prices a 16-core, 64 GiB worker costs about $1.27/hr. A
4-core RTX PRO 6000 worker costs about $3.48/hr. Modal counts physical cores,
so 16 cores is 32 vCPUs.

**Signing in.** If the Modal secret `cursor-worker` holds a `CURSOR_API_KEY`,
the workers use it. Otherwise:

1. `up` queues the workers and starts `signin`, a quarter-core call (about
   $0.02/hr) that keeps an `agent login` link live for up to 24 hours. Each
   link lasts about 24 minutes, and `signin` replaces it when it lapses.
2. `up` prints a sign-in page, `https://a-buran28--cryptanalysis-signin.modal.run?k=<token>`,
   which always redirects to the live link. Open it while signed in to
   cursor.com as the account that should own the workers.
3. The sign-in is saved on the volume `cryptanalysis-workers` and the queued
   workers launch. Later launches reuse the saved sign-in and start at once.

The token keeps other people off the page. `login --new-token` replaces it.

A worker keeps its checkout on local disk. Before it stops, any uncommitted or
unpushed work is saved to `/persist/<name>/unsaved-*.tar.gz` on the volume.
Modal may occasionally preempt a function; the call then restarts on a new
container and reuses the saved sign-in.

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
shellcheck -x cloud/job_runner.sh cloud/worker/*.sh cloud/cairn_runner.sh cloud/pod_env.sh
```

The tests talk to no service. They run `job_runner.sh` and the queue's job
script locally, ship trees against a local repository standing in for
GitHub, and check the pod requests `fleet.py`, `runpod_pod.py` and
`cairn_queue.py` would send. With a cairn binary (`CAIRN_BIN`, or `cairn` on
`PATH`; CI downloads the release runners use), they also run queued jobs
through a real cairn agent and node.
