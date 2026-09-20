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
{{- if lt (int .Values.publisher.replicaCount) 1 -}}
{{- fail "publisher.replicaCount must be at least 1" -}}
{{- end -}}
{{- if lt (int .Values.consumer.replicaCount) 1 -}}
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
{{- if and (not .Values.existingSecret.runtimeDatabaseUrlKey) (not .Values.rds.host) -}}
{{- fail "set rds.host or existingSecret.runtimeDatabaseUrlKey" -}}
{{- end -}}
{{- if and .Values.migration.enabled (not .Values.existingSecret.migrationDatabaseUrlKey) -}}
{{- fail "existingSecret.migrationDatabaseUrlKey is required when migration.enabled=true" -}}
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
