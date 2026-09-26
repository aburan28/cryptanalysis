#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the cryptanalysis repository.
#
# Provisions the toolchain the repository's checks expect (C/CMake, the Rust
# bindings and attack suite, the Go coordinator, the Python binding and the
# index-calculus engine, plus the static-analysis and lint gates) and builds
# the C library so `ca`, libcryptanalysis.{a,so} and the Python binding are
# ready to use. Safe to re-run: every step skips work that is already done.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

log() { printf '\n=== %s ===\n' "$*"; }

# ---- system packages: static analysis and lint gates -----------------------
apt_pkgs=(clang-tidy clang-format cppcheck shellcheck valgrind gcovr gdb)
missing_apt=()
for p in "${apt_pkgs[@]}"; do
  dpkg -s "$p" >/dev/null 2>&1 || missing_apt+=("$p")
done
if ((${#missing_apt[@]})); then
  log "Installing apt packages: ${missing_apt[*]}"
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing_apt[@]}"
fi

# ---- Python tooling --------------------------------------------------------
# ruff/mypy gate the Python binding and index-calculus engine; the SAT back
# ends power `ca-ic fixed --solver sat` and the tests that exercise it.
if ! command -v ruff >/dev/null 2>&1 || ! command -v mypy >/dev/null 2>&1; then
  log "Installing Python lint tooling (ruff, mypy)"
  pip3 install --break-system-packages -q ruff mypy
fi
if ! python3 -c 'import pysat' >/dev/null 2>&1; then
  log "Installing SAT back ends for the index-calculus engine"
  pip3 install --break-system-packages -q -r suite/python/indexcalc/requirements-sat.txt
fi

# ---- Rust toolchain --------------------------------------------------------
# cryptanalysis-cuda requires rustc 1.88 and the suite requires 1.87; the base
# image ships an older stable, so pin the current stable as the default.
if command -v rustup >/dev/null 2>&1; then
  rustup show active-toolchain >/dev/null 2>&1 || rustup toolchain install stable
  rustup default stable
  # rustfmt/clippy gate the bindings and the suite.
  rustup component add rustfmt clippy >/dev/null 2>&1 || true
fi
# cargo-deny gates the suite's dependency-license check.
if ! command -v cargo-deny >/dev/null 2>&1; then
  log "Installing cargo-deny"
  cargo install cargo-deny --locked
fi

# ---- Build the C library, CLI and Python-loadable shared object ------------
log "Configuring and building the C library (Release)"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc 2>/dev/null || echo 4)"

log "Toolchain versions"
cmake --version | head -1
"${CC:-cc}" --version | head -1 || true
rustc --version || true
go version || true
python3 --version || true

log "Environment ready. Try: ./build/ca gpu-info"
