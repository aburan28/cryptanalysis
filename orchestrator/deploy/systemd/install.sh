#!/bin/sh
# Install the control plane, the agents, or both, on one host.
#
#   ./install.sh control                  # the control plane only
#   ./install.sh agent 8                  # eight agents
#   ./install.sh both 4
#
# Idempotent: run it again after a new build to replace the binaries and
# restart the services.  Expects ca-control, ca-agent and ca to be in the
# current directory or already in /usr/local/bin.
set -eu

role=${1:-both}
count=${2:-$(nproc 2>/dev/null || echo 2)}
bindir=/usr/local/bin
etc=/etc/ca

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

# A system user with no shell and no home: the services need to read two
# files and write one directory, and nothing about them wants a login.
id ca >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin ca

install -d -m0750 -o ca -g ca "$etc"
for bin in ca ca-control ca-agent; do
    if [ -f "./$bin" ]; then
        install -m0755 "./$bin" "$bindir/$bin"
    elif [ ! -x "$bindir/$bin" ]; then
        echo "missing $bin (build it, or put it in $bindir)" >&2
        exit 1
    fi
done

# Environment files are never overwritten: they hold the token, and an
# install that clobbered it would take the fleet down on an upgrade.
case "$role" in
control|both)
    install -m0644 ca-control.service /etc/systemd/system/
    [ -f "$etc/control.env" ] || install -m0640 -o ca -g ca ca-control.env "$etc/control.env"
    ;;
esac
case "$role" in
agent|both)
    install -m0644 'ca-agent@.service' /etc/systemd/system/
    [ -f "$etc/agent.env" ] || install -m0640 -o ca -g ca ca-agent.env "$etc/agent.env"
    ;;
esac

systemctl daemon-reload

case "$role" in
control|both)
    systemctl enable --now ca-control
    ;;
esac
case "$role" in
agent|both)
    i=0
    while [ "$i" -lt "$count" ]; do
        systemctl enable --now "ca-agent@$i"
        i=$((i + 1))
    done
    ;;
esac

echo "installed: role=$role agents=$count"
echo "edit $etc/*.env (the token and the server URL), then:"
echo "  systemctl restart ca-control 'ca-agent@*'"
