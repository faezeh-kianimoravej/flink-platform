# GitHub Actions Workflows

This workflow directory is owned by the Platform Team.

The reusable Flink job CI workflow gives tenant repositories a shared build and delivery standard while keeping application source code in the tenant-owned repositories. Tenant repositories call the workflow from this platform repository instead of maintaining separate CI definitions for the same Maven and Docker image publishing process.

The workflow standardizes CI for Flink jobs by checking out the tenant repository, setting up Temurin Java, caching Maven dependencies, configuring Maven artifact repository access, running `mvn clean verify`, building a Docker image, and publishing the image to GitHub Container Registry.

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

## Maven Parent Resolution

Tenant repositories declare the shared parent version in their own `pom.xml` files:

```text
io.github.faezeh-kianimoravej:flink-job-parent
```

CI does not choose, discover, or duplicate this parent version. Maven resolves exactly the version declared by the tenant branch being built, which keeps Dependabot responsible for proposing future parent-version updates.

The reusable workflow supports two artifact repository modes:

- `github-packages`: the safe default for GitHub-hosted Actions runners.
- `nexus`: an opt-in mode for a self-hosted runner or a Nexus URL reachable from the runner.

Current demo mode:

```text
flink-job-parent
  -> GitHub Packages
  -> GitHub-hosted reusable CI
  -> tenant build
  -> GHCR
```

Validated local Nexus mode:

```text
flink-job-parent
  -> local Nexus
  -> local Maven build or self-hosted runner
  -> tenant build
```

Future enterprise mode:

```text
flink-job-parent
  -> company Nexus
  -> reusable CI
  -> tenant repositories
```

GitHub-hosted runners cannot access `http://localhost:8081` on a developer laptop. Keep tenant callers on `artifact_repository: github-packages` unless Nexus is available to the runner, for example through a self-hosted runner on the same machine or a remotely reachable Nexus URL.

To enable Nexus mode later, change the tenant caller input and pass Nexus credentials:

```yaml
with:
  artifact_repository: nexus
  nexus_url: http://localhost:8081/repository/maven-public/
  nexus_server_id: nexus-public
secrets:
  NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
  NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
```

The workflow uses `GH_PACKAGES_READ_TOKEN` only in `github-packages` mode and `NEXUS_USERNAME`/`NEXUS_PASSWORD` only in `nexus` mode. Passwords are written only to the runner's Maven settings file and must not be placed in tenant POM files.

Dependabot remains configured for GitHub Packages while Nexus is only local. Switch Dependabot to Nexus only after Nexus has a GitHub-reachable URL and matching Dependabot secrets.

## Tenant A Example

```yaml
name: Tenant A Flink Job CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    uses: faezeh-kianimoravej/flink-platform/.github/workflows/flink-job-ci-template.yml@main
    with:
      image_name: tenant-a-flink-job
      java_version: "21"
      dockerfile_path: Dockerfile
      artifact_repository: github-packages
    secrets:
      GH_PACKAGES_READ_TOKEN: ${{ secrets.GH_PACKAGES_READ_TOKEN }}
```

## Tenant B Example

```yaml
name: Tenant B Flink Job CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    uses: faezeh-kianimoravej/flink-platform/.github/workflows/flink-job-ci-template.yml@main
    with:
      image_name: tenant-b-flink-job
      java_version: "21"
      dockerfile_path: Dockerfile
      artifact_repository: github-packages
    secrets:
      GH_PACKAGES_READ_TOKEN: ${{ secrets.GH_PACKAGES_READ_TOKEN }}
```
