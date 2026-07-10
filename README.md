# Multi-Tenant Apache Flink Platform

This repository is the platform repository for a master's thesis prototype around Apache Flink on Kubernetes. It contains the shared infrastructure and deployment configuration used to run tenant Flink jobs in a local Minikube cluster.

The project is split across three repositories:

- `flink-platform`: this repository. It owns namespaces, RBAC, the shared Helm chart, Kafka resources, Argo CD Applications, and platform documentation.
- `tenant-a-flink-job`: Tenant A job code, tests, Dockerfile, and CI image build.
- `tenant-b-flink-job`: Tenant B job code, tests, Dockerfile, and CI image build.

Tenant repositories build and publish job images. This repository decides how those images are deployed into Kubernetes.

## Local Setup

For the complete step-by-step guide to deploy and run the platform locally, see:

[docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md)

## Repository Structure

```text
flink-platform/
  .github/workflows/
  argocd/
  charts/flink-job/
  docs/
  kafka/
  namespaces/
  operator/
  rbac/
  tenants/
  README.md
```

The root README is the project overview. The detailed component notes are kept close to the manifests they describe:

- [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) for running the full local prototype
- [operator/README.md](operator/README.md) for the Flink Kubernetes Operator
- [argocd/README.md](argocd/README.md) for Argo CD
- [kafka/README.md](kafka/README.md) for Kafka, Strimzi, topics, and users
- [rbac/README.md](rbac/README.md) for tenant RBAC
- [.github/workflows/README.md](.github/workflows/README.md) for the reusable tenant CI workflow

## Main Platform Components

The prototype uses:

- Minikube as the local Kubernetes runtime
- namespaces for `platform-system`, `kafka-system`, `tenant-a`, and `tenant-b`
- the Flink Kubernetes Operator for reconciling `FlinkDeployment` resources
- Argo CD for GitOps deployment of tenant Flink jobs
- Strimzi for the local Kafka cluster, topics, SCRAM users, and ACLs
- a shared Helm chart in `charts/flink-job/`
- tenant-specific values under `tenants/`

The `kafka-system` namespace is defined with the other namespace manifests in `namespaces/kafka-system.yaml`.

## Namespaces and Tenant Isolation

Namespaces are declared in `namespaces/`:

- `platform-system` for Argo CD and the Flink Kubernetes Operator
- `kafka-system` for Strimzi and the local Kafka cluster
- `tenant-a` for Tenant A workloads
- `tenant-b` for Tenant B workloads

Tenant RBAC is stored in `rbac/`. The Flink Kubernetes Operator runs centrally in `platform-system`, but it receives namespace-scoped permissions for each tenant. This lets the operator manage Flink workloads without giving tenants access to each other's Kubernetes resources.

Kafka access is handled separately from Kubernetes RBAC. The prototype uses Strimzi SCRAM-SHA-512 users and Kafka ACLs to keep Tenant A and Tenant B on their own topics.

## Shared Helm Chart

The shared chart in `charts/flink-job/` renders a `FlinkDeployment` for each tenant:

```text
shared Helm chart + tenant values = tenant FlinkDeployment
```

Tenant values set the namespace, image, job class, JAR URI, Kafka topics, consumer group, checkpoint interval, and Kafka credential Secret.

Useful local checks:

```bash
helm lint charts/flink-job
helm template tenant-a-dev charts/flink-job -f tenants/tenant-a/dev-values.yaml
helm template tenant-b-dev charts/flink-job -f tenants/tenant-b/dev-values.yaml
```

## Kafka Security

Kafka is managed through Strimzi resources in `kafka/`. The local Kafka cluster uses:

- SCRAM-SHA-512 authentication
- Strimzi simple authorization
- tenant-specific `KafkaTopic` resources
- tenant-specific `KafkaUser` resources

Tenant A uses `tenant-a-orders` and `tenant-a-customers` as input topics, `tenant-a-enriched-orders` as the output topic, and `tenant-a-flink-user` as the normal Kafka user.

Tenant B uses `tenant-b-orders` and `tenant-b-products` as input topics, `tenant-b-enriched-orders` as the output topic, and `tenant-b-flink-user` as the normal Kafka user.

Strimzi generates the actual SCRAM credential Secrets in the tenant namespaces. The generated Secrets are not committed to Git.

## Argo CD and GitOps

Argo CD runs in `platform-system`. The Application manifests in `argocd/` point at this repository and render `charts/flink-job` with tenant-specific values:

- `argocd/tenant-a-flink-job.yaml`
- `argocd/tenant-b-flink-job.yaml`

Both applications set `CreateNamespace=false`, so namespace creation is handled explicitly by the bootstrap manifests in `namespaces/`.

## Platform Responsibilities

The Platform Team owns this repository:

- namespace manifests
- RBAC manifests
- shared Helm chart
- Kafka platform resources
- Argo CD Application manifests
- tenant deployment values

The platform repository does not own the Flink job implementation itself. Job code and image builds stay in the tenant application repositories.

## Application Team Responsibilities

Application teams own their tenant job repositories:

- Flink job source code
- tests
- Dockerfiles
- CI pipelines
- published GHCR images

The boundary is simple: tenant repositories produce images; this repository deploys them.

## Deployment Flow

```text
tenant job repository
  -> CI pipeline
  -> GHCR image
  -> tenant values update in flink-platform
  -> Argo CD
  -> shared Helm chart
  -> FlinkDeployment
  -> Flink Kubernetes Operator
  -> running tenant job
```

The reusable CI workflow for tenant repositories is stored under `.github/workflows/`. See [.github/workflows/README.md](.github/workflows/README.md).
