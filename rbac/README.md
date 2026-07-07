# Tenant RBAC

RBAC is part of the tenant onboarding process managed by the Platform Team.

When a new tenant is onboarded, the platform provisions:

- Namespace
- Role
- RoleBinding

These resources allow the Flink Kubernetes Operator to manage Flink workloads inside that tenant namespace.

## Why RBAC?

Each tenant is isolated in its own Kubernetes namespace. RBAC limits operational permissions to that namespace only.

- Tenant A cannot manage resources inside Tenant B.
- Tenant B cannot manage resources inside Tenant A.

This keeps platform operations scoped to the tenant namespace where a Flink workload is deployed.

## Relationship with the Flink Kubernetes Operator

The Flink Kubernetes Operator runs in the `platform-system` namespace.

During tenant onboarding, namespace-scoped permissions are granted through `RoleBinding` resources. Each `RoleBinding` associates a tenant namespace `Role` with the Flink Kubernetes Operator service account in `platform-system`.

The operator can reconcile `FlinkDeployment` resources only inside namespaces where RBAC has been provisioned.

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

Namespace creation and RBAC are deployed together as part of tenant onboarding.

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

Kubernetes RBAC provides operational isolation only. Access to Kafka topics is controlled separately and is outside the scope of Kubernetes RBAC.
