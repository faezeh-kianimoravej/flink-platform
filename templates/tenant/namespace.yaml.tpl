# Isolated namespace for {tenant_display_name} Flink jobs.
apiVersion: v1
kind: Namespace
metadata:
  name: {tenant_id}
  labels:
    app.kubernetes.io/managed-by: flink-platform
    app.kubernetes.io/part-of: multi-tenant-flink-platform
    platform.example.com/environment: local
    platform.example.com/tenant: {tenant_id}
