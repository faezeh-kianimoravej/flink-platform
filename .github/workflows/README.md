# GitHub Actions Workflows

This workflow directory is owned by the Platform Team.

The reusable Flink job CI workflow gives tenant repositories a shared build and delivery standard while keeping application source code in the tenant-owned repositories. Tenant repositories call the workflow from this platform repository instead of maintaining separate CI definitions for the same Maven and Docker image publishing process.

The workflow standardizes CI for Flink jobs by checking out the tenant repository, setting up Temurin Java, caching Maven dependencies, running `mvn clean verify`, building a Docker image, and publishing the image to GitHub Container Registry.

Deployment remains the responsibility of the `flink-platform` GitOps flow. The reusable CI workflow does not deploy to Kubernetes, run `kubectl`, run Helm, sync Argo CD, or update tenant GitOps values.

## Reusable Workflow

Tenant repositories reuse:

```text
faezeh-kianimoravej/flink-platform/.github/workflows/flink-job-ci-template.yml@main
```

Published images use this format:

```text
ghcr.io/${{ github.repository_owner }}/${{ inputs.image_name }}
```

Images are tagged with:

- `latest`
- the commit SHA from `github.sha`

## Tenant A Example

```yaml
name: Tenant A Flink Job CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    uses: faezeh-kianimoravej/flink-platform/.github/workflows/flink-job-ci-template.yml@main
    with:
      image_name: tenant-a-flink-job
      java_version: "21"
      dockerfile_path: Dockerfile
```

## Tenant B Example

```yaml
name: Tenant B Flink Job CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    uses: faezeh-kianimoravej/flink-platform/.github/workflows/flink-job-ci-template.yml@main
    with:
      image_name: tenant-b-flink-job
      java_version: "21"
      dockerfile_path: Dockerfile
```
