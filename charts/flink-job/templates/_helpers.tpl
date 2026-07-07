{{/*
Common template helpers for the flink-job chart.
*/}}
{{- define "flink-job.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "flink-job.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Values.tenantName (include "flink-job.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "flink-job.labels" -}}
app.kubernetes.io/name: {{ include "flink-job.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: flink-job
app.kubernetes.io/part-of: multi-tenant-flink-platform
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
platform.example.com/managed-by: flink-platform
platform.example.com/tenant: {{ .Values.tenantName | quote }}
{{- end -}}
