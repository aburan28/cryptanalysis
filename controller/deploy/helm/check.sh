#!/usr/bin/env bash
# Lint and render the operator chart, validate the manifests and the CRD
# with kubeconform when available, and prove unsafe values are rejected.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chart="$here/cryptanalysis-operator"
kube_version="${KUBECONFORM_KUBERNETES_VERSION:-1.30.0}"

render() {
  helm template operator "$chart" --namespace cryptanalysis-system --include-crds "$@"
}

validate() {
  local name=$1
  shift
  local out
  out=$(mktemp)
  render "$@" >"$out"
  local count crds
  count=$(grep -c '^kind: ' "$out")
  crds=$(grep -c '^kind: CustomResourceDefinition' "$out" || true)
  if command -v kubeconform >/dev/null 2>&1; then
    # The public schema set has no CustomResourceDefinition schema; the CRD
    # is validated by the apiserver validation package in `go test` instead.
    local summary
    summary=$(kubeconform -strict -summary -kubernetes-version "$kube_version" \
      -schema-location default -skip CustomResourceDefinition <"$out" || true)
    echo "$summary"
    if ! grep -q "Valid: $((count - crds)), Invalid: 0, Errors: 0, Skipped: $crds" <<<"$summary"; then
      echo "kubeconform did not validate all $((count - crds)) resources for $name" >&2
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
validate "default"
validate "namespaced" --set watchNamespace=cryptanalysis
validate "two replicas" --set replicaCount=2
validate "metrics disabled" --set metrics.enabled=false --set metrics.service.enabled=false
expect_failure "replicas without leader election" --set replicaCount=2 --set leaderElection=false
expect_failure "bad watch namespace" --set watchNamespace=Not_Valid
expect_failure "bad log level" --set logLevel=trace

echo "operator chart checks passed"
