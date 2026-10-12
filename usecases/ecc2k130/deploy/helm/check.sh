#!/usr/bin/env bash
# Lint and render the coordinator chart across the supported identity and
# workload variants, then prove the chart rejects unsafe values. Used by
# `make ecc2k130-helm` and CI. kubeconform is applied when it is on PATH.
set -euo pipefail

chart="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ecc2k130-coordinator"
kube_version="${KUBECONFORM_KUBERNETES_VERSION:-1.30.0}"

roles=(
  --set serviceAccounts.publisher.awsRoleArn=arn:aws:iam::123456789012:role/ecc2k-publisher
  --set serviceAccounts.consumer.awsRoleArn=arn:aws:iam::123456789012:role/ecc2k-consumer
  --set serviceAccounts.reconciler.awsRoleArn=arn:aws:iam::123456789012:role/ecc2k-reconciler
)

render() {
  helm template ecc2k130 "$chart" --namespace cryptanalysis "$@"
}

validate() {
  local name=$1
  shift
  local out
  out=$(mktemp)
  render "$@" >"$out"
  local count
  count=$(grep -c '^kind: ' "$out")
  if command -v kubeconform >/dev/null 2>&1; then
    # kubeconform only opens *.yaml paths, so stream the manifest instead.
    local summary
    summary=$(kubeconform -strict -summary -kubernetes-version "$kube_version" \
      -schema-location default <"$out")
    echo "$summary"
    if ! grep -q "Valid: $count, Invalid: 0, Errors: 0, Skipped: 0" <<<"$summary"; then
      echo "kubeconform did not validate all $count resources for $name" >&2
      exit 1
    fi
  fi
  echo "rendered $name: $count resources"
  rm -f "$out"
}

expect_failure() {
  local reason=$1
  shift
  if render "$@" >/dev/null 2>&1; then
    echo "chart accepted invalid values: $reason" >&2
    exit 1
  fi
  echo "rejected: $reason"
}

helm lint "$chart"

validate "default (irsa, node role fallback)"
validate "irsa with roles" "${roles[@]}"
validate "external DATABASE_URL" \
  --set existingSecret.runtimeDatabaseUrlKey=database-url --set rds.host=
validate "gke" --set identity.mode=gke "${roles[@]}" \
  --set serviceAccounts.publisher.gcpServiceAccount=ecc2k-publisher@example-project.iam.gserviceaccount.com
validate "gke autopilot" --set identity.mode=gke "${roles[@]}" \
  --set identity.gcp.requireMetadataServer=false
validate "web-identity" --set identity.mode=web-identity "${roles[@]}"
validate "identity none" --set identity.mode=none
# --set deliberately yields a boolean here; the chart must coerce it to a label string.
validate "daemonset publisher" --set publisher.kind=DaemonSet \
  --set publisher.hostPort=8080 \
  --set 'publisher.nodeSelector.cryptanalysis\.io/walker-pool=true'
validate "daemonset publisher on gke" --set publisher.kind=DaemonSet \
  --set identity.mode=gke "${roles[@]}"
validate "publisher-only walker cluster" --set consumer.enabled=false \
  --set reconciler.enabled=false --set rds.host= \
  --set existingSecret.consumerRedisUrlKey= \
  --set existingSecret.migrationDatabaseUrlKey= \
  --set identity.mode=web-identity \
  --set serviceAccounts.publisher.awsRoleArn=arn:aws:iam::123456789012:role/ecc2k-publisher

expect_failure "non-durable queue backend" --set queue.backend=standalone
expect_failure "gke without AWS roles" --set identity.mode=gke
expect_failure "web-identity without AWS roles" --set identity.mode=web-identity
expect_failure "identity none with a role" --set identity.mode=none \
  --set serviceAccounts.publisher.awsRoleArn=arn:aws:iam::123456789012:role/x
expect_failure "gcp service account outside gke" \
  --set serviceAccounts.publisher.gcpServiceAccount=ecc2k-publisher@example-project.iam.gserviceaccount.com
expect_failure "malformed role arn" \
  --set serviceAccounts.publisher.awsRoleArn=ecc2k-publisher
expect_failure "misspelled service account key" \
  --set serviceAccounts.publisher.awsRoleARN=arn:aws:iam::123456789012:role/x
expect_failure "unknown identity mode" --set identity.mode=aks
expect_failure "projected token below the Kubernetes minimum" \
  --set identity.aws.tokenExpirationSeconds=300
expect_failure "hostPort on a Deployment" --set publisher.hostPort=8080
expect_failure "hostPort with DaemonSet maxSurge" --set publisher.kind=DaemonSet \
  --set publisher.hostPort=8080 \
  --set publisher.daemonSet.updateStrategy.rollingUpdate.maxSurge=1 \
  --set publisher.daemonSet.updateStrategy.rollingUpdate.maxUnavailable=0
expect_failure "reserved pod label override" \
  --set 'publisher.podLabels.app\.kubernetes\.io/name=other'
expect_failure "consumer without a Redis credential key" \
  --set existingSecret.consumerRedisUrlKey=
expect_failure "migration without a DDL credential key" \
  --set existingSecret.migrationDatabaseUrlKey=

echo "coordinator chart checks passed"
