apiVersion: kafka.strimzi.io/v1
kind: KafkaUser
metadata:
  name: {kafka_user}
  namespace: kafka-system
  labels:
    strimzi.io/cluster: flink-platform-kafka
    app.kubernetes.io/managed-by: flink-platform
    app.kubernetes.io/part-of: multi-tenant-flink-platform
    platform.example.com/application-id: {application_id}
    platform.example.com/owner-team: {owner_team}
spec:
  authentication:
    type: scram-sha-512
  authorization:
    type: simple
    acls:
{kafka_acls_yaml}
