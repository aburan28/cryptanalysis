#!/usr/bin/env bash
# toolchain.sh - build tools for agents on a fleet pod.
#
# boot.sh runs this in the background (tmux session `fleet-toolchain`) after
# the Cursor worker is up, so the worker is reachable while it installs.  apt
# packages live on the container disk and are reinstalled at every boot (from
# a .deb cache on the volume); everything else is built once under /workspace.
# Features come from FLEET_FEATURES: msolve, sage, cuda13.
# /workspace/fleet/toolchain.json records what is installed once it finishes.
set -uo pipefail

FLEET=/workspace/fleet
SRC="$FLEET/src"
OPT=/workspace/opt
VENV=/workspace/venv
# shellcheck source=/dev/null
source "$FLEET/config.env"
# shellcheck source=/dev/null
source "$FLEET/env.sh"

exec 8>"$FLEET/toolchain.lock"
if ! flock -n 8; then
  echo "toolchain.sh is already running"
  exit 0
fi
rm -f "$FLEET/toolchain.json"

log() { printf '[fleet toolchain %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
has() { [[ ",${FLEET_FEATURES:-}," == *",$1,"* ]]; }
failed=()

# ---- system packages ------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
APT_PKGS=(
  build-essential cmake ninja-build pkg-config autoconf automake libtool m4
  git git-lfs curl wget ca-certificates jq rsync unzip zip zstd xz-utils bzip2
  time bc htop file less tmux lsof strace gdb
  python3 python3-venv python3-dev python3-pip
  libgmp-dev libmpfr-dev libflint-dev libssl-dev libffi-dev zlib1g-dev
  clang clang-format clang-tidy cppcheck valgrind
  golang-go iverilog verilator yosys gh
)
log "apt: ${#APT_PKGS[@]} packages"
apt-get update -qq
if ! apt-get -o Dir::Cache::Archives="$FLEET/apt-archives" install -y -qq \
  --no-install-recommends "${APT_PKGS[@]}" >/dev/null; then
  failed+=(apt)
fi

# ---- Rust -------------------------------------------------------------------------
if [[ ! -x "$CARGO_HOME/bin/cargo" ]]; then
  log "installing Rust (stable)"
  curl -fsSL https://sh.rustup.rs |
    sh -s -- -y -q --profile minimal --default-toolchain stable \
      -c clippy -c rustfmt --no-modify-path || failed+=(rust)
fi

# ---- Python -----------------------------------------------------------------------
REQ="$SRC/cloud/worker/requirements.txt"
if [[ ! -x "$VENV/bin/python" ]]; then
  log "creating $VENV"
  python3 -m venv --system-site-packages "$VENV" || failed+=(venv)
fi
want=$(sha256sum "$REQ" | cut -c1-16)
if [[ -x "$VENV/bin/pip" && "$(cat "$VENV/.requirements" 2>/dev/null)" != "$want" ]]; then
  log "pip install -r cloud/worker/requirements.txt"
  if "$VENV/bin/pip" install -q --upgrade pip && "$VENV/bin/pip" install -q -r "$REQ"; then
    echo "$want" >"$VENV/.requirements"
  else
    failed+=(pip)
  fi
fi

# ---- msolve (experiments/pdp-scaling) ------------------------------------------------
if has msolve && [[ ! -x "$OPT/msolve/bin/msolve" ]]; then
  log "building msolve 0.10.1"
  tmp=$(mktemp -d)
  if git -c advice.detachedHead=false clone -q --depth 1 --branch v0.10.1 \
    https://github.com/algebraic-solving/msolve "$tmp/msolve" &&
    (cd "$tmp/msolve" && ./autogen.sh >/dev/null 2>&1 &&
      ./configure -q --prefix="$OPT/msolve" &&
      make -s -j"$FLEET_CPUS" && make -s install) >"$FLEET/logs/msolve-build.log" 2>&1; then
    log "msolve installed"
  else
    failed+=(msolve)
  fi
  rm -rf "$tmp"
fi

# ---- SageMath (volcano-ic, volcano-descendants-hardness) ------------------------------
if has sage; then
  if [[ ! -x "$OPT/sage/bin/sage" ]]; then
    log "installing SageMath 10.9 from conda-forge (several minutes)"
    mkdir -p "$OPT/micromamba"
    if [[ ! -x "$OPT/micromamba/bin/micromamba" ]]; then
      curl -fsSL https://micro.mamba.pm/api/micromamba/linux-64/latest |
        tar --no-same-owner -xj -C "$OPT/micromamba" bin/micromamba
    fi
    MAMBA_ROOT_PREFIX="$OPT/mamba" "$OPT/micromamba/bin/micromamba" create -y -q \
      -p "$OPT/sage" -c conda-forge "sage=10.9" >"$FLEET/logs/sage-install.log" 2>&1 ||
      failed+=(sage)
  fi
  if [[ -x "$OPT/sage/bin/sage" ]]; then
    ln -sfn "$OPT/sage/bin/sage" /usr/local/bin/sage
  fi
fi

# ---- CUDA 13.3 compiler (ecc2k130 needs clmad from PTX 9.3) ---------------------------
if has cuda13 && [[ ! -x "$CUDA13_HOME/bin/nvcc" ]]; then
  log "fetching the CUDA 13.3 compiler wheels"
  PATH="$VENV/bin:$PATH" sh "$SRC/ecc2k130/scripts/fetch_cuda.sh" "$CUDA13_HOME" \
    >"$FLEET/logs/cuda13-fetch.log" 2>&1 || failed+=(cuda13)
fi

# ---- record -----------------------------------------------------------------------------
first_line() { "$@" 2>/dev/null | head -n1 || true; }
exe() { [[ -x "$1" ]] && echo "$1"; }
nvcc_release() { "$1" --version 2>/dev/null | grep -o 'release [0-9.]*' || true; }
python3 - "$FLEET/toolchain.json" \
  "failed=${failed[*]:-}" \
  "gcc=$(first_line gcc --version)" \
  "cmake=$(first_line cmake --version)" \
  "rustc=$(first_line "$CARGO_HOME/bin/rustc" --version)" \
  "python=$(first_line "$VENV/bin/python" --version)" \
  "go=$(first_line go version)" \
  "msolve=$(exe "$OPT/msolve/bin/msolve")" \
  "sage=$(exe "$OPT/sage/bin/sage")" \
  "nvcc=$(command -v nvcc >/dev/null && nvcc_release nvcc)" \
  "nvcc13=$(exe "$CUDA13_HOME/bin/nvcc")" <<'EOF'
import json, sys
record = dict(arg.split("=", 1) for arg in sys.argv[2:])
out = {k: v or None for k, v in record.items()}
out["failed"] = record["failed"].split()
with open(sys.argv[1], "w") as f:
    json.dump(out, f, indent=1)
EOF
if ((${#failed[@]})); then
  log "finished with failures: ${failed[*]} (see /workspace/fleet/logs)"
else
  log "finished"
fi
