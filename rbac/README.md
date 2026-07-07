# Tenant RBAC

Kubernetes RBAC is part of the tenant onboarding process managed by the Platform Team.

When a new tenant is onboarded, the platform provisions:

- Namespace
- Role
- RoleBinding

These resources allow the Flink Kubernetes Operator to manage Flink workloads inside that tenant namespace.

## Why RBAC?

Each tenant is isolated in its own Kubernetes namespace. RBAC limits operational permissions to that namespace only, so operator access remains scoped and auditable.

- Tenant A cannot manage resources inside Tenant B.
- Tenant B cannot manage resources inside Tenant A.

This keeps platform operations scoped to the tenant namespace where a Flink workload is deployed. The prototype uses namespace-scoped `Role` and `RoleBinding` resources rather than broad cluster-wide permissions for tenant workloads.

## Relationship with the Flink Kubernetes Operator

The Flink Kubernetes Operator runs in the `platform-system` namespace.

During tenant onboarding, namespace-scoped permissions are granted through `RoleBinding` resources. Each `RoleBinding` associates a tenant namespace `Role` with the Flink Kubernetes Operator service account in `platform-system`.

The operator can reconcile `FlinkDeployment` resources only inside namespaces where RBAC has been provisioned. For this prototype, each tenant RBAC manifest grants the operator the Kubernetes permissions needed to reconcile Flink workloads in that tenant namespace.

## Tenant Onboarding Flow

```text
Platform Team
        |
        v
Create Namespace
        |
        v
Create Role
        |
        v
Create RoleBinding
        |
        v
Flink Operator can manage resources in the tenant namespace
```

Namespace creation and RBAC are deployed together as part of tenant onboarding. This means onboarding a tenant is represented as a change to platform-owned manifests rather than a sequence of manual cluster commands.

## GitOps

The RBAC manifests are stored in Git and managed declaratively.

For the local prototype they are applied together with the namespace manifests:

```bash
kubectl apply -f namespaces/ -f rbac/
```

This applies:

- tenant namespaces
- the `platform-system` namespace
- tenant-specific Roles
- tenant-specific RoleBindings

In the final GitOps flow, Argo CD will synchronize these manifests automatically from the platform repository, so tenant onboarding becomes declarative and repeatable.

## Verification

After applying the manifests, verify that each tenant namespace has its own Role and RoleBinding:

```bash
kubectl get role -n tenant-a
kubectl get rolebinding -n tenant-a

kubectl get role -n tenant-b
kubectl get rolebinding -n tenant-b
```

For a local syntax check without changing the cluster, use:

```bash
kubectl apply --dry-run=client -f rbac/
```

## Notes

Kubernetes RBAC provides operational isolation only. It controls access to Kubernetes resources such as pods, services, configmaps, and `FlinkDeployment` resources.

Access to Kafka topics is controlled separately and is outside the scope of Kubernetes RBAC. A Flink job may read from or join multiple Kafka streams if it has Kafka-level access to those topics, but it does not need Kubernetes access to another tenant namespace.
