{{- define "ecc2k130-coordinator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ecc2k130-coordinator.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "ecc2k130-coordinator.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "ecc2k130-coordinator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ecc2k130-coordinator.labels" -}}
helm.sh/chart: {{ include "ecc2k130-coordinator.chart" . }}
app.kubernetes.io/name: {{ include "ecc2k130-coordinator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: cryptanalysis
{{- end -}}

{{- define "ecc2k130-coordinator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ecc2k130-coordinator.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "ecc2k130-coordinator.image" -}}
{{- if .Values.image.digest -}}
{{- printf "%s@%s" .Values.image.repository .Values.image.digest -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository (default .Chart.AppVersion .Values.image.tag) -}}
{{- end -}}
{{- end -}}

{{- define "ecc2k130-coordinator.secretName" -}}
{{- required "existingSecret.name is required" .Values.existingSecret.name -}}
{{- end -}}

{{- define "ecc2k130-coordinator.serviceAccountName" -}}
{{- $root := .root -}}
{{- $component := .component -}}
{{- $account := index $root.Values.serviceAccounts $component -}}
{{- if $account.create -}}
{{- default (printf "%s-%s" (include "ecc2k130-coordinator.fullname" $root) $component) $account.name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- required (printf "serviceAccounts.%s.name is required when create=false" $component) $account.name -}}
{{- end -}}
{{- end -}}

{{/*
Whether a component is part of this release. The publisher always is.
Usage: include "ecc2k130-coordinator.componentEnabled" (dict "root" $ "component" "consumer")
*/}}
{{- define "ecc2k130-coordinator.componentEnabled" -}}
{{- if eq .component "publisher" -}}true
{{- else if and (eq .component "consumer") .root.Values.consumer.enabled -}}true
{{- else if and (eq .component "reconciler") .root.Values.reconciler.enabled -}}true
{{- end -}}
{{- end -}}

{{/*
Identity modes that federate a projected Kubernetes token into AWS IAM
directly, without the EKS pod identity webhook.
*/}}
{{- define "ecc2k130-coordinator.federatedIdentity" -}}
{{- if has .Values.identity.mode (list "gke" "web-identity") -}}true{{- end -}}
{{- end -}}

{{/*
Complete annotation map for a component's ServiceAccount: mode-specific
identity bindings merged over the verbatim serviceAccounts.<component>.annotations.
Usage: include "ecc2k130-coordinator.serviceAccountAnnotations" (dict "root" $ "component" "publisher")
*/}}
{{- define "ecc2k130-coordinator.serviceAccountAnnotations" -}}
{{- $root := .root -}}
{{- $account := index $root.Values.serviceAccounts .component -}}
{{- $annotations := merge (dict) $account.annotations -}}
{{- if and (eq $root.Values.identity.mode "irsa") $account.awsRoleArn -}}
{{- $_ := set $annotations "eks.amazonaws.com/role-arn" $account.awsRoleArn -}}
{{- $_ := set $annotations "eks.amazonaws.com/audience" $root.Values.identity.aws.audience -}}
{{- $_ := set $annotations "eks.amazonaws.com/token-expiration" (toString $root.Values.identity.aws.tokenExpirationSeconds) -}}
{{- $_ := set $annotations "eks.amazonaws.com/sts-regional-endpoints" (ternary "true" "false" $root.Values.identity.aws.stsRegionalEndpoints) -}}
{{- end -}}
{{- if and (eq $root.Values.identity.mode "gke") $account.gcpServiceAccount -}}
{{- $_ := set $annotations "iam.gke.io/gcp-service-account" $account.gcpServiceAccount -}}
{{- end -}}
{{- toYaml $annotations -}}
{{- end -}}

{{/*
AWS SDK environment for federated identity modes. boto3 reads the projected
token and calls sts:AssumeRoleWithWebIdentity itself, refreshing as needed.
*/}}
{{- define "ecc2k130-coordinator.identityEnv" -}}
{{- $root := .root -}}
{{- $account := index $root.Values.serviceAccounts .component -}}
{{- if and (include "ecc2k130-coordinator.federatedIdentity" $root) $account.awsRoleArn -}}
- name: AWS_ROLE_ARN
  value: {{ $account.awsRoleArn | quote }}
- name: AWS_WEB_IDENTITY_TOKEN_FILE
  value: {{ printf "%s/token" $root.Values.identity.aws.tokenMountPath | quote }}
- name: AWS_ROLE_SESSION_NAME
  value: {{ printf "%s-%s" (include "ecc2k130-coordinator.fullname" $root) .component | trunc 64 | trimSuffix "-" | quote }}
{{- if $root.Values.identity.aws.stsRegionalEndpoints }}
- name: AWS_STS_REGIONAL_ENDPOINTS
  value: regional
{{- end }}
{{- end }}
{{- end -}}

{{- define "ecc2k130-coordinator.identityVolume" -}}
{{- if include "ecc2k130-coordinator.federatedIdentity" . -}}
- name: aws-web-identity-token
  projected:
    sources:
      - serviceAccountToken:
          audience: {{ .Values.identity.aws.audience | quote }}
          expirationSeconds: {{ .Values.identity.aws.tokenExpirationSeconds }}
          path: token
{{- end }}
{{- end -}}

{{- define "ecc2k130-coordinator.identityVolumeMount" -}}
{{- if include "ecc2k130-coordinator.federatedIdentity" . -}}
- name: aws-web-identity-token
  mountPath: {{ .Values.identity.aws.tokenMountPath }}
  readOnly: true
{{- end }}
{{- end -}}

{{/*
Node selector for a workload: the user's selector plus the GKE metadata server
pin when Workload Identity is in use.
Usage: include "ecc2k130-coordinator.nodeSelector" (dict "root" $ "component" "publisher")
*/}}
{{- define "ecc2k130-coordinator.nodeSelector" -}}
{{- $root := .root -}}
{{- $workload := index $root.Values .component -}}
{{- $selector := dict -}}
{{- range $key, $value := $workload.nodeSelector -}}
{{- /* Label values must be strings; --set and YAML booleans would be rejected by the API. */ -}}
{{- $_ := set $selector $key (toString $value) -}}
{{- end -}}
{{- if and (eq $root.Values.identity.mode "gke") $root.Values.identity.gcp.requireMetadataServer -}}
{{- $_ := set $selector "iam.gke.io/gke-metadata-server-enabled" "true" -}}
{{- end -}}
{{- with $selector -}}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end -}}
{{- end -}}

{{- define "ecc2k130-coordinator.publisherTrafficPolicy" -}}
{{- if .Values.publisher.service.internalTrafficPolicy -}}
{{- .Values.publisher.service.internalTrafficPolicy -}}
{{- else if eq .Values.publisher.kind "DaemonSet" -}}
Local
{{- else -}}
Cluster
{{- end -}}
{{- end -}}

{{- define "ecc2k130-coordinator.producerQueueSecretEnv" -}}
- name: RHO_QUEUE_REDIS_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "ecc2k130-coordinator.secretName" . }}
      key: {{ required "existingSecret.producerRedisUrlKey is required" .Values.existingSecret.producerRedisUrlKey }}
{{- end -}}

{{- define "ecc2k130-coordinator.consumerQueueSecretEnv" -}}
- name: RHO_QUEUE_REDIS_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "ecc2k130-coordinator.secretName" . }}
      key: {{ required "existingSecret.consumerRedisUrlKey is required" .Values.existingSecret.consumerRedisUrlKey }}
{{- end -}}

{{- define "ecc2k130-coordinator.databaseSecretEnv" -}}
{{- if .Values.existingSecret.runtimeDatabaseUrlKey }}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "ecc2k130-coordinator.secretName" . }}
      key: {{ .Values.existingSecret.runtimeDatabaseUrlKey }}
{{- end }}
{{- end -}}

{{- define "ecc2k130-coordinator.migrationDatabaseSecretEnv" -}}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "ecc2k130-coordinator.secretName" . }}
      key: {{ required "existingSecret.migrationDatabaseUrlKey is required when migration.enabled=true" .Values.existingSecret.migrationDatabaseUrlKey }}
{{- end -}}

{{- define "ecc2k130-coordinator.secretEnv" -}}
{{ include "ecc2k130-coordinator.consumerQueueSecretEnv" . }}
{{ include "ecc2k130-coordinator.databaseSecretEnv" . }}
{{- end -}}

{{- define "ecc2k130-coordinator.validate" -}}
{{- $secret := include "ecc2k130-coordinator.secretName" . -}}
{{- if ne .Values.queue.backend "memorydb" -}}
{{- fail "queue.backend must be memorydb in the production Helm chart" -}}
{{- end -}}
{{- if not .Values.queue.cluster -}}
{{- fail "queue.cluster must be true for AWS MemoryDB" -}}
{{- end -}}
{{- if and (eq .Values.publisher.kind "Deployment") (lt (int .Values.publisher.replicaCount) 1) -}}
{{- fail "publisher.replicaCount must be at least 1" -}}
{{- end -}}
{{- if and (ne .Values.publisher.kind "DaemonSet") (gt (int .Values.publisher.hostPort) 0) -}}
{{- fail "publisher.hostPort requires publisher.kind=DaemonSet" -}}
{{- end -}}
{{- if and (gt (int .Values.publisher.hostPort) 0) (ne (toString (dig "rollingUpdate" "maxSurge" 0 .Values.publisher.daemonSet.updateStrategy)) "0") -}}
{{- fail "publisher.daemonSet.updateStrategy.rollingUpdate.maxSurge must be 0 when publisher.hostPort is set" -}}
{{- end -}}
{{- $mode := .Values.identity.mode -}}
{{- $federated := include "ecc2k130-coordinator.federatedIdentity" . -}}
{{- range $component := list "publisher" "consumer" "reconciler" -}}
{{- $account := index $.Values.serviceAccounts $component -}}
{{- $active := include "ecc2k130-coordinator.componentEnabled" (dict "root" $ "component" $component) -}}
{{- if and (eq $mode "none") (or $account.awsRoleArn $account.gcpServiceAccount) -}}
{{- fail (printf "serviceAccounts.%s sets a cloud identity but identity.mode is none" $component) -}}
{{- end -}}
{{- if and (ne $mode "gke") $account.gcpServiceAccount -}}
{{- fail (printf "serviceAccounts.%s.gcpServiceAccount requires identity.mode=gke" $component) -}}
{{- end -}}
{{- if and $federated $active (not $account.awsRoleArn) -}}
{{- fail (printf "serviceAccounts.%s.awsRoleArn is required in identity.mode=%s: the coordinator's data plane is AWS and the projected token has no role to assume" $component $mode) -}}
{{- end -}}
{{- end -}}
{{- if and $federated (not (hasKey .Values.podSecurityContext "fsGroup")) -}}
{{- fail "podSecurityContext.fsGroup is required so the non-root containers can read the projected AWS token" -}}
{{- end -}}
{{- if and .Values.consumer.enabled (lt (int .Values.consumer.replicaCount) 1) -}}
{{- fail "consumer.replicaCount must be at least 1" -}}
{{- end -}}
{{- if ge (int64 .Values.queue.highMessages) (int64 .Values.queue.criticalMessages) -}}
{{- fail "queue.highMessages must be less than queue.criticalMessages" -}}
{{- end -}}
{{- if ge (int64 .Values.queue.highBytes) (int64 .Values.queue.criticalBytes) -}}
{{- fail "queue.highBytes must be less than queue.criticalBytes" -}}
{{- end -}}
{{- if ge (int64 .Values.queue.highAgeSeconds) (int64 .Values.queue.criticalAgeSeconds) -}}
{{- fail "queue.highAgeSeconds must be less than queue.criticalAgeSeconds" -}}
{{- end -}}
{{- if ge (float64 .Values.queue.highMemoryRatio) (float64 .Values.queue.criticalMemoryRatio) -}}
{{- fail "queue.highMemoryRatio must be less than queue.criticalMemoryRatio" -}}
{{- end -}}
{{- $needsDatabase := or .Values.consumer.enabled .Values.reconciler.enabled -}}
{{- $runsMigration := and .Values.migration.enabled (or .Values.consumer.enabled (and .Values.reconciler.enabled .Values.migration.runOnReconciler)) -}}
{{- if and $needsDatabase (not .Values.existingSecret.runtimeDatabaseUrlKey) (not .Values.rds.host) -}}
{{- fail "set rds.host or existingSecret.runtimeDatabaseUrlKey" -}}
{{- end -}}
{{- if and .Values.consumer.enabled (not .Values.existingSecret.consumerRedisUrlKey) -}}
{{- fail "existingSecret.consumerRedisUrlKey is required when consumer.enabled=true" -}}
{{- end -}}
{{- if and $runsMigration (not .Values.existingSecret.migrationDatabaseUrlKey) -}}
{{- fail "existingSecret.migrationDatabaseUrlKey is required when the migration init container runs" -}}
{{- end -}}
{{- range $component := list "publisher" "consumer" -}}
{{- $workload := index $.Values $component -}}
{{- range $label := list "app.kubernetes.io/name" "app.kubernetes.io/instance" "app.kubernetes.io/component" -}}
{{- if hasKey $workload.podLabels $label -}}
{{- fail (printf "%s.podLabels may not override reserved label %s" $component $label) -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}
