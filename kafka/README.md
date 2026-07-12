# Kafka Messaging Layer

Kafka is the shared messaging layer used by the Apache Flink jobs in the local multi-tenant platform prototype.

Kafka is not deployed inside the `tenant-a` or `tenant-b` namespaces. Instead, Kafka is installed as a shared platform component inside its own Kubernetes namespace.

For the local thesis prototype, Kafka runs inside the Minikube cluster. For the target enterprise architecture, Kafka represents an existing enterprise messaging platform managed independently from the Flink platform.

# Kafka Namespace

Kafka uses the dedicated namespace:

```text
kafka-system
```

The intended namespace layout is:

```text
platform-system
- Flink Kubernetes Operator
- Argo CD

kafka-system
- Strimzi Kafka Operator
- Kafka Cluster

tenant-a
- Tenant A Flink Job

tenant-b
- Tenant B Flink Job
```

Commands used to create and verify the namespace:

```bash
kubectl apply -f namespaces/kafka-system.yaml

kubectl get namespace kafka-system --show-labels
```

The first command applies the declarative namespace manifest stored in this repository. The second command verifies that the namespace exists and shows the labels that identify it as part of the local multi-tenant Flink platform prototype.

# Installing the Strimzi Kafka Operator

Strimzi was selected because it provides a Kubernetes-native way to run Kafka in the local Minikube prototype. It lets the prototype manage Kafka clusters and Kafka topics through Kubernetes custom resources, which matches the GitOps-oriented platform model used for Flink.

Step 1:

```bash
helm repo add strimzi https://strimzi.io/charts/
```

This adds the Strimzi Helm chart repository to the local Helm client.

Step 2:

```bash
helm repo update
```

This updates the local Helm repository index so the Strimzi chart can be installed.

Step 3:

```bash
helm install strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace kafka-system
```

This installs the Strimzi Kafka Operator into the `kafka-system` namespace.

# Verifying the Installation

Verify the operator pod:

```bash
kubectl get pods -n kafka-system
```

Expected result: the Strimzi Operator pod should eventually reach `1/1 Running`.

Verify the Helm release:

```bash
helm list -n kafka-system
```

Expected result: the `strimzi-kafka-operator` Helm release should be listed in the `kafka-system` namespace.

Verify the Kafka custom resource definitions:

```bash
kubectl get crds | findstr kafka
```

Expected result: Kafka CRDs should exist, including:

- `kafkas.kafka.strimzi.io`
- `kafkatopics.kafka.strimzi.io`
- `kafkausers.kafka.strimzi.io`

# Kafka Cluster Manifest

The local Kafka cluster is defined in:

```text
kafka/kafka-cluster.yaml
```

This manifest creates the Strimzi `Kafka` custom resource named `flink-platform-kafka` in the `kafka-system` namespace. It is intentionally sized for a local Minikube thesis demo, not for production.

The manifest uses KRaft mode with:

- one controller node pool
- one broker node pool
- ephemeral storage
- one internal listener named `plain` on port `9092`
- TLS disabled
- no external listener
- SCRAM-SHA-512 listener authentication
- Strimzi simple authorization
- the Strimzi Topic Operator enabled
- standalone tenant User Operators deployed from `rbac/strimzi-user-operator-tenant-rbac.yaml`

Kafka topics are not created by this manifest. Tenant topics will be added separately after the shared cluster is running.

Apply the local Kafka cluster:

```bash
kubectl apply -f kafka/kafka-cluster.yaml
```

Verify the Kafka custom resource:

```bash
kubectl get kafka -n kafka-system
```

Verify the Kafka, controller, broker, and operator pods:

```bash
kubectl get pods -n kafka-system
```

Verify the internal Kafka services:

```bash
kubectl get svc -n kafka-system
```

# Planned Kafka Topics

Tenant A:

- `tenant-a-orders`
- `tenant-a-customers`
- `tenant-a-enriched-orders`

Tenant B:

- `tenant-b-orders`
- `tenant-b-products`
- `tenant-b-enriched-orders`

# Creating Tenant Topics

Tenant topics are defined as Strimzi `KafkaTopic` resources in:

```text
kafka/topics/
```

These topics represent tenant-level Kafka separation in the local prototype. Tenant A uses `tenant-a-*` topics, and Tenant B uses `tenant-b-*` topics. In production, Kafka ACLs or the enterprise messaging platform would enforce topic-level access.

Create the tenant topics:

```bash
kubectl apply -f kafka/topics/
```

Verify the topic resources:

```bash
kubectl get kafkatopic -n kafka-system
```

# Kafka Authentication and Authorization

Kafka client access is managed with Strimzi `KafkaUser` resources in:

```text
kafka/users/
```

The embedded Strimzi User Operator is intentionally disabled in `kafka/kafka-cluster.yaml`. Tenant users are reconciled by the standalone User Operator deployments in `rbac/strimzi-user-operator-tenant-rbac.yaml`.

Each standalone User Operator watches one tenant namespace, uses a tenant-specific `STRIMZI_LABELS` selector, and ignores the other tenant's Kafka usernames with `STRIMZI_IGNORED_USERS_PATTERN`. This prevents two User Operators from competing over the same Kafka-side SCRAM credentials or ACLs. Generated Secrets are created in the same namespace as each `KafkaUser` and are never committed to Git.

Apply Kafka auth resources:

```bash
kubectl apply -f rbac/strimzi-user-operator-tenant-rbac.yaml
kubectl apply -f kafka/kafka-cluster.yaml
kubectl apply -f kafka/users/
```

Generated Secret names:

```text
tenant-a/tenant-a-flink-user
tenant-a/tenant-a-restricted-user
tenant-b/tenant-b-flink-user
tenant-b/tenant-b-restricted-user
```

ACL summary:

```text
tenant-a-flink-user:
  read/describe tenant-a-orders, tenant-a-customers
  write/describe tenant-a-enriched-orders
  read/describe groups tenant-a-flink-job, tenant-a-flink-job-customers

tenant-a-restricted-user:
  read/describe tenant-a-orders, tenant-a-customers
  read/describe groups tenant-a-flink-job, tenant-a-flink-job-customers
  no write access to tenant-a-enriched-orders

tenant-b-flink-user:
  read/describe tenant-b-orders, tenant-b-products
  write/describe tenant-b-enriched-orders
  read/describe groups tenant-b-flink-job, tenant-b-flink-job-products

tenant-b-restricted-user:
  read/describe tenant-b-orders, tenant-b-products
  read/describe groups tenant-b-flink-job, tenant-b-flink-job-products
  no write access to tenant-b-enriched-orders
```

The Helm values for each tenant select the Secret with:

```yaml
kafka:
  security:
    userSecretName: tenant-a-flink-user
governance:
  applicationId: APP-TENANT-A
  ownerTeam: tenant-a
  kafkaUser: tenant-a-flink-user
```

For the negative authorization demo, change only `kafka.security.userSecretName` and `governance.kafkaUser` to the restricted user for that tenant, commit the platform change, and let Argo CD sync the `FlinkDeployment`.

# Data Flow

Tenant A:

Reads:

- `tenant-a-orders`
- `tenant-a-customers`

Writes:

- `tenant-a-enriched-orders`

Tenant B:

Reads:

- `tenant-b-orders`
- `tenant-b-products`

Writes:

- `tenant-b-enriched-orders`

# RBAC vs Kafka Access

Kubernetes RBAC only controls access to Kubernetes resources such as namespaces, pods, services, configmaps, and `FlinkDeployment` resources.

Kafka topic permissions are separate.

For this prototype, tenant separation is enforced with Strimzi SCRAM users and Kafka ACLs. Tenant A uses `tenant-a-*` topics and Tenant B uses `tenant-b-*` topics. Cross-tenant reads and writes are denied by Kafka authorization.

In production, these ACLs could be managed by the enterprise messaging platform, but the GitOps model remains the same: non-secret desired access is in Git, generated credentials stay in Kubernetes Secrets.

# Current Progress

- Kafka namespace manifest created
- Strimzi Kafka Operator installation documented
- Kafka CRD verification documented
- Local Kafka cluster manifest created
- Tenant Kafka topic manifests created
- SCRAM-SHA-512 listener authentication configured
- Strimzi simple authorization configured
- Tenant KafkaUser manifests and ACLs created
- Restricted demo users created

# Next Steps

- Rebuild tenant images after Kafka client authentication support changes
- Update tenant image tags in `tenants/*/dev-values.yaml`
- Validate positive and negative authorization scenarios through Argo CD
