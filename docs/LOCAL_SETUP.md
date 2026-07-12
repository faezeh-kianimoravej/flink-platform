# Local Setup

This guide runs the complete local prototype from a clean Minikube environment. It is ordered by runtime dependency, not by repository directory.

Run the commands from the root of the `flink-platform` repository unless a step says otherwise.

## Prerequisites

Install these tools locally:

- Docker
- Minikube
- `kubectl`
- Helm
- Argo CD CLI, if you want to run `argocd app sync` from the terminal

The development values files reference these GHCR images:

```text
ghcr.io/faezeh-kianimoravej/tenant-a-flink-job:21376fcf70d31c0f41679066eaa4ca6cea1cd52e
ghcr.io/faezeh-kianimoravej/tenant-b-flink-job:4ce312c0ea0b8ea54dd824e209324b91f045427f
```

Those images must be available to the Kubernetes cluster. The tenant repositories are only needed if you want to inspect or rebuild the job code.

## Clone the Platform Repository

```bash
git clone https://github.com/faezeh-kianimoravej/flink-platform.git
cd flink-platform
```

Argo CD is configured to watch the same repository URL in `argocd/tenant-a-flink-job.yaml` and `argocd/tenant-b-flink-job.yaml`.

## 1. Start Minikube

```bash
minikube start --profile flink-platform-demo --cpus=4 --memory=8192 --driver=docker
kubectl config use-context flink-platform-demo
minikube status --profile flink-platform-demo
```

## 2. Create Namespaces

All namespaces are declared under `namespaces/`, including `namespaces/argocd.yaml` and `namespaces/kafka-system.yaml`. Argo CD Applications use `CreateNamespace=false`, so the namespaces must exist before the applications sync.

```bash
kubectl apply -f namespaces/
kubectl get namespaces
```

Expected namespaces:

- `argocd`
- `platform-system`
- `kafka-system`
- `tenant-a`
- `tenant-b`

## 3. Add Required Helm Repositories

Add the Helm repositories used by the platform:

```bash
helm repo add flink-operator-repo https://downloads.apache.org/flink/flink-kubernetes-operator-1.12.1/
helm repo add strimzi https://strimzi.io/charts/
helm repo update

## 4. Install the Flink Kubernetes Operator

Install the operator in `platform-system`:

```bash
helm install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator \
  --namespace platform-system
```

Verify it:

```bash
kubectl get pods -n platform-system
kubectl get crds | findstr flink
helm list -n platform-system
helm status flink-kubernetes-operator -n platform-system
```

## 5. Install Argo CD

Install Argo CD in `argocd`:

```bash
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Verify it:

```bash
kubectl get pods -n argocd
```

## 6. Install Strimzi

Install the Strimzi Kafka Operator in `kafka-system`:

```bash
helm install strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace kafka-system
```

Verify it:

```bash
kubectl get pods -n kafka-system
helm list -n kafka-system
kubectl get crds | findstr kafka
```

## 7. Apply RBAC

The `rbac/` directory contains tenant RBAC for the Flink Kubernetes Operator.

```bash
kubectl apply -f rbac/
```

Verify tenant RBAC:

```bash
kubectl get serviceaccount flink -n tenant-a
kubectl get role -n tenant-a
kubectl get rolebinding -n tenant-a

kubectl get serviceaccount flink -n tenant-b
kubectl get role -n tenant-b
kubectl get rolebinding -n tenant-b
```

## 8. Deploy Kafka

Deploy the local Kafka cluster:

```bash
kubectl apply -f kafka/kafka-cluster.yaml
```

Verify the Kafka custom resource, pods, and services:

```bash
kubectl get kafka -n kafka-system
kubectl get pods -n kafka-system
kubectl get svc -n kafka-system
```

Deploy tenant topics:

```bash
kubectl apply -f kafka/topics/
kubectl get kafkatopic -n kafka-system
```

Deploy Kafka users:

```powershell
kubectl apply -f kafka/users/
kubectl get kafkauser -n kafka-system
kubectl wait --for=condition=Ready kafkauser/tenant-a-flink-user -n kafka-system --timeout=120s
kubectl wait --for=condition=Ready kafkauser/tenant-b-flink-user -n kafka-system --timeout=120s
.\kafka\scripts\sync-kafka-user-secrets.ps1
```

Kafka runs in `kafka-system`. Tenant Flink jobs connect to:

```text
flink-platform-kafka-kafka-bootstrap.kafka-system.svc.cluster.local:9092
```

The embedded Kafka User Operator runs with the Kafka cluster in `kafka-system`, so `KafkaUser` resources and their generated SCRAM credential Secrets are created there. Do not create duplicate `KafkaUser` resources in tenant namespaces. The local demo synchronizes only the normal workload Secrets into the tenant namespaces because the tenant Flink pods read their Kafka password from a namespace-local Secret:

```text
kafka-system/tenant-a-flink-user
kafka-system/tenant-b-flink-user

tenant-a/tenant-a-flink-user
tenant-b/tenant-b-flink-user
```

The repository does not include a native secret synchronization controller such as External Secrets, a reflector, or the Secrets Store CSI driver. The PowerShell sync script is the local Minikube demo solution; production environments should use a platform-approved external secret synchronization mechanism.

## 9. Deploy Argo CD Applications

The Argo CD Application manifests deploy the shared Helm chart with Tenant A and Tenant B development values.

```bash
kubectl apply -f argocd/tenant-a-flink-job.yaml
kubectl apply -f argocd/tenant-b-flink-job.yaml
```

If you use the Argo CD CLI, sync the applications:

```bash
argocd app sync tenant-a-flink-job
argocd app sync tenant-b-flink-job
```

If you are not using the CLI, verify that Argo CD has registered the applications and let automated sync reconcile them:

```bash
kubectl get applications -n argocd
```

## 10. Verify the Runtime State

Check namespaces:

```bash
kubectl get namespace argocd --show-labels
kubectl get namespace platform-system --show-labels
kubectl get namespace kafka-system --show-labels
kubectl get namespace tenant-a --show-labels
kubectl get namespace tenant-b --show-labels
```

Check Kafka resources:

```bash
kubectl get kafka -n kafka-system
kubectl get kafkatopic -n kafka-system
kubectl get kafkauser -n kafka-system
kubectl get pods -n kafka-system
kubectl get svc -n kafka-system
```

Check generated KafkaUser Secrets:

```bash
kubectl get secret tenant-a-flink-user -n tenant-a
kubectl get secret tenant-b-flink-user -n tenant-b
kubectl get secret tenant-a-flink-user -n kafka-system
kubectl get secret tenant-a-restricted-user -n kafka-system
kubectl get secret tenant-b-flink-user -n kafka-system
kubectl get secret tenant-b-restricted-user -n kafka-system
```

Check Argo CD and Flink:

```bash
kubectl get applications -n argocd
kubectl get flinkdeployment -A
kubectl get pods -n tenant-a
kubectl get pods -n tenant-b
kubectl get pods -n tenant-a -l app=tenant-a-flink-job
kubectl get pods -n tenant-b -l app=tenant-b-flink-job
```

Check the Flink job status stored on the `FlinkDeployment` resources:

```bash
kubectl get flinkdeployment tenant-a-flink-job -n tenant-a -o jsonpath="{.status.jobStatus.state}"
kubectl get flinkdeployment tenant-b-flink-job -n tenant-b -o jsonpath="{.status.jobStatus.state}"
```

## 11. Open the UIs

Open Argo CD:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Then open:

```text
https://localhost:8080
```

The default username is `admin`. Retrieve the initial password with PowerShell:

```powershell
kubectl get secret argocd-initial-admin-secret `
  -n argocd `
  -o jsonpath="{.data.password}" |
ForEach-Object {
    [System.Text.Encoding]::UTF8.GetString(
        [System.Convert]::FromBase64String($_)
    )
}
```

Open the Flink Web UI for Tenant A:

```bash
kubectl port-forward svc/tenant-a-flink-job-rest -n tenant-a 8081:8081
```

Then open:

```text
http://localhost:8081
```

Open the Flink Web UI for Tenant B:

```bash
kubectl port-forward svc/tenant-b-flink-job-rest -n tenant-b 8082:8081
```

Then open:

```text
http://localhost:8082
```

This repository does not include Kubernetes Dashboard setup.

## Kafka Authorization Demo

Positive scenario:

```powershell
kubectl apply -f namespaces/
kubectl apply -f rbac/
kubectl apply -f kafka/kafka-cluster.yaml
kubectl apply -f kafka/topics/
kubectl apply -f kafka/users/
kubectl wait --for=condition=Ready kafkauser/tenant-a-flink-user -n kafka-system --timeout=120s
kubectl wait --for=condition=Ready kafkauser/tenant-b-flink-user -n kafka-system --timeout=120s
.\kafka\scripts\sync-kafka-user-secrets.ps1
argocd app sync tenant-a-flink-job
argocd app sync tenant-b-flink-job
kubectl get flinkdeployment -A
```

Expected result: both tenant jobs authenticate with their normal KafkaUser Secrets, read their own input topics, write their own output topics, and cannot access the other tenant's topics.

Negative scenario for Tenant A:

```bash
# Change tenants/tenant-a/dev-values.yaml:
# kafka.security.userSecretName: tenant-a-restricted-user
# governance.kafkaUser: tenant-a-restricted-user
.\kafka\scripts\sync-kafka-user-secret.ps1 -Tenant tenant-a -SecretName tenant-a-restricted-user
git add tenants/tenant-a/dev-values.yaml
git commit -m "Use restricted Kafka user for tenant-a demo"
git push
argocd app sync tenant-a-flink-job
kubectl logs -n tenant-a -l app=tenant-a-flink-job,component=taskmanager --tail=200
```

Expected result: authentication succeeds and input reads are allowed, but writes to `tenant-a-enriched-orders` fail with a Kafka `TopicAuthorizationException`. Restore `tenant-a-flink-user` in another Git commit and sync again.

Tenant B follows the same pattern with `tenant-b-restricted-user` and `tenant-b-enriched-orders`.

## Troubleshooting

Inspect platform pods:

```bash
kubectl get pods -n argocd
kubectl get pods -n platform-system
kubectl get pods -n kafka-system
```

Inspect tenant pods:

```bash
kubectl get pods -n tenant-a
kubectl get pods -n tenant-b
```

Inspect TaskManager logs:

```bash
kubectl logs -n tenant-a -l app=tenant-a-flink-job,component=taskmanager --tail=200
kubectl logs -n tenant-b -l app=tenant-b-flink-job,component=taskmanager --tail=200
```

Check Argo CD Applications and FlinkDeployments:

```bash
kubectl get applications -n argocd
kubectl get flinkdeployment -A
```

For local chart checks without changing the cluster:

```bash
helm lint charts/flink-job
helm template tenant-a charts/flink-job
helm template tenant-a-dev charts/flink-job -f tenants/tenant-a/dev-values.yaml
helm template tenant-b-dev charts/flink-job -f tenants/tenant-b/dev-values.yaml
helm template tenant-a-test charts/flink-job -f tenants/tenant-a/test-values.yaml
helm template tenant-b-test charts/flink-job -f tenants/tenant-b/test-values.yaml
helm template tenant-a-prod charts/flink-job -f tenants/tenant-a/prod-values.yaml
helm template tenant-b-prod charts/flink-job -f tenants/tenant-b/prod-values.yaml
```

## Cleanup and Reset

The repository does not currently document a project-specific cleanup sequence for individual resources.

For a disposable local run, keep the work isolated in the `flink-platform-demo` Minikube profile. If you choose to remove that profile, do it only when you no longer need the local cluster state.
