{{/* Name helpers, the usual shape. */}}
{{- define "ca-coordinator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ca-coordinator.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "ca-coordinator.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "ca-coordinator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: cryptanalysis
{{- end -}}

{{- define "ca-coordinator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ca-coordinator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: coordinator
{{- end -}}

{{- define "ca-coordinator.agentSelectorLabels" -}}
app.kubernetes.io/name: {{ include "ca-coordinator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: agent
{{- end -}}

{{- define "ca-coordinator.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "ca-coordinator.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/* Where the job document comes from: a ConfigMap you brought, or ours. */}}
{{- define "ca-coordinator.jobConfigMap" -}}
{{- if .Values.job.existingConfigMap -}}
{{- .Values.job.existingConfigMap -}}
{{- else -}}
{{- printf "%s-job" (include "ca-coordinator.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "ca-coordinator.tokenSecret" -}}
{{- if .Values.auth.existingSecret -}}
{{- .Values.auth.existingSecret -}}
{{- else -}}
{{- printf "%s-token" (include "ca-coordinator.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "ca-coordinator.hasToken" -}}
{{- if or .Values.auth.token .Values.auth.existingSecret -}}true{{- end -}}
{{- end -}}

{{/* The URL agents inside the cluster dial. */}}
{{- define "ca-coordinator.internalURL" -}}
{{- printf "http://%s.%s.svc:%d" (include "ca-coordinator.fullname" .) .Release.Namespace (int .Values.service.port) -}}
{{- end -}}

{{- define "ca-coordinator.coordinatorImage" -}}
{{- printf "%s:%s" .Values.coordinator.image.repository (default .Chart.AppVersion .Values.coordinator.image.tag) -}}
{{- end -}}

{{- define "ca-coordinator.agentImage" -}}
{{- printf "%s:%s" .Values.agents.image.repository (default .Chart.AppVersion .Values.agents.image.tag) -}}
{{- end -}}

{{/*
Refuse configurations that cannot work, at template time rather than at
3 a.m.:
  * no job document at all;
  * more than one coordinator replica, which would split the
    distinguished-point table and miss every collision spanning the two;
  * auth.required with nothing to require.
*/}}
{{- define "ca-coordinator.validate" -}}
{{- if and (not .Values.job.document) (not .Values.job.existingConfigMap) -}}
{{- fail "ca-coordinator: set job.document to the line `ca coord-job` printed, or job.existingConfigMap to a ConfigMap holding one" -}}
{{- end -}}
{{- if ne (int .Values.coordinator.replicaCount) 1 -}}
{{- fail "ca-coordinator: the coordinator holds the shared distinguished-point table in memory, so exactly one replica is correct; two would each hold half of it and miss the collisions that span them" -}}
{{- end -}}
{{- if and .Values.auth.required (not (include "ca-coordinator.hasToken" .)) -}}
{{- fail "ca-coordinator: auth.required is set but no token was given; set auth.token, auth.existingSecret, or auth.required=false" -}}
{{- end -}}
{{- end -}}
