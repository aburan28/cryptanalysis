#!/bin/bash
# EC2 user data for an agent instance.
#
# Pass the control plane's address and the token through instance tags or
# Secrets Manager rather than pasting them here: user data is readable by
# anything on the instance that can reach the metadata service, and by
# anybody with ec2:DescribeInstanceAttribute.
#
#   aws ec2 run-instances --user-data file://ec2-user-data.sh \
#       --key-name meow34 --instance-type c7i.8xlarge ...
#
# The instance is deliberately disposable: agents hold no state, a spot
# reclaim costs the unit in flight, and that unit goes back in the queue.
set -euxo pipefail

CONTROL_URL="${CONTROL_URL:-http://control.internal:8080}"
TOKEN_SECRET_ID="${TOKEN_SECRET_ID:-cryptanalysis/agent-token}"
RELEASE_URL="${RELEASE_URL:-}"   # a tarball with ca, ca-agent and the units

exec > >(tee /var/log/ca-bootstrap.log | logger -t ca-bootstrap) 2>&1

# Amazon Linux and Debian both, so one script covers the usual images.
if command -v dnf >/dev/null; then
    dnf install -y tar gzip awscli
elif command -v apt-get >/dev/null; then
    apt-get update && apt-get install -y --no-install-recommends tar gzip awscli ca-certificates
fi

workdir=$(mktemp -d)
cd "$workdir"

if [ -n "$RELEASE_URL" ]; then
    curl -fsSL "$RELEASE_URL" -o release.tar.gz
    tar xzf release.tar.gz
else
    echo "RELEASE_URL is unset: expecting ca, ca-agent and the unit files to be baked into the AMI"
fi

# The token comes from Secrets Manager, not from user data.
TOKEN=$(aws secretsmanager get-secret-value --secret-id "$TOKEN_SECRET_ID" \
        --query SecretString --output text 2>/dev/null || echo "")

./install.sh agent "$(nproc)"

# Write the environment file after the install, which does not overwrite one.
install -m0640 -o ca -g ca /dev/stdin /etc/ca/agent.env <<ENV
CA_SERVER=$CONTROL_URL
CA_BIN=/usr/local/bin/ca
CA_TOKEN=$TOKEN
CA_LOG_LEVEL=info
CA_LABELS=capacity=$(curl -fsS -m1 -H "X-aws-ec2-metadata-token: $(curl -fsS -m1 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' || true)" http://169.254.169.254/latest/meta-data/instance-life-cycle 2>/dev/null || echo unknown)
ENV

systemctl restart 'ca-agent@*' || true

# A spot instance gets a two-minute interruption notice.  Turning that into a
# SIGTERM lets the agent upload the points it has produced and hand its unit
# back, instead of losing both when the instance disappears.
cat >/usr/local/bin/ca-spot-watch <<'WATCH'
#!/bin/sh
# Poll the instance metadata for a spot interruption or a scheduled rebalance
# and stop the agents cleanly when one arrives.
while :; do
    tok=$(curl -fsS -m1 -X PUT http://169.254.169.254/latest/api/token \
              -H 'X-aws-ec2-metadata-token-ttl-seconds: 120' || true)
    if curl -fsS -m1 -H "X-aws-ec2-metadata-token: $tok" \
        http://169.254.169.254/latest/meta-data/spot/instance-action >/dev/null 2>&1; then
        logger -t ca-spot-watch "interruption notice: stopping agents"
        systemctl stop 'ca-agent@*'
        exit 0
    fi
    sleep 5
done
WATCH
chmod 0755 /usr/local/bin/ca-spot-watch

cat >/etc/systemd/system/ca-spot-watch.service <<'UNIT'
[Unit]
Description=Stop cryptanalysis agents on a spot interruption notice
[Service]
Type=exec
ExecStart=/usr/local/bin/ca-spot-watch
Restart=always
RestartSec=10s
[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now ca-spot-watch
echo "agent bootstrap complete"
