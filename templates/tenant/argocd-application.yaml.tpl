apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {tenant_id}-flink-job
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/faezeh-kianimoravej/flink-platform.git
    targetRevision: main
    path: charts/flink-job
    helm:
      releaseName: {tenant_id}
      valueFiles:
        - ../../tenants/{tenant_id}/dev-values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: {tenant_id}
  ignoreDifferences:
    - group: flink.apache.org
      kind: FlinkDeployment
      jsonPointers:
        - /metadata/finalizers
        - /metadata/managedFields
        - /metadata/generation
        - /metadata/annotations/kubectl.kubernetes.io~1last-applied-configuration
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=false
