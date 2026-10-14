#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: remote_agent_runner.sh SSH_ALIAS {check|codex|claude|worker} [CLI_ARGS...]

Set REMOTE_AGENT_WORKDIR to the repository path on the remote host.
SSH_ALIAS must be a Host entry in your SSH config. The launcher never copies
local CLI credentials to the remote host.
USAGE
  exit 2
}

(( $# >= 2 )) || usage
target=$1
mode=$2
shift 2

[[ $target =~ ^[A-Za-z0-9._-]+$ ]] || usage
remote_dir=${REMOTE_AGENT_WORKDIR:-/workspace/cryptanalysis}
[[ $remote_dir = /* ]] || { echo 'REMOTE_AGENT_WORKDIR must be absolute' >&2; exit 2; }

case $mode in
  check)
    (( $# == 0 )) || usage
    ssh -T "$target" 'export PATH="$HOME/.local/bin:$PATH"; printf "host: "; hostname; printf "codex: "; command -v codex || true; printf "claude: "; command -v claude || true; printf "conductor: "; command -v conductor || true; printf "git: "; command -v git || true'
    ;;
  codex|claude|worker)
    printf -v quoted_dir '%q' "$remote_dir"
    if [[ $mode == worker ]]; then
      remote_command="export PATH=\"\$HOME/.local/bin:\$PATH\"; cd $quoted_dir && command -v conductor >/dev/null && exec conductor worker --repo $quoted_dir"
    else
      remote_command="export PATH=\"\$HOME/.local/bin:\$PATH\"; cd $quoted_dir && command -v conductor >/dev/null && exec conductor wrap $mode"
    fi
    for arg in "$@"; do
      printf -v quoted_arg '%q' "$arg"
      remote_command+=" $quoted_arg"
    done
    ssh -tt "$target" "$remote_command"
    ;;
  *) usage ;;
esac
