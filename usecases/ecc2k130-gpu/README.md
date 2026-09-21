# ECC2K-130 GPU rho — 20 B/s on one RTX PRO 6000

This is the **Certicom ECC2K-130** Pollard rho client (binary Koblitz curve
over `F_{2^131}`), not the prime-field GLV rho in `ca_curve.h`.

Upstream: [`aburan28/crypto`](https://github.com/aburan28/crypto) `ecc2k130/`
**main** (`a6ad623` / #507) already has `make gpu-rtx-pro6000-20b`. The patches
and bundle below are kept for replay onto older checkouts.

| artifact | purpose |
|----------|---------|
| `patches/0001-*.patch`, `0002-*.patch` | `git am` onto `aburan28/crypto` @ `c6d2a10` |
| `ecc2k130-20b.bundle` | the same two commits as a git bundle |
| `ONE-BLOCK-GEOMETRY.md` | measurement note (L1 geometry + tag denominators) |
| `scripts/cloud_launch.sh` | **one entrypoint** — Modal / RunPod GPU / ingest MiG |
| `scripts/runpod_deploy_ecc2k130.sh` | start/status/stop on a named RunPod GPU |
| `scripts/runpod_ingest_ecc2k130.sh` | `dp_ingest` on the MiG pod named `ingest` |
| `scripts/modal_deploy_ecc2k130.sh` | Modal deploy/bench/search/sync (20 B/s overlay) |
| `scripts/patch_modal_app_20b.py` | local overlay so Modal bakes the 20 B/s knobs |
| `docs/CLOUD_LAUNCH.md` | credentials, Make targets, GitHub Actions one-click |

## Measured on `solar_ivory_canidae` (live)

Hardware: NVIDIA RTX PRO 6000 Blackwell Server Edition (188 SMs).

| mode | result |
|------|--------|
| `--packed --bench` | **~19.5–20.1 B it/s** |
| verify 300 DPs vs host reference | **300 / 300** |
| live campaign `--dp-weight 34 --verify 0` | **~18.9 B it/s**, GPU ~95–97%, ~600 W |

Binary on the pod: `/root/ecc2k130-20b/bins/ecc2k130-rtx-pro6000-20b`  
Campaign dir: `/root/ecc2k130-campaign/` (tmux session `ecc2k130-20b`)

Fresh walks keep the GPU saturated. Archiving a multi-million DP corpus before
`--load` avoids host stalls at 0% GPU.

## Apply upstream (older trees only)

```sh
git clone https://github.com/aburan28/crypto.git && cd crypto
git checkout c6d2a10
git checkout -b ecc2k130-l1-geometry-and-tag-denominator
git am /path/to/cryptanalysis/usecases/ecc2k130-gpu/patches/*.patch
# or: git fetch /path/to/ecc2k130-20b.bundle && git checkout FETCH_HEAD
git push -u origin ecc2k130-l1-geometry-and-tag-denominator
```

On current `main`, just build:

```sh
cd ecc2k130
PATH=/opt/cuda133/cuda/bin:$PATH make gpu-rtx-pro6000-20b
./ecc2k130 --curve 131 --packed --bench --steps 1024 --launches 64 --verify 0
```

## One-click (preferred)

```sh
./scripts/cloud_launch.sh doctor
./scripts/cloud_launch.sh ingest start   # MiG pod "ingest" → Postgres/status.json
./scripts/cloud_launch.sh modal long     # 24h × 4 GPUs
./scripts/cloud_launch.sh runpod status  # solar_ivory_canidae GPU campaign
```

See [docs/CLOUD_LAUNCH.md](../../docs/CLOUD_LAUNCH.md) for Make targets and
the GitHub Actions “Cloud ECC2K-130” workflow.

## Campaign on RunPod (GPU)

```sh
export RUNPOD_API_KEY=...
./scripts/cloud_launch.sh runpod start   # default pod solar_ivory_canidae
./scripts/cloud_launch.sh runpod status
./scripts/cloud_launch.sh runpod stop
```

`--run-id` must fit in 16 bits (0..65535).

## Ingest on RunPod (MiG)

The pod named `ingest` is a MIG `1g.24gb` slice — use it for
`aws/ingest.sh` / `dp_ingest.py` so the status page sees S3 DPs without
burning a full GPU:

```sh
export RUNPOD_API_KEY=...
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
./scripts/cloud_launch.sh ingest start
./scripts/cloud_launch.sh ingest status
```

## Deploy on Modal

Needs Modal tokens. Stock `modal_app.py` does not bake the 20 B/s knobs; the
deploy script applies `patch_modal_app_20b.py` to a local crypto checkout.

Verified on Modal RTX PRO 6000: **20.05 B it/s** packed bench; search at
`ECC_RUN_ID=4242` stores DPs on the `ecc2k130` volume (avoid run-id 1 — stale
checkpoint).

```sh
export MODAL_TOKEN_ID=...
export MODAL_TOKEN_SECRET=...
./scripts/cloud_launch.sh modal setup
./scripts/cloud_launch.sh modal bench
./scripts/cloud_launch.sh modal long
./scripts/cloud_launch.sh modal sync-loop   # volume → S3 (pair with ingest)
```

Tokens: https://modal.com/settings/tokens
