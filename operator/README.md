# Flink Kubernetes Operator

The Flink Kubernetes Operator is a shared platform component installed in the `platform-system` namespace.

The operator is owned by the Platform Team. Tenant teams do not install or manage their own operators. Instead, the shared operator watches onboarded tenant namespaces and reconciles `FlinkDeployment` resources created from the platform Helm chart.

When a tenant `FlinkDeployment` is applied, the operator reconciles the desired state and creates the Kubernetes resources needed to run the Flink job, including JobManager and TaskManager pods.

# Installing the Flink Kubernetes Operator

This guide documents the local prototype installation process from scratch. It assumes that a Kubernetes cluster is already running and that `kubectl` is configured to point to that cluster.

For this thesis prototype, the target namespace is:

```text
platform-system
```

The `platform-system` namespace is defined declaratively in this repository under `namespaces/`.

## 1. Add the Helm repository

```bash
helm repo add flink-operator-repo https://downloads.apache.org/flink/flink-kubernetes-operator-1.12.1/
```

## 2. Update Helm repositories

```bash
helm repo update
```

## 3. Create platform and tenant onboarding resources

Apply the namespace and tenant RBAC manifests from the platform repository:

```bash
kubectl apply -f namespaces/ -f rbac/
```

This creates:

- the `platform-system` namespace for shared platform components
- tenant namespaces such as `tenant-a` and `tenant-b`
- tenant-specific Roles
- tenant-specific RoleBindings

## 4. Install the operator

Install the Flink Kubernetes Operator into the `platform-system` namespace:

```bash
helm install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator \
  --namespace platform-system
```

## 5. Verify the operator pod

```bash
kubectl get pods -n platform-system
```

The operator pod should be running in the `platform-system` namespace.

## 6. Verify the Flink CRDs

```bash
kubectl get crds | findstr flink
```

This confirms that the Flink custom resource definitions, including `FlinkDeployment`, are installed in the cluster.

## 7. Optional: Inspect the Helm release

```bash
helm list -n platform-system
helm status flink-kubernetes-operator -n platform-system
```

## Tenant RBAC

Tenant-specific RBAC is managed separately under `rbac/`.

The operator runs in `platform-system`, but it receives namespace-scoped permissions for each onboarded tenant through tenant-specific `Role` and `RoleBinding` manifests. This lets the shared operator manage Flink workloads in tenant namespaces without giving tenants access to each other's Kubernetes resources.

## Notes

Tenant teams do not install their own Flink Kubernetes Operators. The shared operator is a platform component and is operated by the Platform Team.

The operator installation and tenant RBAC solve different concerns:

- the operator installation adds the controller and Flink CRDs
- tenant RBAC grants the operator namespace-scoped permissions for onboarded tenants

In a later GitOps phase, this installation can be represented declaratively through Argo CD instead of being installed manually with Helm commands.
