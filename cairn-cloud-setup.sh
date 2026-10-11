#!/usr/bin/env bash
# Install and run Cairn in a Linux cloud workspace.
#
#   cairn-cloud-setup.sh [all|install|start|stop|status] [--require-seed]
#
#   all (default)  install, then start a background node
#   install        download, verify, and install only
#   start          start the node (idempotent) and report seed reachability
#   stop           stop the node started by this script
#   status         report the node and the latest seed connection evidence
#
#   --require-seed  return 1 from start/all unless the node logs a successful
#                   seed handshake before the wait period expires
#
# Environment (all optional):
#   CAIRN_VERSION       release version, with or without the leading v
#   CAIRN_PREFIX        state and install root (default: ~/.cairn)
#   CAIRN_LISTEN        p2p address (default: 127.0.0.1:9000)
#   CAIRN_SERVE         HTTP address (default: 127.0.0.1:8080)
#   CAIRN_SEEDS_URL     published seed list (default: the Pages copy)
#   CAIRN_FALLBACK_SEED address used only for a TCP preflight if the list
#                       cannot be fetched (default: the address in Makefile)
#   CAIRN_LINK           0 = do not symlink into /usr/local/bin
#
# The node is started with `run --no-mcp`. A background process must not have
# its MCP stdin connected to /dev/null: the embedded MCP server treats EOF as
# a request to stop the combined node. HTTP, p2p, and seed discovery remain
# enabled.
set -euo pipefail

: "${HOME:?HOME must be set}"

PREFIX=${CAIRN_PREFIX:-$HOME/.cairn}
LISTEN=${CAIRN_LISTEN:-127.0.0.1:9000}
SERVE=${CAIRN_SERVE:-127.0.0.1:8080}
SEEDS_URL=${CAIRN_SEEDS_URL:-https://aburan28.github.io/cairn/seeds.json}
FALLBACK_SEED=${CAIRN_FALLBACK_SEED:-44.229.170.164:5000}
REPO=aburan28/distributed-researcher

BIN=$PREFIX/bin/cairn
DATA=$PREFIX/node
BUNDLE=$PREFIX/bundle
# `identity` is a submitter-signing identity, not a node transport identity.
# The daemon creates the latter itself when this file is absent.
IDENTITY=$DATA/peer.identity.json
ROOT_KEY=$DATA/root.key
CHECKPOINT=$DATA/checkpoint.json
PIDFILE=$DATA/node.pid
LOGFILE=$DATA/node.log
SEED_LIST=$DATA/seeds.json
VERSION_FILE=$PREFIX/.cairn-version

MODE=all
REQUIRE_SEED=0
for arg in "$@"; do
  case "$arg" in
    all|install|start|stop|status) MODE=$arg ;;
    --require-seed) REQUIRE_SEED=1 ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "unknown argument: $arg (try --help)" >&2; exit 2 ;;
  esac
done

say()  { printf '  %s\n' "$*"; }
rule() { printf '\n== %s\n' "$*"; }
warn() { printf '  WARNING: %s\n' "$*" >&2; }
die()  { printf 'cairn-cloud-setup: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

WORK=
cleanup() {
  if [ -n "${WORK:-}" ] && [ -d "$WORK" ]; then
    rm -rf "$WORK"
  fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------- install ---

latest_version() {
  local url tag
  url=$(curl -fsSL --proto '=https' --max-time 30 -o /dev/null \
    -w '%{url_effective}' "https://github.com/$REPO/releases/latest") || return 1
  tag=${url##*/tag/}
  tag=${tag#v}
  [[ $tag =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]] || return 1
  printf '%s\n' "$tag"
}

sha256_file() {
  if have sha256sum; then
    sha256sum "$1" | awk '{print $1}'
  elif have shasum; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    return 1
  fi
}

installed_version_matches() {
  local wanted=$1 output
  [ -x "$BIN" ] || return 1
  [ -f "$VERSION_FILE" ] || return 1
  [ "$(cat "$VERSION_FILE")" = "$wanted" ] || return 1
  # The released CLI has no --version command. `--help` is the executable
  # smoke test and avoids treating a stale marker as a working installation.
  output=$("$BIN" --help 2>&1) || return 1
  grep -q 'cairn' <<<"$output"
}

install_cairn() {
  rule "install"
  have curl || die "curl is required"
  have tar || die "tar is required"
  sha256_file /dev/null >/dev/null 2>&1 || die "sha256sum or shasum is required"

  local arch target ver tag asset base want got
  case "$(uname -m)" in
    x86_64|amd64) arch=x86_64 ;;
    aarch64|arm64) arch=aarch64 ;;
    *) die "unsupported CPU: $(uname -m)" ;;
  esac
  [ "$(uname -s)" = Linux ] || die "this script is for Linux workspaces ($(uname -s) found)"
  target=$arch-unknown-linux-musl

  ver=${CAIRN_VERSION:-}
  if [ -z "$ver" ]; then
    ver=$(latest_version) || die "could not read the latest release; set CAIRN_VERSION=x.y.z"
  fi
  tag=${ver#v}
  [[ $tag =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]] \
    || die "invalid CAIRN_VERSION: $ver"

  if installed_version_matches "$tag"; then
    say "cairn $tag already installed at $BIN"
  else
    WORK=$(mktemp -d "${TMPDIR:-/tmp}/cairn-install.XXXXXX")
    asset=cairn-v$tag-$target.tar.gz
    base=https://github.com/$REPO/releases/download/v$tag
    say "downloading $asset"
    curl -fsSL --proto '=https' --max-time 300 \
      -o "$WORK/$asset" "$base/$asset" \
      || die "download failed: $base/$asset"
    curl -fsSL --proto '=https' --max-time 60 \
      -o "$WORK/$asset.sha256" "$base/$asset.sha256" \
      || die "checksum download failed"

    want=$(awk 'NF { print $1; exit }' "$WORK/$asset.sha256")
    got=$(sha256_file "$WORK/$asset") \
      || die "neither sha256sum nor shasum is available"
    [ -n "$want" ] && [ "$got" = "$want" ] \
      || die "checksum mismatch for $asset"
    say "sha256 ok"

    tar -xzf "$WORK/$asset" -C "$WORK"
    [ -f "$WORK/cairn" ] || die "release archive does not contain cairn"
    mkdir -p "$PREFIX/bin"
    cp "$WORK/cairn" "$BIN.new.$$"
    chmod 0755 "$BIN.new.$$"
    mv -f "$BIN.new.$$" "$BIN"
    printf '%s\n' "$tag" >"$VERSION_FILE.new.$$"
    mv -f "$VERSION_FILE.new.$$" "$VERSION_FILE"
    say "installed cairn $tag at $BIN"
  fi

  if [ "${CAIRN_LINK:-1}" = 1 ] && [ -w /usr/local/bin ]; then
    ln -sf "$BIN" /usr/local/bin/cairn
    say "linked /usr/local/bin/cairn"
  else
    say "add to PATH: export PATH=\"$PREFIX/bin:\$PATH\""
  fi

  # The source bundle must match the binary tag. Verifier paths are resolved
  # under --root, so a missing bundle makes every pinned checker unavailable.
  fetch_bundle "$tag"
}

fetch_bundle() {
  local tag=$1 archive new_bundle
  mkdir -p "$PREFIX"
  if [ -d "$BUNDLE/examples" ]; then
    say "bundle present: $BUNDLE"
    return 0
  fi

  have curl || { warn "curl is required to fetch the verifier bundle"; return 0; }
  archive=${WORK:-$(mktemp -d "${TMPDIR:-/tmp}/cairn-bundle.XXXXXX")}/source.tar.gz
  new_bundle=$(mktemp -d "${TMPDIR:-/tmp}/cairn-bundle-extract.XXXXXX")
  say "downloading verifier bundle for v$tag"
  if curl -fsSL --proto '=https' --max-time 300 \
       -o "$archive" "https://github.com/$REPO/archive/refs/tags/v$tag.tar.gz" \
       && tar -xzf "$archive" -C "$new_bundle" --strip-components=1 \
       && [ -d "$new_bundle/examples" ]; then
    if [ -e "$BUNDLE" ]; then
      mv "$BUNDLE" "$BUNDLE.incomplete.$$"
    fi
    mv "$new_bundle" "$BUNDLE"
    say "bundle fetched into $BUNDLE"
  else
    warn "bundle fetch failed; claims will answer unavailable until $BUNDLE holds the repository"
    rm -rf "$new_bundle"
  fi
}

# ---------------------------------------------------------------- lifecycle -

pid_value() {
  [ -r "$PIDFILE" ] || return 1
  awk 'NR == 1 { print $1; exit }' "$PIDFILE"
}

pid_is_running() {
  local pid=${1:-}
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null
}

pid_is_ours() {
  local pid=${1:-} command
  pid_is_running "$pid" || return 1
  command=$(ps -p "$pid" -o command= 2>/dev/null || true)
  [[ "$command" == *"$BIN"* ]] && [[ "$command" == *" run"* || "$command" == *" run "* ]]
}

fetch_seed_list() {
  local tmp
  mkdir -p "$DATA"
  if ! have curl; then
    warn "curl is unavailable; using the seed list embedded in the binary"
    return 0
  fi
  tmp=$(mktemp "$DATA/seeds.json.XXXXXX")
  if ! curl -fsSL --proto '=https,file' --max-time 30 -o "$tmp" "$SEEDS_URL"; then
    rm -f "$tmp"
    warn "could not fetch $SEEDS_URL; using the seed list embedded in the binary"
    return 0
  fi
  if ! grep -Eq '"seeds"[[:space:]]*:' "$tmp"; then
    rm -f "$tmp"
    warn "seed list from $SEEDS_URL has no seeds array; using the embedded list"
    return 0
  fi
  mv -f "$tmp" "$SEED_LIST"
  say "using published seed list: $SEEDS_URL"
}

seed_addresses() {
  # This is diagnostic only. The Cairn binary parses and authenticates the
  # list; this extraction is never used as an identity or trust decision.
  if have python3 && [ -f "$SEED_LIST" ]; then
    python3 - "$SEED_LIST" <<'PY'
import json
import sys

try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, ValueError):
    raise SystemExit(0)
for seed in data.get("seeds", []):
    addr = seed.get("addr")
    if isinstance(addr, str) and addr:
        print(addr)
PY
  else
    printf '%s\n' "$FALLBACK_SEED"
  fi
}

tcp_probe() {
  local endpoint=$1 host port
  if [[ "$endpoint" == \[*\]:* ]]; then
    host=${endpoint%%\]*}; host=${host#\[}; port=${endpoint##*\]:}
  elif [[ "$endpoint" == *:* ]]; then
    host=${endpoint%:*}; port=${endpoint##*:}
  else
    return 2
  fi
  have python3 || return 2
  python3 - "$host" "$port" <<'PY'
import socket
import sys

try:
    with socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=3):
        pass
except OSError:
    raise SystemExit(1)
PY
}

preflight_seeds() {
  local addr
  while read -r addr; do
    [ -n "$addr" ] || continue
    if tcp_probe "$addr"; then
      say "seed TCP port reachable: $addr"
    else
      case $? in
        2) warn "cannot preflight $addr (python3 unavailable or invalid address)" ;;
        *) warn "seed TCP port not reachable from this workspace: $addr" ;;
      esac
    fi
  done < <(seed_addresses)
}

seed_log_line() {
  [ -f "$LOGFILE" ] || return 0
  grep -E 'seeds: .* (answered at|did not hand over|is outside|is neither)' "$LOGFILE" \
    | tail -1 || true
}

seed_answered() {
  [ -f "$LOGFILE" ] && grep -Eq 'seeds: .* answered at' "$LOGFILE"
}

wait_for_seed() {
  local seconds=${1:-20} i
  for ((i = 0; i < seconds; i++)); do
    seed_answered && return 0
    sleep 1
  done
  return 1
}

start_node() {
  rule "start"
  mkdir -p "$DATA"
  if [ -f "$PIDFILE" ]; then
    local old_pid
    old_pid=$(pid_value || true)
    if pid_is_ours "$old_pid"; then
      say "cairn already running (pid $old_pid)"
    else
      rm -f "$PIDFILE"
    fi
  fi

  if [ ! -x "$BIN" ]; then
    die "cairn is not installed at $BIN; run $0 install first"
  fi
  fetch_seed_list
  preflight_seeds

  # Keep the node transport identity separate from the submitter identity
  # created by `cairn identity`. The daemon generates this file on first start.
  local pid
  if [ ! -f "$PIDFILE" ]; then
    if [ -f "$SEED_LIST" ]; then
      CAIRN_SEEDS="$SEED_LIST" nohup "$BIN" --data-dir "$DATA" --root "$BUNDLE" run \
        --identity "$IDENTITY" --root-key "$ROOT_KEY" --checkpoint "$CHECKPOINT" \
        --listen "$LISTEN" --serve "$SERVE" --no-mcp \
        </dev/null >>"$LOGFILE" 2>&1 &
    else
      nohup "$BIN" --data-dir "$DATA" --root "$BUNDLE" run \
        --identity "$IDENTITY" --root-key "$ROOT_KEY" --checkpoint "$CHECKPOINT" \
        --listen "$LISTEN" --serve "$SERVE" --no-mcp \
        </dev/null >>"$LOGFILE" 2>&1 &
    fi
    pid=$!
    printf '%s\n' "$pid" >"$PIDFILE"
    say "started cairn (pid $pid)"
    sleep 1
    if ! pid_is_running "$pid"; then
      warn "cairn exited during startup; recent log:"
      tail -20 "$LOGFILE" >&2 || true
      return 1
    fi
  fi

  if wait_for_seed 20; then
    say "seed handshake succeeded"
  else
    warn "no successful seed handshake was logged within 20 seconds"
    seed_log_line | sed 's/^/  /' || true
    [ "$REQUIRE_SEED" = 1 ] && return 1
  fi
  say "node log: $LOGFILE"
  say "HTTP: http://$SERVE/"
}

stop_node() {
  rule "stop"
  local pid
  pid=$(pid_value || true)
  if [ -z "$pid" ]; then
    say "cairn is not running"
    return 0
  fi
  if ! pid_is_running "$pid"; then
    rm -f "$PIDFILE"
    say "removed stale pid file"
    return 0
  fi
  if ! pid_is_ours "$pid"; then
    die "pid $pid is not the Cairn process recorded by $PIDFILE; refusing to signal it"
  fi
  kill -TERM "$pid"
  local i
  for ((i = 0; i < 10; i++)); do
    pid_is_running "$pid" || break
    sleep 1
  done
  if pid_is_running "$pid"; then
    warn "pid $pid did not stop after 10 seconds; leaving it running"
    return 1
  fi
  rm -f "$PIDFILE"
  say "stopped cairn"
}

status_node() {
  rule "status"
  local pid
  pid=$(pid_value || true)
  if [ -n "$pid" ] && pid_is_ours "$pid"; then
    say "running (pid $pid)"
  elif [ -n "$pid" ] && pid_is_running "$pid"; then
    say "pid file points to another process (pid $pid)"
  else
    say "not running"
  fi
  say "binary: $BIN"
  say "data:   $DATA"
  say "listen: $LISTEN"
  say "serve:  $SERVE"
  if [ -f "$LOGFILE" ]; then
    say "latest seed evidence:"
    seed_log_line | sed 's/^/  /' || say "none yet"
  fi
}

case "$MODE" in
  install) install_cairn ;;
  start) start_node ;;
  stop) stop_node ;;
  status) status_node ;;
  all) install_cairn; start_node ;;
esac
