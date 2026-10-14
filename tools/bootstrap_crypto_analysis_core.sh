#!/usr/bin/env bash
set -euo pipefail

# The suite imports these two modules from crypto. Keep the dependency small:
# Cargo's git source would check out crypto's entire research tree.
rev="e4f200cc2da058492a9a27f348fb88dc23f8a745"
remote="${CRYPTO_ANALYSIS_CORE_REMOTE:-https://github.com/aburan28/crypto.git}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
checkout="$root/deps/crypto"

if [[ -L "$checkout" ]]; then
  echo "Remove the local deps/crypto symlink before bootstrapping the pinned checkout" >&2
  exit 1
fi
if [[ ! -d "$checkout/.git" ]]; then
  if [[ -e "$checkout" ]]; then
    echo "deps/crypto exists but is not a Git checkout" >&2
    exit 1
  fi
  mkdir -p "$checkout"
  git -C "$checkout" init -q
  git -C "$checkout" remote add origin "$remote"
  git -C "$checkout" sparse-checkout set --no-cone \
    /crates/crypto-analysis-core/ \
    /src/cryptanalysis/avalanche.rs \
    /src/cryptanalysis/statistical.rs
fi

if [[ "$(git -C "$checkout" rev-parse HEAD 2>/dev/null || true)" != "$rev" ]]; then
  if [[ -n "$(git -C "$checkout" status --porcelain)" ]]; then
    echo "deps/crypto has local changes; refusing to replace them" >&2
    exit 1
  fi
  git -C "$checkout" -c protocol.version=2 fetch --no-tags --depth=1 --filter=blob:none origin "$rev"
  git -C "$checkout" checkout --detach --force "$rev"
fi

[[ "$(git -C "$checkout" rev-parse HEAD)" == "$rev" ]]
test -f "$checkout/crates/crypto-analysis-core/Cargo.toml"
test -f "$checkout/src/cryptanalysis/avalanche.rs"
test -f "$checkout/src/cryptanalysis/statistical.rs"
