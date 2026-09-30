# taskq workers for cryptanalysis

[taskq](https://github.com/aburan28/crypto/tree/main/taskq) is the shared
Redis job queue for `crypto`, `crypto-autoresearcher` and this repository. A
job names a pushed commit of this repository; a worker checks it out, builds
`ca` in the job's `setup` steps, runs the job and measures it with `wait4`
rusage, and collects everything the job writes to `$TASKQ_OUTPUT_DIR`. This
directory makes this repository a consumer of it:

| file | what it is |
| --- | --- |
| `Dockerfile.cpu`, `Dockerfile.gpu` | worker images: the taskq worker plus the C toolchain; the GPU one on `nvidia/cuda:12.8.1-devel-ubuntu24.04` for sm_120 |
| `values-cryptanalysis.yaml` | Helm values for the taskq chart: pools `ca-cpu` and `ca-gpu-sm120` |
| `ca_ecdlp_job.py` | runs `ca solve` on one instance and writes `metrics.json` and `certificate.json` |
| `instances/*.json` | toy prime-field ECDLP instances, with how each was generated |
| `examples/*.json` | `taskq.task-spec/v1` specs: a CPU rho solve, a CPU rho benchmark, a GPU rho solve |
| `testdata/` | real `ca solve` output the tests replay |

This adds plumbing only. It makes no performance claim, and a result from it
is subject to the same reporting rules as any other run ([AGENTS.md](../../AGENTS.md)).

## Build the images

The build context is this directory; nothing from the tree is copied in,
because the worker checks out each job's own commit.

```sh
docker build -f cloud/taskq/Dockerfile.cpu -t ghcr.io/aburan28/cryptanalysis-taskq-cpu:dev \
    --build-arg TASKQ_IMAGE=ghcr.io/aburan28/cryptanalysis-taskq-cpu:dev cloud/taskq
docker build -f cloud/taskq/Dockerfile.gpu -t ghcr.io/aburan28/cryptanalysis-taskq-gpu:dev \
    --build-arg TASKQ_IMAGE=ghcr.io/aburan28/cryptanalysis-taskq-gpu:dev cloud/taskq
```

`--build-arg TASKQ_REF=<sha>` pins the taskq client (default `main` of
aburan28/crypto). The GPU image has CUDA 12.8 only: enough for `ca`'s CUDA
backend at sm_120, not for ecc2k130's kernels, which need the CUDA 13.3
compiler (`cloud/worker/toolchain.sh`, `ecc2k130/scripts/fetch_cuda.sh`).
Neither image is built or published by CI yet.

## Deploy the pools

```sh
helm upgrade --install taskq <crypto checkout>/taskq/deploy/helm/taskq \
    -f cloud/taskq/values-cryptanalysis.yaml
```

The chart brings Redis (AOF on a PVC), the repo allowlist ConfigMap
(`cryptanalysis` → this repository's GitHub URL), the shared results PVC and
one Deployment per pool. Set the GPU pool's `nodeSelector` and `tolerations`
to your cluster's; the values file's comments say how to share another
release's Redis.

**Timing.** One task runs per pod. CPU timings are comparable only under
Guaranteed QoS with the static CPU manager policy (the values file sets
requests equal to limits). **GPU timing comparisons need exclusive nodes**: one
GPU pod per node and nothing else scheduled beside it, since a neighbour on the
same GPU, PCIe switch or CPU socket changes the result. A shared node gives
correct answers but no comparable timings.

## Submit a job

A job names a commit that is pushed: the worker fetches it. The example specs
carry the placeholder commit `0000000000000000000000000000000000000000`;
replace it before submitting.

```sh
pip install "taskq[mcp] @ git+https://github.com/aburan28/crypto.git#subdirectory=taskq"
export TASKQ_REDIS_URL=redis://:PASSWORD@redis-host:6379/0

sha=$(git rev-parse HEAD)      # pushed
jq --arg c "$sha" '.source.commit = $c' cloud/taskq/examples/cpu-rho-solve.json | taskq submit --spec -
taskq wait T-… ; taskq result T-…
```

or, without a spec file:

```sh
taskq submit --repo cryptanalysis --checkout . --queue ca-cpu --verify \
    --setup 'cmake -S . -B build/taskq-cpu -DCMAKE_BUILD_TYPE=Release -DCA_BUILD_TESTS=OFF -DCA_BUILD_SHARED=OFF' \
    --setup 'cmake --build build/taskq-cpu --target ca -j 4' \
    -- python3 cloud/taskq/ca_ecdlp_job.py --ca build/taskq-cpu/ca \
       --instance cloud/taskq/instances/generic-26.json --seed 1
```

From an agent, add the MCP server to `.mcp.json`
(`{"mcpServers": {"taskq": {"command": "taskq", "args": ["mcp"], "env": {"TASKQ_REDIS_URL": "…"}}}}`)
and call `submit_task` with a spec from `examples/`, then `wait_for_task` and
`get_result`.

The examples:

- `cpu-rho-solve.json`: `ca solve --alg rho` on `instances/generic-26.json`
  (a 22-bit prime-order subgroup), once.
- `cpu-rho-benchmark.json`: the same solver on `instances/p48-b111.json`
  (48-bit prime order), 1 warmup and 9 timed repetitions,
  `--seed-from-repetition` so each repetition starts a different walk.
- `gpu-rho-sm120.json`: `ca solve --alg gpu-rho --backend cuda` on
  `instances/p48-b111.json`, built with `-DCA_CUDA=ON -DCA_CUDA_ARCHITECTURES=120`
  and routed to a `gpu=sm120` worker. `--backend cuda` fails with status
  `unsupported` rather than falling back to the CPU emulator when no CUDA
  device or build is present. The last setup step records `ca gpu-info`.

All three set `"verify": {"builtin": "certificate"}`, which needs a taskq with
certificate verification (aburan28/crypto#1091). An older worker refuses the
field at submit time; drop it there and run `python -m taskq.verify
certificate.json` on the collected artifact instead.

## The job wrapper

```sh
python3 cloud/taskq/ca_ecdlp_job.py --ca build/ca --instance cloud/taskq/instances/generic-26.json \
    [--alg rho|gpu-rho|glv|dlog|kangaroo|bsgs|grumpy|precomp] [--seed S] [--seed-from-repetition] \
    [--threads T] [--max-ops N] [--out DIR] [-- EXTRA ca solve ARGS]
```

It runs `ca solve --alg ALG --group ec --p P --a A --b B --order N --g Px,Py
--h Qx,Qy` and parses the one JSON line `ca solve` prints, for example
(captured in `testdata/rho-generic-26-seed1.stdout`):

```json
{"status":"ok","alg":"rho","x":1234567,"ops":2869,"iterations":90,"table_entries":85,"collisions":4,"bytes_peak":98688,"seconds":0.000421,"threads":1}
```

Into `--out` (default `$TASKQ_OUTPUT_DIR`) it writes:

- `metrics.json`: the solver's counters as printed (`ops`, `iterations`,
  `table_entries`, `collisions`, `bytes_peak`, `threads`, and `launches` for
  gpu-rho), its `seconds` as `solver_seconds`, `solver_status`,
  `solver_exit_code`, `solved`, `k`, the instance's name, path and sha256,
  the exact argv, `wrapper_wall_seconds` (the parent's clock around the solver
  process), and the derived `ops_per_sqrt_order` (the repo's `S = ops/sqrt(n)`).
- `certificate.json`: when, and only when, the solver printed `"status":"ok"`
  with a scalar:
  `{"kind": "discrete_log", "curve": {"field": "prime", "p", "a", "b"}, "statement": {"P", "Q", "k", "n"}}`
  with decimal strings; otherwise `{"kind": "none"}`. The wrapper does not
  check the claim itself. The verifier (`taskq.verify`) shares no code with
  the solver and checks that P and Q are on the curve, that `n*P = O`, and
  that `k*P = Q`.
- `solver.stdout` (and `solver.stderr`, if any): the solver's output verbatim.

Its exit status is the solver's (0 solved, 1 a solver status such as `limit
reached`, 2 bad arguments), or 3 if the solver exited 0 without a parseable
answer. A nonzero exit makes the taskq run `failed`; its metrics and
certificate are still collected. As everywhere in this program, an unsolved,
timed-out or failed run is no evidence about the instance.

`ca solve` takes 64-bit integers, so instances are prime-field curves with
`p < 2^64`. Binary-field instances (such as ECC2K-130) go through their own
tools, not this wrapper.

## Test data

`testdata/*.stdout|stderr` were captured from `ca` built at
72292477fc0a9bd76a998f9b33ff827ea39aadce with
`cmake -DCMAKE_BUILD_TYPE=Release -DCA_BUILD_TESTS=OFF -DCA_BUILD_SHARED=OFF`
(no CUDA), from the `ca solve` commands the wrapper builds for the named
instance, algorithm and seed; `gpu-rho-emulate-*` used `--backend emulate`,
`gpu-rho-cuda-not-compiled` used `--backend cuda` on that CPU-only build, and
`rho-bad-point.stderr` came from giving `--g 1,1`, which is not on the curve.
The tests in `cloud/tests/test_taskq_job.py` replay them through a stand-in
`ca`:

```sh
python3 -m unittest discover -s cloud/tests -p 'test_taskq_job.py' -v
CA_BIN=build/ca python3 -m unittest discover -s cloud/tests -p 'test_taskq_job.py'   # also the real solver
```

The schema tests need `taskq` importable; they skip otherwise.
