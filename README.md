# Multi-Tenant Apache Flink Platform

This repository represents the Platform Team for a master's thesis prototype. Its purpose is to provide a reusable GitOps-based deployment platform for Apache Flink applications running on Kubernetes.

Individual development teams own their own Flink job repositories, such as `tenant-a-flink-job` and `tenant-b-flink-job`. Those repositories contain the application source code, tests, Dockerfile, and CI pipeline for building Flink job container images.

This repository contains the shared platform components used to deploy those jobs consistently across tenants. It is responsible for the common Kubernetes, Helm, and GitOps assets that connect tenant job images to the runtime platform.

## Prototype Scope

The prototype demonstrates:

- A shared Kubernetes platform
- GitOps deployment workflow
- Multi-tenancy
- Shared Helm chart
- Argo CD
- Flink Kubernetes Operator
- Tenant isolation using Kubernetes namespaces

The prototype uses two example tenants:

- `tenant-a`
- `tenant-b`

The goal is to keep the platform understandable and suitable for a local thesis prototype. Production-grade features such as secret management, certificate automation, network policies, and advanced observability can be added in later phases.

## Local Kubernetes Cluster

The prototype uses a dedicated Minikube cluster so that the platform can be tested locally without affecting any other Kubernetes environment.

Create the local cluster with:

```bash
minikube start --profile flink-platform-demo --cpus=4 --memory=8192 --driver=docker
```

Use the same profile for later Minikube commands:

```bash
minikube status --profile flink-platform-demo
```

If needed, switch `kubectl` to the Minikube context:

```bash
kubectl config use-context flink-platform-demo
```

# Namespace Provisioning

The first completed platform implementation step is namespace provisioning. The platform repository manages Kubernetes namespaces declaratively as code.

Instead of creating namespaces manually with:

```bash
kubectl create namespace ...
```

the platform defines namespace resources as Kubernetes manifests stored under:

```text
namespaces/
  platform-system.yaml
  tenant-a.yaml
  tenant-b.yaml
```

These manifests define:

- `platform-system` for platform components such as Argo CD and the Flink Kubernetes Operator
- `tenant-a` for Tenant A Flink jobs
- `tenant-b` for Tenant B Flink jobs

This follows the Infrastructure as Code and GitOps approach because namespace definitions are version-controlled, reviewable, and reproducible. In later phases, Argo CD can synchronize these manifests into the cluster automatically.

Apply the namespaces:

```bash
kubectl apply -f namespaces/
```

Inspect the created namespaces:

```bash
kubectl get namespaces
kubectl get namespace tenant-a --show-labels
kubectl get namespace tenant-b --show-labels
```

## Tenant Onboarding

Tenant onboarding is managed declaratively from this platform repository. Namespace creation and RBAC are applied together during tenant onboarding:

```bash
kubectl apply -f namespaces/ -f rbac/
```

Tenant RBAC is documented in [rbac/README.md](rbac/README.md).

## Shared Helm Chart

The shared Helm chart is owned by the Platform Team. It provides a reusable `FlinkDeployment` template for all tenant Flink jobs, using the Apache Flink Kubernetes Operator custom resource.

The relationship is:

```text
shared Helm chart + tenant-specific values = tenant-specific FlinkDeployment
```

The chart lives under `charts/flink-job/` and contains:

- `Chart.yaml` with the chart metadata
- `values.yaml` with demo-friendly default values
- `templates/flinkdeployment.yaml` for the rendered FlinkDeployment resource
- `templates/_helpers.tpl` for chart naming helpers

The chart keeps platform deployment structure separate from application code. Tenant job repositories build and publish container images, while this platform chart defines how those images are deployed on Kubernetes.

Validate the chart:

```bash
helm lint charts/flink-job
```

Render the chart with default values:

```bash
helm template tenant-a charts/flink-job
```

Render the chart with Tenant A values:

```bash
helm template tenant-a charts/flink-job -f tenants/tenant-a/dev-values.yaml
```

## Tenant-Specific Values

The shared Helm chart is combined with tenant-specific values to render separate `FlinkDeployment` resources for each tenant and environment.

```text
charts/flink-job + tenants/tenant-a/dev-values.yaml = Tenant A development FlinkDeployment
charts/flink-job + tenants/tenant-b/dev-values.yaml = Tenant B development FlinkDeployment
```

Tenant values live under `tenants/`:

```text
tenants/
  tenant-a/
    dev-values.yaml
    test-values.yaml
    prod-values.yaml
  tenant-b/
    dev-values.yaml
    test-values.yaml
    prod-values.yaml
```

Each values file overrides the shared defaults for the tenant name, namespace, image, Flink job class, JAR URI, parallelism, Kafka topics, consumer group, and checkpoint interval.

Render the development deployments:

```bash
helm template tenant-a-dev charts/flink-job -f tenants/tenant-a/dev-values.yaml
helm template tenant-b-dev charts/flink-job -f tenants/tenant-b/dev-values.yaml
```

Optional test renders:

```bash
helm template tenant-a-test charts/flink-job -f tenants/tenant-a/test-values.yaml
helm template tenant-b-test charts/flink-job -f tenants/tenant-b/test-values.yaml
```

Optional production renders:

```bash
helm template tenant-a-prod charts/flink-job -f tenants/tenant-a/prod-values.yaml
helm template tenant-b-prod charts/flink-job -f tenants/tenant-b/prod-values.yaml
```

## Platform Responsibilities

The Platform Team is responsible for the shared deployment foundation:

- Kubernetes namespace definitions for each tenant
- Tenant-level RBAC needed by the platform components
- A reusable Helm chart for Flink job deployments
- Argo CD Application definitions
- GitOps values files that select image versions and runtime configuration
- Integration with the Flink Kubernetes Operator

The Platform Team does not own the Flink job implementation itself. Job code and image builds stay in the tenant application repositories.

## Application Team Responsibilities

Each application team owns its own Flink job repository. For this prototype, the example job repositories are:

- `tenant-a-flink-job`
- `tenant-b-flink-job`

Application teams are responsible for:

- Flink job source code
- Job-specific tests
- Docker image builds
- CI pipelines
- Publishing versioned job images
- Requesting or proposing GitOps values updates when a new image should be deployed

## Target Deployment Flow

The platform is designed around the following flow:

```text
tenant job repository
  -> CI pipeline
  -> container image
  -> GitOps values update
  -> Argo CD
  -> shared Helm chart
  -> FlinkDeployment
  -> Flink Kubernetes Operator
  -> tenant namespace
```

This separation keeps application delivery and platform operations clear. Development teams produce deployable Flink job images, while the platform repository controls how those images are deployed into the shared Kubernetes platform.

## Initial Repository Layout

The repository is expected to evolve toward this structure:

```text
flink-platform/
  charts/
    flink-job/
  tenants/
    tenant-a/
    tenant-b/
  namespaces/
  rbac/
  argocd/
  README.md
```

The initial implementation should remain simple and educational. The purpose is to demonstrate the platform architecture and GitOps workflow, not to create a complete production platform.
