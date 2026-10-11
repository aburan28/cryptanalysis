#!/usr/bin/env bash
set -euo pipefail

# Plain CUDA bases do not include RunPod's /start.sh.  Reproduce the small
# SSH bootstrap needed for pod access, then hand PID 1 to the ECC entrypoint.
if [[ -n "${PUBLIC_KEY:-}" ]]; then
    install -d -m 700 /root/.ssh
    printf '%s\n' "${PUBLIC_KEY}" > /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
fi

ssh-keygen -A >/dev/null 2>&1
/usr/sbin/sshd
if [[ -n "${ECC_START_COMMAND:-}" ]]; then
    exec /opt/ecc2k130/deploy/entrypoint.sh bash -lc "${ECC_START_COMMAND}"
fi
exec /opt/ecc2k130/deploy/entrypoint.sh "$@"
