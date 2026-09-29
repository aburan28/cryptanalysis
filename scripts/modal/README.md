# Modal Sage calculation workers

This launcher builds the repository's current Sage source fork in a Linux
Modal image, then starts one isolated Sandbox per calculation. Each Sandbox
checks out a **full commit SHA** from `aburan28/cryptanalysis`, validates its
Linux Sage installation through a generated `runtime-current.json`, saves
`sage-runtime-info.json`, and invokes the checkout's `sage` launcher. The
source archive includes local, possibly uncommitted Sage fork changes. Job
scripts must be committed and pushed to the Git remote before launch.

The first Sage image build is large and may take hours. Modal caches it until
the source archive or build instructions change. It is compiled on Linux;
the local macOS installation and its binaries are excluded.
The `validators/` files are copies of the installed-runtime and CPU
compatibility validators from this workspace. Their bytes are pinned in the
Modal image and compatibility receipt.

## Local setup

Install and authenticate the [Modal Python SDK](https://modal.com/docs/guide):

```sh
python3 -m pip install 'modal>=1.2.6'
modal setup
```

From the repository root, package the current source fork:

```sh
scripts/modal/package_sage_source.sh
```

The archive goes to `scripts/modal/.build/sage-source.tar.gz`. Inspect the
source changes before packaging; the archive is uploaded to Modal during image
build. The archive must never be committed.

## Launch

Use a script from a pushed commit. The script should put durable output under
`MODAL_JOB_OUTPUT`, which is a unique directory on the results Volume. The
script's own timer must delimit any target-dependent online interval; Modal
startup, source checkout, and Sage checks are outside it.

```sh
python3 scripts/modal/modal_app.py \
  --revision FULL_40_CHARACTER_COMMIT_SHA \
  --script scripts/modal/smoke_sage.py \
  --job-id sage-smoke-r1 \
  --cpu 8 --memory-mb 32768 --timeout-s 86400
```

The launcher prints a `sandbox_id`. Jobs continue after the local process
disconnects, up to Modal's 24-hour Sandbox lifetime. Run multiple commands
with distinct job IDs to use parallel workers; each gets its own resource
allocation and output directory. A job is one measured execution, so keep
its scientific workload, seed, and resource limits explicit in the script and
result record. IC comparisons must also follow `AGENTS.md` and the candidate
catalog measurement contract.

For a real campaign, replace `--script` with a committed experiment path and
pass script arguments through `--args-json '["--seed","1"]'`. The smoke job
only checks arithmetic; its nanosecond field is not a performance result.

Inspect and download output:

```sh
modal volume ls cryptanalysis-sage-results sage-smoke-r1
modal volume get cryptanalysis-sage-results sage-smoke-r1 ./modal-results/sage-smoke-r1
modal app dashboard cryptanalysis-sage-jobs
```

The output directory contains `status.json`, `sage-runtime-info.json`,
`tool-versions.json`, `compatibility/receipt.json`, and `job.log`. It can
contain any additional files the job writes to
`MODAL_JOB_OUTPUT`. A failure remains recorded in `status.json`. Result
directories are never silently overwritten. Keep external checkpoints in the
Volume if a computation needs more than 24 hours; a later Sandbox can resume
from them with a new job ID.

## Scope and verification

The image installs a C/C++/Fortran toolchain, Rust/Cargo 1.94.1, M4RI headers,
CryptoMiniSat, Redis, zstd, and the Sage source fork. Sage builds its own
remaining dependencies. The Linux acceptance step checks installed module
origins and hashes, exercises native binary-curve dispatch, then runs the
installed scalar, batch, and CPU backend compatibility suite before a job
starts. CUDA, Metal, OpenCL, and hardware
speedups are outside this CPU image; use the hardware compatibility protocol
before claiming or automatically routing to a device backend.

The image build and full remote calculation have not been run by adding these
scripts. A first launch is the integration test for Ubuntu dependency and
source-build compatibility. If it fails, Modal retains the build log and no
calculation is started.
