# One-click cloud launch (Modal + RunPod)

Launch the ECC2K-130 packed GPU rho client (~20 B it/s on one RTX PRO 6000)
without hand-assembling Modal/RunPod commands. The unified entrypoint is
[`scripts/cloud_launch.sh`](../scripts/cloud_launch.sh).

```sh
./scripts/cloud_launch.sh doctor     # what credentials / CLIs are missing?
./scripts/cloud_launch.sh modal long # 24h × 4 GPUs on Modal (true one-click)
./scripts/cloud_launch.sh ingest start   # MiG pod "ingest" → Postgres + status.json
./scripts/cloud_launch.sh runpod status
make cloud-doctor && make ingest-start && make modal-long
```

GitHub one-click: **Actions → “Cloud ECC2K-130” → Run workflow** (see below).

This is the Certicom Koblitz challenge over `F_{2^131}`, not the prime-field
GLV path in `ca_curve.h`. Details and measurements live in
[usecases/ecc2k130-gpu/README.md](../usecases/ecc2k130-gpu/README.md).

## Credentials

| Backend | Required | Where |
|---------|----------|-------|
| **Modal** (preferred GPU one-click) | `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | https://modal.com/settings/tokens |
| **RunPod** (GPU campaign + ingest MiG) | `RUNPOD_API_KEY` + SSH key `~/.ssh/id_ed25519` | https://console.runpod.io/user/settings |
| Status page + ingest | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Modal volume→S3 sync **and** the ingest MiG host |

Install once:

```sh
pip install 'modal>=0.72' boto3   # boto3 for sync / ingest tooling locally
# runpodctl: https://docs.runpod.io/runpodctl
```

`cloud_launch doctor` reports what is missing. It succeeds when **at least one**
of Modal or RunPod is ready; AWS is required for ingest and for Modal workers
to appear on the public status page.

## Modal (recommended GPU fanout)

Modal builds and runs the 20 B/s geometry remotely. No local GPU or CUDA
toolkit. Stock `modal_app.py` does not bake the knobs; the deploy script
applies [`scripts/patch_modal_app_20b.py`](../scripts/patch_modal_app_20b.py)
to a local clone of [`aburan28/crypto`](https://github.com/aburan28/crypto).

```sh
export MODAL_TOKEN_ID=…
export MODAL_TOKEN_SECRET=…

./scripts/cloud_launch.sh modal setup    # clone crypto + auth
./scripts/cloud_launch.sh modal bench    # packed throughput check
./scripts/cloud_launch.sh modal long     # 24h × ECC_FANOUT (default 4) GPUs
./scripts/cloud_launch.sh modal sync     # volume → S3 (needs AWS_*)
./scripts/cloud_launch.sh modal sync-loop
```

Useful env knobs:

| Variable | Default | Meaning |
|----------|---------|---------|
| `ECC_HOURS` | `24` | search / fanout duration |
| `ECC_FANOUT` | `4` | parallel Modal GPUs |
| `ECC_RUN_ID` | `4242` | base run-id (avoid `1` — stale volume ckpt) |
| `ECC_GPU` | `RTX-PRO-6000` | Modal GPU string |
| `ECC_BUCKET` | account default | S3 bucket for status sync |
| `SYNC_INTERVAL` | `120` | seconds between sync-loop passes |
| `CRYPTO_DIR` | `$HOME/src/crypto` | local crypto checkout |

Make aliases: `make modal-setup`, `make modal-bench`, `make modal-long`,
`make modal-sync`, `make modal-sync-loop`.

## RunPod multi-GPU fanout (`marginal_chocolate_ostrich`)

The 8-GPU pod exposes **8× MIG `1g.24gb`** slices. Launch one packed worker
per slice (~4.9 B it/s each, ~39 B it/s aggregate):

```sh
export RUNPOD_API_KEY=…
./scripts/cloud_launch.sh fanout start    # WORKERS=8, BASE_RUN_ID=5000
./scripts/cloud_launch.sh fanout status
./scripts/cloud_launch.sh fanout stop
```

Overrides: `POD_NAME`, `WORKERS`, `BASE_RUN_ID`, `BIN_HOST` (copy
`ecc2k130-rtx-pro6000-20b` onto the pod first if missing). Make:
`make fanout-start`, `make fanout-status`, `make fanout-stop`.

## RunPod GPU campaign (`solar_ivory_canidae`)

Expects a **running** full-GPU pod that already has the 20 B/s binary (default
name `solar_ivory_canidae`, binary at
`/root/ecc2k130-20b/bins/ecc2k130-rtx-pro6000-20b`). This path starts or
stops a single campaign in tmux.

```sh
export RUNPOD_API_KEY=…
./scripts/cloud_launch.sh runpod start
./scripts/cloud_launch.sh runpod status
./scripts/cloud_launch.sh runpod stop
```

Overrides: `POD_NAME`, `SSH_KEY`, `RUN_ID` (16-bit). Make: `make runpod-start`,
`make runpod-status`, `make runpod-stop`.

For attaching a Cursor My Machines worker to the same pod, see
[RUNPOD_CURSOR_WORKER.md](RUNPOD_CURSOR_WORKER.md).

## Ingest MiG pod (`ingest`)

GPU workers write distinguished points to S3 (or a Modal volume that you sync).
The public status page reads **Postgres + `status.json`**, which are filled by
`aws/ingest.sh` / `dp_ingest.py` from upstream crypto.

Run that loop on the cheap RunPod **MiG** instance named `ingest` (MIG
`1g.24gb` on an RTX PRO 6000) instead of tying up a full GPU:

```sh
export RUNPOD_API_KEY=…
export AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=…
./scripts/cloud_launch.sh ingest start    # ensure SSH, clone crypto, tmux ingest
./scripts/cloud_launch.sh ingest status
./scripts/cloud_launch.sh ingest stop
```

The script merges your SSH pubkey into the pod's `PUBLIC_KEY` env and restarts
once if needed (same pattern as the Cursor worker attach). On start it writes
`~/.aws/credentials` on the pod, clones `aburan28/crypto`, and runs
`ecc2k130/aws/ingest.sh` in tmux session `ecc2k130-ingest` with
`INGEST_ENSURE_ACCESS=1` so the pod's egress IP is admitted to the RDS SG.

Overrides: `INGEST_POD_NAME` (default `ingest`), `INGEST_THREADS`,
`ECC_BUCKET`, `ECC_STATUS_BUCKET`, `CRYPTO_REMOTE` (path on the pod).

Make: `make ingest-start`, `make ingest-status`, `make ingest-stop`.

## GitHub Actions one-click

Workflow: [`.github/workflows/cloud-ecc2k130.yml`](../.github/workflows/cloud-ecc2k130.yml).

1. Repo **Settings → Secrets and variables → Actions**, add at least
   `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`. Optional: `RUNPOD_API_KEY`,
   `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ECC_BUCKET`,
   `RUNPOD_SSH_PRIVATE_KEY` (for ingest/runpod from Actions).
2. **Actions → Cloud ECC2K-130 → Run workflow**.
3. Pick an action: `doctor`, `bench`, `long`, `sync`, `ingest-start`,
   `ingest-status`, or `runpod-status`.

`long` bills Modal GPU time (default 24 h × 4). Prefer `bench` first.
`ingest-*` needs `RUNPOD_API_KEY` + AWS secrets and
`RUNPOD_SSH_PRIVATE_KEY`.

## Status page visibility

Three durable syncers keep S3 (and then ingest) fed:

1. **Modal volume → S3** (must stay up — Modal workers are invisible without it):
   ```sh
   ./scripts/cloud_launch.sh sync ensure    # tmux ecc2k130-modal-sync + autorestart
   ./scripts/cloud_launch.sh sync status
   make modal-sync-ensure
   ```
2. **RunPod dps.bin → S3** (ostrich fanout + solar campaign):
   ```sh
   POD_NAME=marginal_chocolate_ostrich CAMP_ROOT=/root/ecc2k130-fanout \
     WORKERS=8 BASE_RUN_ID=5000 ./scripts/cloud_launch.sh sync runpod
   POD_NAME=solar_ivory_canidae CAMP_ROOT=/root/ecc2k130-campaign \
     WORKERS=1 BASE_RUN_ID=4242 ./scripts/cloud_launch.sh sync runpod
   ```
3. **S3 → Postgres + status.json** on the MiG ingest pod:
   `./scripts/cloud_launch.sh ingest start`

`sync` expands `ECC_RUN_ID` across `ECC_FANOUT` so run-ids `4242–4245` all
publish when you launched with the defaults. The ensure wrapper kills any
loose `modal_sync --watch` process so only one syncer runs.

## What “all” does

```sh
./scripts/cloud_launch.sh all
# or: make cloud-all
```

Runs doctor (non-fatal), ingest + RunPod status if configured, then Modal
`long`. Does not start `sync-loop` or `ingest start` automatically (those are
long-lived — run `make ingest-start` and `make modal-sync-loop` in separate
terminals once).
