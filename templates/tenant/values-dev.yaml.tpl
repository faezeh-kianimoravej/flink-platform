tenantName: {tenant_id}
namespace: {tenant_id}

image:
  repository: {image_repository}
  tag: {initial_image_tag}
  pullPolicy: IfNotPresent

flinkVersion: v2_2

job:
  className: {java_main_class}
  jarURI: local:///opt/flink/usrlib/{jar_name}
  parallelism: 1
  restartNonce: 7

kafka:
  bootstrapServers: flink-platform-kafka-kafka-bootstrap.kafka-system.svc.cluster.local:9092
  inputTopics:
{input_topics_yaml}
  outputTopic: {output_topic}
  consumerGroupId: {consumer_group_id}
  security:
    enabled: true
    protocol: SASL_PLAINTEXT
    saslMechanism: SCRAM-SHA-512
    username: {kafka_user}
    userSecretName: {kafka_user}
    passwordKey: password

governance:
  applicationId: {application_id}
  ownerTeam: {owner_team}
  kafkaUser: {kafka_user}

checkpointing:
  interval: 30s
