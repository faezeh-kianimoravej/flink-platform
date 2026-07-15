# Tenant Onboarding

This document describes version 1 of platform-side onboarding for a new Flink
tenant.

The platform repository owns Kubernetes namespaces, tenant RBAC, Argo CD
Applications, Kafka topic and user manifests, and tenant Helm values. Tenant
application repositories own source code, tests, Dockerfiles, CI, and published
GHCR images.

## Flow

1. Create a tenant repository from `flink-job-template`.
2. Configure the tenant repository source package, main class, Dockerfile, and
   CI workflow.
3. Push tenant code and wait for CI to publish a GHCR image tagged with the full
   immutable commit SHA.
4. In `flink-platform`, run the `Onboard Tenant` workflow.
5. Review the generated pull request.
6. Merge after governance review and validation.
7. Apply or bootstrap namespace, RBAC, Kafka resources, and the Argo CD
   Application where the current local setup still requires manual
   `kubectl apply`.
8. After Strimzi creates the tenant KafkaUser Secret in `kafka-system`, run the
   existing local Minikube Secret sync helper for the tenant.
9. Argo CD renders `charts/flink-job` with the tenant dev values file, and the
   Flink Kubernetes Operator reconciles the resulting `FlinkDeployment`.

## Workflow

Run:

```text
.github/workflows/onboard-tenant.yml
```

Workflow name:

```text
Onboard Tenant
```

The workflow is manually triggered with `workflow_dispatch`. It creates a branch
named:

```text
onboard/<tenant_id>
```

and opens a pull request titled:

```text
chore(<tenant_id>): onboard Flink tenant
```

The workflow never commits directly to `main` and never deploys to Kubernetes.

## Required Inputs

- `tenant_id`: DNS-safe tenant ID, such as `tenant-c`.
- `tenant_display_name`: human-readable name, such as `Tenant C`.
- `repository_name`: tenant job repository, such as `tenant-c-flink-job`.
- `initial_image_tag`: full immutable 40-character commit SHA image tag.
- `java_main_class`: Flink job main class.
- `jar_name`: job JAR name inside the image.
- `application_id`: governance application ID.
- `owner_team`: owner team label value.
- `input_topics`: comma-separated tenant input topics.
- `output_topic`: tenant output topic.

Optional inputs:

- `image_repository`: defaults to
  `ghcr.io/faezeh-kianimoravej/<repository_name>` when blank.
- `consumer_group_id`: defaults to `<tenant_id>-flink-job` when blank.
- `kafka_user`: defaults to `<tenant_id>-flink-user` when blank.

## Generated Files

Version 1 generates only development-environment tenant files:

```text
namespaces/<tenant_id>.yaml
rbac/<tenant_id>-rbac.yaml
tenants/<tenant_id>/dev-values.yaml
argocd/<tenant_id>-flink-job.yaml
kafka/topics/<tenant_id>-topics.yaml
kafka/users/<tenant_id>-flink-user.yaml
```

The generated files follow the active `tenant-a` and `tenant-b` repository
structure. The shared chart, shared Kafka cluster, and existing tenant files are
not changed.

## Operator Opt-In

The active repository does not currently contain a Flink Operator
watch-namespace configuration file. Tenant opt-in is represented by generated
namespace-scoped RBAC that binds the shared operator service account in
`platform-system` to permissions inside the tenant namespace.

The workflow reports this explicitly in the pull request body. If a real
operator watch-namespace values file is added later, update
`.github/scripts/generate_tenant.py` and
`.github/scripts/validate_tenant_onboarding.py` before onboarding more tenants.

## Validation

The onboarding workflow validates generated files before opening the pull
request. Pull requests that modify tenant onboarding paths are validated again by:

```text
.github/workflows/validate-tenant-onboarding.yml
```

Workflow name:

```text
Validate Tenant Onboarding
```

Validation checks include:

- tenant ID format
- no overwrite of existing tenant files
- immutable full commit-SHA image tag
- GHCR image repository under `ghcr.io/faezeh-kianimoravej/`
- tenant-prefixed Kafka topics, Kafka user, and consumer group
- YAML syntax
- `helm lint charts/flink-job`
- `helm template` with the generated dev values file
- rendered `FlinkDeployment` namespace, image, main class, and Kafka Secret
- namespace and RBAC structure
- Argo CD Application path, values file, destination namespace, and
  `CreateNamespace=false`
- KafkaTopic and KafkaUser ACL tenant scoping
- changed files limited to the generated tenant-scoped files
- existing `tenant-a` and `tenant-b` files remain unchanged

## Manual Governance

Automation does not replace governance. These steps remain manual:

- approve onboarding for the tenant
- review generated RBAC and Kafka ACLs
- create required tenant repository secrets, including the Dependabot
  `GH_PACKAGES_READ_TOKEN` secret where needed
- decide production resource sizing and parallelism
- configure production-grade secret synchronization
- apply/bootstrap resources where the local setup still relies on manual
  `kubectl apply`
- merge the generated pull request only after review

## Local Secret Sync

For local Minikube, Strimzi creates the KafkaUser Secret in `kafka-system`.
Tenant pods need a namespace-local Secret, so run the existing helper after the
KafkaUser is ready:

```powershell
.\kafka\scripts\sync-kafka-user-secret.ps1 -Tenant <tenant_id>
```

This helper is for the local demo only. It is not production secret
synchronization infrastructure.
