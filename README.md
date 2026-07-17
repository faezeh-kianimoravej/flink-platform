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
- namespaces for `argocd`, `platform-system`, `kafka-system`, `tenant-a`, and `tenant-b`
- the Flink Kubernetes Operator for reconciling `FlinkDeployment` resources
- Argo CD for GitOps deployment of tenant Flink jobs
- Strimzi for the local Kafka cluster, topics, SCRAM users, and ACLs
- a shared Helm chart in `charts/flink-job/`
- tenant-specific values under `tenants/`

The `kafka-system` namespace is defined with the other namespace manifests in `namespaces/kafka-system.yaml`.

## Namespaces and Tenant Isolation

Namespaces are declared in `namespaces/`:

- `argocd` for Argo CD
- `platform-system` for the Flink Kubernetes Operator
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

Strimzi generates the actual SCRAM credential Secrets in `kafka-system`, where the Kafka cluster and embedded User Operator run. The generated Secrets are not committed to Git.

Tenant Flink jobs run in `tenant-a` and `tenant-b`, so the local Minikube demo synchronizes the normal workload KafkaUser Secrets into the corresponding tenant namespace for pod consumption without decoding or committing passwords. Production environments should use a platform-approved external secret synchronization mechanism.

## Argo CD and GitOps

Argo CD runs in `argocd`. The Application manifests in `argocd/` are created in that namespace, point at this repository, and render `charts/flink-job` with tenant-specific values:

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
  -> immutable GHCR image tagged with the full Git SHA
  -> automatic dev promotion PR in flink-platform
  -> Platform Validation
  -> human review and manual merge
  -> Argo CD
  -> shared Helm chart
  -> FlinkDeployment
  -> Flink Kubernetes Operator
  -> running tenant job
```

Tenant repositories never deploy directly to Kubernetes. After a tenant change is merged to `main`, tenant CI must pass Maven verification, build the Docker image, and push the immutable SHA tag to GHCR before it sends a promotion request to this repository.

The promotion workflow updates only `tenants/<tenant>/dev-values.yaml`. Test and production promotion stay manual: copy a reviewed immutable SHA into `test-values.yaml` or `prod-values.yaml`, open a normal platform pull request, let Platform Validation run, and merge after approval.

Rollback uses the same PR-based GitOps path. Revert the dev image tag to a previous known-good SHA, let Platform Validation pass, merge the PR, and Argo CD reconciles the previous image.

## Platform Validation

`.github/workflows/platform-validation.yml` is the general required Pull Request check for this repository. It runs on every Pull Request targeting `main` and validates the platform as a whole:

- Helm lint for `charts/flink-job`
- Helm rendering for every `tenants/*/dev-values.yaml`, `test-values.yaml`, and `prod-values.yaml`
- rendered `FlinkDeployment` semantics, including immutable non-`latest` SHA image tags
- YAML syntax under `namespaces/`, `rbac/`, `argocd/`, `kafka/`, `operator/`, and `tenants/`
- Kubernetes schema validation with kubeconform
- semantic validation for Argo CD `Application`, Strimzi `KafkaTopic`, Strimzi `KafkaUser`, and rendered `FlinkDeployment` resources
- Python tests for promotion and validation helpers

Keep onboarding validation separate. `Validate Tenant Onboarding` protects onboarding-generated resources, while `Platform Validation` protects every platform Pull Request.

## Automatic Dev Image Promotion

`.github/workflows/promote-tenant-image.yml` listens for `repository_dispatch` events of type `tenant-image-published`. Tenant repositories send the dispatch only after their reusable CI job succeeds on a `push` to `main`.

The dispatch payload contains:

```text
tenant_id
repository_name
image_repository
image_tag
source_commit_sha
source_repository
```

The platform workflow verifies the tenant exists, `tenants/<tenant_id>/dev-values.yaml` exists, the configured image repository matches the request, and the image tag is the full lowercase 40-character Git SHA. It rejects `latest`, semantic tags, branch names, empty values, malformed SHAs, and repository mismatches.

Promotion branches use:

```text
promote/<tenant>/<short-sha>
```

Promotion commits use:

```text
chore(<tenant>): promote image to <short-sha>
```

Promotion PRs are titled:

```text
Promote <tenant> image to <short-sha>
```

Duplicate strategy: workflow-level concurrency is scoped to `promotion-<tenant>-dev`, so tenants do not block each other. Before creating a PR, the workflow searches for existing open promotion PRs for the same tenant. If the same SHA is already open, it exits successfully. If an older SHA is open, it closes that older PR, deletes the old branch when possible, and opens a fresh PR for the newer SHA. This keeps only one open dev promotion PR per tenant.

## Required GitHub Configuration

For this thesis prototype, use a fine-grained personal access token for `PLATFORM_PROMOTION_TOKEN`. A GitHub App installation token is preferable in a production organization because it is easier to scope, rotate, and audit.

Create the fine-grained PAT in GitHub under **Settings -> Developer settings -> Personal access tokens -> Fine-grained tokens**. Grant access only to the repositories that need it.

Store `PLATFORM_PROMOTION_TOKEN` in:

- each tenant repository that needs to request promotion, so it can call `repository_dispatch` on `flink-platform`
- the `flink-platform` repository, so the promotion workflow can push the promotion branch and open a PR in a way that triggers Pull Request validation

Required repository permissions for the token:

- `flink-platform`: Contents read/write, Pull requests read/write, Metadata read
- tenant repositories: no write access required for promotion, but the secret must be readable by Actions in that repository

Template-created tenant repositories must define the repository variable:

```text
TENANT_ID=<tenant-id>
```

Concrete repositories such as `tenant-a-flink-job` and `tenant-b-flink-job` hardcode their tenant ID in workflow YAML. Template-created repositories do not parse the repository name; they read `TENANT_ID`.

The reusable CI workflow for tenant repositories is stored under `.github/workflows/`. See [.github/workflows/README.md](.github/workflows/README.md).
