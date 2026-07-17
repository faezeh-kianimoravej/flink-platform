# GitHub Actions Workflows

This workflow directory is owned by the Platform Team.

The reusable Flink job CI workflow gives tenant repositories a shared build and delivery standard while keeping application source code in the tenant-owned repositories. Tenant repositories call the workflow from this platform repository instead of maintaining separate CI definitions for the same Maven and Docker image publishing process.

The workflow standardizes CI for Flink jobs by checking out the tenant repository, setting up Temurin Java, caching Maven dependencies, configuring Maven artifact repository access, running `mvn clean verify`, building a Docker image, and publishing the image to GitHub Container Registry.

Deployment remains the responsibility of the `flink-platform` GitOps flow. The reusable CI workflow does not deploy to Kubernetes, run `kubectl`, run Helm, or sync Argo CD. Tenant repositories request a dev image promotion only after the reusable CI job succeeds on `main`; the platform repository opens a GitOps PR for review.

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

GitOps values must use the immutable full commit SHA tag. `latest` is published for developer convenience only and is rejected by Platform Validation.

## Platform Validation

`platform-validation.yml` is the general Pull Request check for `flink-platform`. It runs on every PR targeting `main` and validates all platform changes, not only onboarding paths. The check name is stable:

```text
Platform Validation
```

It runs Helm lint, renders every tenant `dev`, `test`, and `prod` values file, validates rendered `FlinkDeployment` resources, parses platform YAML, runs kubeconform for Kubernetes schema validation, runs semantic checks for Argo CD and Strimzi resources, and executes the Python tests.

## Automatic Dev Image Promotion

Tenant repositories call the reusable CI workflow in job `ci`. A separate tenant-owned `promote-dev` job depends on `ci` and runs only for:

```text
github.event_name == 'push' && github.ref == 'refs/heads/main'
```

That means Pull Requests never promote images, and promotion is skipped if Maven verification, Docker build, or Docker push fails.

The tenant job sends a `repository_dispatch` event to `flink-platform` with:

```text
event_type: tenant-image-published
tenant_id
repository_name
image_repository
image_tag
source_commit_sha
source_repository
```

`promote-tenant-image.yml` updates only `tenants/<tenant_id>/dev-values.yaml`, commits to `promote/<tenant>/<short-sha>`, and opens a Pull Request titled `Promote <tenant> image to <short-sha>`. It never auto-merges and never updates `test-values.yaml` or `prod-values.yaml`.

Duplicate strategy: one workflow run per tenant dev promotion is allowed at a time through `promotion-<tenant>-dev` concurrency. If the same SHA already has an open promotion PR, the workflow exits successfully. If an older SHA has an open promotion PR, the workflow closes that older PR and opens a fresh PR for the newer image.

## Required Promotion Credentials

For the thesis prototype, use a fine-grained personal access token stored as `PLATFORM_PROMOTION_TOKEN`. A GitHub App is the better production option because installation permissions are easier to scope and rotate.

Store `PLATFORM_PROMOTION_TOKEN` in:

- each tenant repository, so it can send `repository_dispatch` to `flink-platform`
- `flink-platform`, so the promotion workflow can push branches and open PRs that trigger normal PR validation

Minimum token permissions for `flink-platform`:

- Contents: Read and write
- Pull requests: Read and write
- Metadata: Read

For template-created repositories, configure the repository variable:

```text
TENANT_ID=<tenant-id>
```

Concrete tenant repositories may hardcode their tenant ID in workflow YAML. Template-created repositories must not infer the tenant from the repository name.

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
  ci:
    uses: faezeh-kianimoravej/flink-platform/.github/workflows/flink-job-ci-template.yml@main
    with:
      image_name: tenant-a-flink-job
      java_version: "21"
      dockerfile_path: Dockerfile
      artifact_repository: github-packages
    secrets:
      GH_PACKAGES_READ_TOKEN: ${{ secrets.GH_PACKAGES_READ_TOKEN }}

  promote-dev:
    needs: ci
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Request dev image promotion
        env:
          GH_TOKEN: ${{ secrets.PLATFORM_PROMOTION_TOKEN }}
          PLATFORM_REPOSITORY: faezeh-kianimoravej/flink-platform
          TENANT_ID: tenant-a
          IMAGE_REPOSITORY: ghcr.io/${{ github.repository_owner }}/tenant-a-flink-job
        run: |
          gh api --method POST "repos/${PLATFORM_REPOSITORY}/dispatches" ...
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
  ci:
    uses: faezeh-kianimoravej/flink-platform/.github/workflows/flink-job-ci-template.yml@main
    with:
      image_name: tenant-b-flink-job
      java_version: "21"
      dockerfile_path: Dockerfile
      artifact_repository: github-packages
    secrets:
      GH_PACKAGES_READ_TOKEN: ${{ secrets.GH_PACKAGES_READ_TOKEN }}

  promote-dev:
    needs: ci
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Request dev image promotion
        env:
          GH_TOKEN: ${{ secrets.PLATFORM_PROMOTION_TOKEN }}
          PLATFORM_REPOSITORY: faezeh-kianimoravej/flink-platform
          TENANT_ID: tenant-b
          IMAGE_REPOSITORY: ghcr.io/${{ github.repository_owner }}/tenant-b-flink-job
        run: |
          gh api --method POST "repos/${PLATFORM_REPOSITORY}/dispatches" ...
```
