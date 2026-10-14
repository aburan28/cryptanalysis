#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

# Run on a trusted Linux Pod with: ssh SSH_ALIAS 'bash -s' < this_script
command -v curl >/dev/null || { echo 'curl is required' >&2; exit 1; }
command -v git >/dev/null || { echo 'git is required' >&2; exit 1; }
command -v sha256sum >/dev/null || { echo 'sha256sum is required to verify Conductor' >&2; exit 1; }

# Cloud agent sessions must register before their CLI starts. Download the
# published Linux release and verify its archive against the release checksums.
if ! command -v conductor >/dev/null; then
  mkdir -p "$HOME/.local/bin"
  case "$(uname -m)" in
    x86_64|amd64) conductor_arch=amd64 ;;
    aarch64|arm64) conductor_arch=arm64 ;;
    *) echo 'unsupported architecture for Conductor' >&2; exit 1 ;;
  esac
  conductor_repo=${CONDUCTOR_RELEASE_REPO:-aburan28/conductor}
  conductor_base="https://github.com/${conductor_repo}/releases"
  conductor_version=${CONDUCTOR_RELEASE_VERSION:-}
  if [[ -z $conductor_version ]]; then
    conductor_version="$(curl -fsSI "$conductor_base/latest" \
      | awk 'tolower($1) == "location:" { n = split($2, p, "/"); print p[n] }' \
      | tr -d '\r\n ')"
  fi
  [[ -n $conductor_version ]] || { echo 'could not resolve a Conductor release' >&2; exit 1; }
  conductor_asset="conductor_${conductor_version}_linux_${conductor_arch}.tar.gz"
  conductor_tmp=$(mktemp -d)
  trap 'rm -rf "$conductor_tmp"' EXIT
  if ! curl -fSL --retry 3 -o "$conductor_tmp/$conductor_asset" \
    "$conductor_base/download/$conductor_version/$conductor_asset"; then
    # Newer release workflows omit the v prefix inside the archive name.
    conductor_asset="conductor_${conductor_version#v}_linux_${conductor_arch}.tar.gz"
    curl -fSL --retry 3 -o "$conductor_tmp/$conductor_asset" \
      "$conductor_base/download/$conductor_version/$conductor_asset"
  fi
  curl -fSL --retry 3 -o "$conductor_tmp/SHA256SUMS" \
    "$conductor_base/download/$conductor_version/SHA256SUMS"
  grep " ${conductor_asset}\$" "$conductor_tmp/SHA256SUMS" \
    | (cd "$conductor_tmp" && sha256sum -c -)
  tar -xzf "$conductor_tmp/$conductor_asset" -C "$conductor_tmp"
  install -m 0755 \
    "$conductor_tmp/${conductor_asset%.tar.gz}/conductor" \
    "$HOME/.local/bin/conductor"
fi

if ! command -v codex >/dev/null; then
  curl -fsSL https://chatgpt.com/codex/install.sh | sh
fi
if ! command -v claude >/dev/null; then
  curl -fsSL https://claude.ai/install.sh | bash
fi

command -v codex >/dev/null || { echo 'Codex installation was not found on PATH' >&2; exit 1; }
command -v claude >/dev/null || { echo 'Claude Code installation was not found on PATH' >&2; exit 1; }
codex --version
claude --version
conductor version
