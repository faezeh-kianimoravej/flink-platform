# Argo CD

## Purpose

Argo CD is the GitOps controller of the platform. It continuously watches the `flink-platform` Git repository and synchronizes the desired state into the Kubernetes cluster.

In this thesis prototype, Argo CD connects the platform repository to the Kubernetes runtime. The platform team defines Kubernetes and Helm resources in Git, and Argo CD applies those desired resources to the cluster.

The deployment flow is:

```text
flink-platform Git Repository
        |
        v
Argo CD
        |
        v
Helm Chart + Tenant Values
        |
        v
FlinkDeployment
        |
        v
Flink Kubernetes Operator
        |
        v
Running Flink Job
```

## Namespace

Argo CD is installed in:

```text
platform-system
```

The `platform-system` namespace is used for shared platform components, including Argo CD and the Flink Kubernetes Operator.

## Installation

Install Argo CD into the `platform-system` namespace with:

```bash
kubectl apply -n platform-system -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

This command applies the standard Argo CD installation manifests to the cluster. It installs the Argo CD controllers, API server, repository server, Redis component, services, service accounts, RBAC rules, and custom resource definitions needed to manage Argo CD `Application` resources.

## Verification

Verify that the Argo CD pods are created in the `platform-system` namespace:

```bash
kubectl get pods -n platform-system
```

All Argo CD components should eventually reach the `Running` state. During startup, some pods may briefly appear as `Pending`, `ContainerCreating`, or `Init` before becoming ready.

## Accessing the Argo CD UI

Forward the local port `8080` to the Argo CD server service:

```bash
kubectl port-forward svc/argocd-server -n platform-system 8080:443
```

The Argo CD UI is available at:

```text
https://localhost:8080
```

The browser may display a certificate warning because the local Argo CD installation uses a self-signed certificate. For the local thesis prototype, this warning is expected.

## Login

The default username is:

```text
admin
```

Use the following PowerShell command to retrieve the initial admin password:

```powershell
kubectl get secret argocd-initial-admin-secret `
  -n platform-system `
  -o jsonpath="{.data.password}" |
ForEach-Object {
    [System.Text.Encoding]::UTF8.GetString(
        [System.Convert]::FromBase64String($_)
    )
}
```

## GitOps Repository

Argo CD watches the platform repository:

```text
https://github.com/faezeh-kianimoravej/flink-platform.git
```

This repository contains the desired platform state:

- Helm chart
- Tenant values
- Argo CD Applications
- Kubernetes manifests
- Shared platform configuration

Argo CD does not deploy directly from the tenant job repositories:

- `tenant-a-flink-job`
- `tenant-b-flink-job`

Those tenant repositories are responsible for application source code and GitHub Actions pipelines that build Docker images. The resulting image references are then consumed by the platform repository through tenant-specific values files.

## Next Step

The next implementation step is creating two Argo CD `Application` resources:

- `tenant-a-flink-job`
- `tenant-b-flink-job`

These Applications will deploy the shared Helm chart using tenant-specific values from the `flink-platform` repository. Argo CD will render the Helm chart, create the resulting `FlinkDeployment` resources in the tenant namespaces, and the Flink Kubernetes Operator will reconcile those resources into running Flink components.

Apply the tenant Applications with:

```bash
kubectl apply -f argocd/tenant-a-flink-job.yaml
kubectl apply -f argocd/tenant-b-flink-job.yaml
```

Verify that Argo CD has registered the Applications:

```bash
kubectl get applications -n platform-system
```
