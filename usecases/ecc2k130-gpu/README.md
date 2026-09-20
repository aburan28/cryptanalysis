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
| `scripts/runpod_deploy_ecc2k130.sh` | start/status/stop on a named RunPod |
| `scripts/modal_deploy_ecc2k130.sh` | Modal deploy/bench/search (20 B/s overlay) |
| `scripts/patch_modal_app_20b.py` | local overlay so Modal bakes the 20 B/s knobs |

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

## Campaign on RunPod

```sh
export RUNPOD_API_KEY=...
./scripts/runpod_deploy_ecc2k130.sh          # start (default pod solar_ivory_canidae)
./scripts/runpod_deploy_ecc2k130.sh status
./scripts/runpod_deploy_ecc2k130.sh stop
```

`--run-id` must fit in 16 bits (0..65535).

## Deploy on Modal

Needs Modal tokens. Stock `modal_app.py` does not bake the 20 B/s knobs; the
deploy script applies `patch_modal_app_20b.py` to a local crypto checkout.

Verified on Modal RTX PRO 6000: **20.05 B it/s** packed bench; search at
`ECC_RUN_ID=4242` stores DPs on the `ecc2k130` volume (avoid run-id 1 — stale
checkpoint).

```sh
export MODAL_TOKEN_ID=...
export MODAL_TOKEN_SECRET=...
./scripts/modal_deploy_ecc2k130.sh setup
./scripts/modal_deploy_ecc2k130.sh deploy
./scripts/modal_deploy_ecc2k130.sh bench     # --threads 512 --min-blocks 1
ECC_HOURS=4 ./scripts/modal_deploy_ecc2k130.sh search
ECC_FANOUT=8 ECC_HOURS=4 ./scripts/modal_deploy_ecc2k130.sh fanout
```

Tokens: https://modal.com/settings/tokens
