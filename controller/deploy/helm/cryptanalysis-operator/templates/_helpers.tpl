{{- define "cryptanalysis-operator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "cryptanalysis-operator.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "cryptanalysis-operator.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "cryptanalysis-operator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "cryptanalysis-operator.labels" -}}
helm.sh/chart: {{ include "cryptanalysis-operator.chart" . }}
app.kubernetes.io/name: {{ include "cryptanalysis-operator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: cryptanalysis
app.kubernetes.io/component: campaign-controller
{{- end -}}

{{- define "cryptanalysis-operator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "cryptanalysis-operator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "cryptanalysis-operator.image" -}}
{{- if .Values.image.digest -}}
{{- printf "%s@%s" .Values.image.repository .Values.image.digest -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository (default .Chart.AppVersion .Values.image.tag) -}}
{{- end -}}
{{- end -}}

{{- define "cryptanalysis-operator.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "cryptanalysis-operator.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- required "serviceAccount.name is required when serviceAccount.create=false" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/* Rules shared by the cluster-wide and namespaced roles. */}}
{{- define "cryptanalysis-operator.rules" -}}
- apiGroups: ["cryptanalysis.io"]
  resources: ["campaigns"]
  verbs: ["get", "list", "watch", "update", "patch"]
- apiGroups: ["cryptanalysis.io"]
  resources: ["campaigns/status"]
  verbs: ["get", "update", "patch"]
- apiGroups: ["cryptanalysis.io"]
  resources: ["campaigns/finalizers"]
  verbs: ["update"]
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: [""]
  resources: ["events"]
  verbs: ["create", "patch"]
{{- end -}}

{{- define "cryptanalysis-operator.validate" -}}
{{- if and (gt (int .Values.replicaCount) 1) (not .Values.leaderElection) -}}
{{- fail "leaderElection must be true when replicaCount > 1" -}}
{{- end -}}
{{- end -}}
