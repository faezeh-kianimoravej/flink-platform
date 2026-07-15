# The Flink Kubernetes Operator runs in the platform-system namespace.
# During tenant onboarding, the Platform Team grants it namespace-scoped
# permissions for each tenant namespace.
#
# This Role only applies inside {tenant_id}. It does not grant {tenant_id}
# access to other tenant namespaces, and it does not control Kafka topic
# access. Kafka permissions are managed separately from Kubernetes RBAC.
apiVersion: v1
kind: ServiceAccount
metadata:
  name: flink
  namespace: {tenant_id}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: {tenant_id}-flink-operator-role
  namespace: {tenant_id}
rules:
  - apiGroups:
      - ""
    resources:
      - pods
      - services
      - configmaps
      - secrets
      - events
      - serviceaccounts
    verbs:
      - get
      - list
      - watch
      - create
      - update
      - patch
      - delete
  - apiGroups:
      - apps
    resources:
      - deployments
      - replicasets
    verbs:
      - get
      - list
      - watch
      - create
      - update
      - patch
      - delete
  - apiGroups:
      - flink.apache.org
    resources:
      - flinkdeployments
      - flinksessionjobs
    verbs:
      - get
      - list
      - watch
      - create
      - update
      - patch
      - delete
---
# Bind the {tenant_id} Role to the operator service account in platform-system
# and to the tenant runtime service account used by JobManager and TaskManager
# pods.
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {tenant_id}-flink-operator-rolebinding
  namespace: {tenant_id}
subjects:
  - kind: ServiceAccount
    name: flink-kubernetes-operator
    namespace: platform-system
  - kind: ServiceAccount
    name: flink
    namespace: {tenant_id}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: {tenant_id}-flink-operator-role
