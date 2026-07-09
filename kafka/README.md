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
kubectl apply -f kafka/kafka-system-namespace.yaml

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
- one internal plain listener on port `9092`
- TLS disabled
- no external listener
- no listener authentication
- the Strimzi Topic Operator enabled

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

For this prototype, tenant separation is represented using dedicated Kafka topics. Tenant A uses `tenant-a-*` topics, and Tenant B uses `tenant-b-*` topics.

In production, topic-level permissions would normally be enforced through Kafka ACLs or the enterprise messaging platform.

# Current Progress

- Kafka namespace manifest created
- Strimzi Kafka Operator installation documented
- Kafka CRD verification documented
- Local Kafka cluster manifest created
- Tenant Kafka topic manifests created

# Next Steps

- Connect tenant-a Flink job to Kafka
- Connect tenant-b Flink job to Kafka
