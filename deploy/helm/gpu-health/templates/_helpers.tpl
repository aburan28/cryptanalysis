{{/* Name helpers, the usual shape. */}}
{{- define "gpu-health.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "gpu-health.fullname" -}}
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

{{/* A name with a suffix, cut so that the result is a legal DNS label. */}}
{{- define "gpu-health.suffixed" -}}
{{- $top := index . 0 -}}
{{- $suffix := index . 1 -}}
{{- $room := int (sub 62 (len $suffix)) -}}
{{- printf "%s-%s" (include "gpu-health.fullname" $top | trunc $room | trimSuffix "-") $suffix -}}
{{- end -}}

{{- define "gpu-health.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "gpu-health.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: cryptanalysis
{{- end -}}

{{- define "gpu-health.image" -}}
{{- if .Values.image.digest -}}
{{- printf "%s@%s" .Values.image.repository .Values.image.digest -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository (default .Chart.AppVersion .Values.image.tag) -}}
{{- end -}}
{{- end -}}

{{/*
The MutatingAdmissionPolicy API: inject.apiVersion, else the newest version
the cluster serves, else (helm template, no cluster to ask) v1.
*/}}
{{- define "gpu-health.admissionApi" -}}
{{- $found := .Values.inject.apiVersion -}}
{{- range list "v1" "v1beta1" "v1alpha1" -}}
{{- $gv := printf "admissionregistration.k8s.io/%s" . -}}
{{- if and (not $found) ($.Capabilities.APIVersions.Has (printf "%s/MutatingAdmissionPolicy" $gv)) -}}
{{- $found = $gv -}}
{{- end -}}
{{- end -}}
{{- default "admissionregistration.k8s.io/v1" $found -}}
{{- end -}}

{{/*
The check's environment, as a JSON list of {name, value}, for a mode:
"inject" (in the device plugin's pod) or "gate" (the node-gate DaemonSet).
NODE_NAME comes from the downward API and each consumer adds it.  Call as:
include "gpu-health.env" (list . "inject") | fromJsonArray
*/}}
{{- define "gpu-health.env" -}}
{{- $root := index . 0 -}}
{{- $mode := index . 1 -}}
{{- $c := $root.Values.check -}}
{{- $seconds := $c.seconds -}}
{{- if eq $mode "gate" -}}{{- $seconds = $root.Values.nodeGate.seconds -}}{{- end -}}
{{- $env := list (dict "name" "GPU_HEALTH_SECONDS" "value" (toString $seconds)) -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_EXPECT_GPUS" "value" (toString $c.expectGpus)) -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_WAIT_SECONDS" "value" (toString $c.waitSeconds)) -}}
{{- if $c.strict -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_STRICT" "value" "1") -}}
{{- end -}}
{{- with $c.thresholds -}}
{{- $pairs := list -}}
{{- range $k, $v := . -}}{{- $pairs = append $pairs (printf "%s=%v" $k $v) -}}{{- end -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_THRESHOLDS" "value" (join "," $pairs)) -}}
{{- end -}}
{{- with $c.baselines -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_BASELINES_JSON" "value" (toJson .)) -}}
{{- end -}}
{{- if $c.reportOnly -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_REPORT_ONLY" "value" "1") -}}
{{- end -}}
{{- if eq $mode "inject" -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_STATE_DIR" "value" $c.stateDir) -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_MAX_UPTIME" "value" (toString (int $c.maxUptimeSeconds))) -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_SKIP_WITHOUT_GPUS" "value" "1") -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_SKIP_UNSUPPORTED" "value" "1") -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_SKIP_IF_BUSY" "value" "1") -}}
{{- if $root.Values.inject.labelNode -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_LABEL_NODE" "value" "1") -}}
{{- end -}}
{{- else -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_NODE_GATE" "value" "1") -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_GATE_TAINT" "value" $root.Values.nodeGate.taint) -}}
{{- $env = append $env (dict "name" "GPU_HEALTH_GATE_LABEL" "value" $root.Values.nodeGate.label) -}}
{{- end -}}
{{- $env = append $env (dict "name" "NVIDIA_VISIBLE_DEVICES" "value" "all") -}}
{{- $env = append $env (dict "name" "NVIDIA_DRIVER_CAPABILITIES" "value" "compute,utility") -}}
{{- range $c.extraEnv -}}
{{- $env = append $env (dict "name" .name "value" (toString .value)) -}}
{{- end -}}
{{- toJson $env -}}
{{- end -}}

{{/*
A CEL string literal.  toJson quotes and escapes a string the way CEL reads
it: \" \\ \n \t and \uXXXX (Go also writes < > & as \u escapes), never \/.
*/}}
{{- define "gpu-health.cel" -}}
{{- toJson (toString .) -}}
{{- end -}}

{{/* A CEL map literal of strings, from a map of scalars. */}}
{{- define "gpu-health.celMap" -}}
{{- $items := list -}}
{{- range $k, $v := . -}}
{{- $items = append $items (printf "%s: %s" (include "gpu-health.cel" $k) (include "gpu-health.cel" $v)) -}}
{{- end -}}
{{- printf "{%s}" (join ", " $items) -}}
{{- end -}}
