# ECC2K-130 GPU rho — 20 B/s on one RTX PRO 6000

This is the **Certicom ECC2K-130** Pollard rho client (binary Koblitz curve
over `F_{2^131}`), not the prime-field GLV rho in `ca_curve.h`.

Upstream live tree: [`aburan28/crypto`](https://github.com/aburan28/crypto)
`ecc2k130/`. The two commits that reach **20.08 B complete scalar updates / s**
on one RTX PRO 6000 Blackwell are vendored here until that branch is pushed
upstream (this Cloud Agent cannot write to `aburan28/crypto`).

| artifact | purpose |
|----------|---------|
| `patches/0001-*.patch`, `0002-*.patch` | `git am` onto `aburan28/crypto` @ `c6d2a10` |
| `ecc2k130-20b.bundle` | the same two commits as a git bundle |
| `ONE-BLOCK-GEOMETRY.md` | measurement note (L1 geometry + tag denominators) |
| `scripts/runpod_deploy_ecc2k130.sh` | start/stop the campaign on a named RunPod |

## Measured on `solar_ivory_canidae` (this deploy)

Hardware: NVIDIA RTX PRO 6000 Blackwell Server Edition (188 SMs).

| mode | result |
|------|--------|
| `--packed --bench` (throughput only) | **~19.5 B it/s** |
| verify 300 DPs vs host reference | **300 / 300** |
| live campaign `--dp-weight 34 --verify 64` | GPU ~97%, climbing past **10 B it/s** while storing DPs |

Binary on the pod: `/root/ecc2k130-20b/bins/ecc2k130-rtx-pro6000-20b`  
Campaign dir: `/root/ecc2k130-campaign/` (tmux session `ecc2k130-20b`)

## Apply upstream (when you have write access to `crypto`)

```sh
git clone https://github.com/aburan28/crypto.git && cd crypto
git checkout c6d2a10
git checkout -b ecc2k130-l1-geometry-and-tag-denominator
git am /path/to/cryptanalysis/usecases/ecc2k130-gpu/patches/*.patch
# or: git fetch /path/to/ecc2k130-20b.bundle && git checkout FETCH_HEAD
git push -u origin ecc2k130-l1-geometry-and-tag-denominator
```

Build on a CUDA 13.3 host (see `README.txt`):

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

`--run-id` must fit in 16 bits (0..65535). Fresh walks (no giant `--load`) keep
the GPU saturated near 19 B/s; archive old `dps.bin` before reloading millions
of orbits or the host stalls at 0% GPU.

## Deploy on Modal

Source of truth is `aburan28/crypto` `main` (PR #507). Needs Modal tokens:

```sh
export MODAL_TOKEN_ID=...
export MODAL_TOKEN_SECRET=...
./scripts/modal_deploy_ecc2k130.sh setup
./scripts/modal_deploy_ecc2k130.sh deploy
./scripts/modal_deploy_ecc2k130.sh bench     # packed throughput on RTX-PRO-6000
ECC_HOURS=4 ./scripts/modal_deploy_ecc2k130.sh search
ECC_FANOUT=8 ECC_HOURS=4 ./scripts/modal_deploy_ecc2k130.sh fanout
```

Tokens: https://modal.com/settings/tokens