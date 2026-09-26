#!/usr/bin/env bash
# EC2 user-data for the coordinator instance.
#
# Assumptions, each for a reason stated in README.md:
#   * Amazon Linux 2023 or Ubuntu 24.04, x86_64 or arm64;
#   * the instance role may read the token from Secrets Manager, so the
#     token is never in user-data -- which anything on the box can read
#     back from the instance metadata service;
#   * the job document is in S3 and the role may read it.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/aburan28/cryptanalysis}"
JOB_S3="${JOB_S3:-s3://my-bucket/rho/job.txt}"
TOKEN_SECRET="${TOKEN_SECRET:-ca/coordinator-token}"
REGION="${REGION:-us-east-1}"

# 1. Toolchain and build.  The agent is C (CMake, pthreads); the
#    coordinator is Go and links the same C sources through cgo.
if command -v dnf >/dev/null; then
    dnf install -y git gcc cmake make golang awscli
else
    apt-get update && apt-get install -y git build-essential cmake golang-go awscli curl
fi
git clone --depth 1 "$REPO_URL" /opt/cryptanalysis
cmake -S /opt/cryptanalysis -B /opt/cryptanalysis/build -DCMAKE_BUILD_TYPE=Release
cmake --build /opt/cryptanalysis/build -j"$(nproc)" --target ca
install -m 0755 /opt/cryptanalysis/build/ca /usr/local/bin/ca
( cd /opt/cryptanalysis/bindings/go && CGO_ENABLED=1 go build -o /usr/local/bin/ca-coordinator ./cmd/ca-coordinator )

# 2. Identity and directories.
useradd --system --home /var/lib/ca --create-home ca || true
install -d -o ca -g ca /var/lib/ca
install -d -m 0750 -o root -g ca /etc/ca

# 3. Job and token.  The token goes into a 0640 file the unit reads; it
#    is never an argv value, which `ps` shows to every local user.
aws s3 cp "$JOB_S3" /var/lib/ca/job.txt --region "$REGION"
chown ca:ca /var/lib/ca/job.txt
aws secretsmanager get-secret-value --secret-id "$TOKEN_SECRET" \
    --region "$REGION" --query SecretString --output text > /etc/ca/token
chmod 0640 /etc/ca/token && chown root:ca /etc/ca/token

# 4. Service.
install -m 0644 /opt/cryptanalysis/deploy/ca-coordinator/ca-coordinator.service \
    /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ca-coordinator

# 5. Health: the ALB target group polls /healthz, which needs no token.
curl -fsS http://127.0.0.1:8080/healthz
