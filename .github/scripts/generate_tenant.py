#!/usr/bin/env python3
"""Generate platform-owned onboarding files for one new Flink tenant."""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path


TENANT_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
IMAGE_PREFIX = "ghcr.io/faezeh-kianimoravej/"
TEMPLATE_DIR = Path("templates/tenant")

# The active repository currently has no Flink Operator watch-namespace values
# file. If one is added later, keep this list narrow and explicit.
OPERATOR_WATCH_CONFIG_CANDIDATES = [
    Path("operator/flink-kubernetes-operator-values.yaml"),
    Path("operator/values.yaml"),
]


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: str
    tenant_display_name: str
    repository_name: str
    image_repository: str
    initial_image_tag: str
    java_main_class: str
    jar_name: str
    application_id: str
    owner_team: str
    input_topics: list[str]
    output_topic: str
    consumer_group_id: str
    kafka_user: str


def write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as output:
        if "\n" in value:
            output.write(f"{name}<<EOF\n{value}\nEOF\n")
        else:
            output.write(f"{name}={value}\n")


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def require_prefixed(value: str, prefix: str, label: str) -> None:
    if not value.startswith(prefix):
        raise SystemExit(f"{label} must begin with '{prefix}'. Got: {value}")


def build_config(args: argparse.Namespace) -> TenantConfig:
    tenant_id = args.tenant_id.strip()
    if not TENANT_RE.fullmatch(tenant_id):
        raise SystemExit("tenant_id must match ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

    repository_name = args.repository_name.strip()
    image_repository = args.image_repository.strip() or f"{IMAGE_PREFIX}{repository_name}"
    consumer_group_id = args.consumer_group_id.strip() or f"{tenant_id}-flink-job"
    kafka_user = args.kafka_user.strip() or f"{tenant_id}-flink-user"
    input_topics = split_csv(args.input_topics)

    if not repository_name:
        raise SystemExit("repository_name is required.")
    if not args.tenant_display_name.strip():
        raise SystemExit("tenant_display_name is required.")
    if not args.java_main_class.strip():
        raise SystemExit("java_main_class is required.")
    if not args.jar_name.strip():
        raise SystemExit("jar_name is required.")
    if not args.application_id.strip():
        raise SystemExit("application_id is required.")
    if not args.owner_team.strip():
        raise SystemExit("owner_team is required.")
    if not args.output_topic.strip():
        raise SystemExit("output_topic is required.")
    if len(input_topics) < 2:
        raise SystemExit("input_topics must contain at least two comma-separated topics.")
    if args.initial_image_tag.strip() == "latest" or not args.initial_image_tag.strip():
        raise SystemExit("initial_image_tag must not be empty or latest.")
    if not SHA_RE.fullmatch(args.initial_image_tag.strip()):
        raise SystemExit("initial_image_tag must be a full 40-character lowercase Git SHA.")
    if not image_repository.startswith(IMAGE_PREFIX):
        raise SystemExit(f"image_repository must be under {IMAGE_PREFIX}.")

    topic_prefix = f"{tenant_id}-"
    for topic in [*input_topics, args.output_topic.strip()]:
        require_prefixed(topic, topic_prefix, "Kafka topic")
    require_prefixed(kafka_user, topic_prefix, "kafka_user")
    require_prefixed(consumer_group_id, topic_prefix, "consumer_group_id")

    if len(set([*input_topics, args.output_topic.strip()])) != len(input_topics) + 1:
        raise SystemExit("Kafka input and output topics must be unique.")

    return TenantConfig(
        tenant_id=tenant_id,
        tenant_display_name=args.tenant_display_name.strip(),
        repository_name=repository_name,
        image_repository=image_repository,
        initial_image_tag=args.initial_image_tag.strip(),
        java_main_class=args.java_main_class.strip(),
        jar_name=args.jar_name.strip(),
        application_id=args.application_id.strip(),
        owner_team=args.owner_team.strip(),
        input_topics=input_topics,
        output_topic=args.output_topic.strip(),
        consumer_group_id=consumer_group_id,
        kafka_user=kafka_user,
    )


def render_template(repo_root: Path, template_name: str, values: dict[str, str]) -> str:
    template_path = repo_root / TEMPLATE_DIR / template_name
    content = template_path.read_text(encoding="utf-8")
    for key, value in values.items():
        content = content.replace("{" + key + "}", value)
    return content


def topic_document(topic: str) -> str:
    return f"""apiVersion: kafka.strimzi.io/v1
kind: KafkaTopic
metadata:
  name: {topic}
  namespace: kafka-system
  labels:
    strimzi.io/cluster: flink-platform-kafka
spec:
  partitions: 1
  replicas: 1
"""


def topic_acl(topic: str, operations: list[str]) -> str:
    ops = "\n".join(f"          - {operation}" for operation in operations)
    return f"""      - resource:
          type: topic
          name: {topic}
          patternType: literal
        operations:
{ops}
"""


def group_acl(group: str) -> str:
    return f"""      - resource:
          type: group
          name: {group}
          patternType: literal
        operations:
          - Read
          - Describe
"""


def render_files(repo_root: Path, config: TenantConfig) -> dict[Path, str]:
    input_topics_yaml = "\n".join(f"    - {topic}" for topic in config.input_topics)
    topics = [*config.input_topics, config.output_topic]
    kafka_topics_documents = "---\n".join(topic_document(topic) for topic in topics).rstrip() + "\n"

    kafka_acls = []
    for topic in config.input_topics:
        kafka_acls.append(topic_acl(topic, ["Read", "Describe"]))
    kafka_acls.append(topic_acl(config.output_topic, ["Write", "Describe"]))
    kafka_acls.append(group_acl(config.consumer_group_id))
    for topic in config.input_topics[1:]:
        suffix = topic.removeprefix(f"{config.tenant_id}-")
        kafka_acls.append(group_acl(f"{config.consumer_group_id}-{suffix}"))

    values = {
        "tenant_id": config.tenant_id,
        "tenant_display_name": config.tenant_display_name,
        "image_repository": config.image_repository,
        "initial_image_tag": config.initial_image_tag,
        "java_main_class": config.java_main_class,
        "jar_name": config.jar_name,
        "application_id": config.application_id,
        "owner_team": config.owner_team,
        "input_topics_yaml": input_topics_yaml,
        "output_topic": config.output_topic,
        "consumer_group_id": config.consumer_group_id,
        "kafka_user": config.kafka_user,
        "kafka_topics_documents": kafka_topics_documents,
        "kafka_acls_yaml": "".join(kafka_acls).rstrip(),
    }

    tenant_id = config.tenant_id
    return {
        Path(f"namespaces/{tenant_id}.yaml"): render_template(repo_root, "namespace.yaml.tpl", values),
        Path(f"rbac/{tenant_id}-rbac.yaml"): render_template(repo_root, "rbac.yaml.tpl", values),
        Path(f"tenants/{tenant_id}/dev-values.yaml"): render_template(repo_root, "values-dev.yaml.tpl", values),
        Path(f"argocd/{tenant_id}-flink-job.yaml"): render_template(repo_root, "argocd-application.yaml.tpl", values),
        Path(f"kafka/topics/{tenant_id}-topics.yaml"): render_template(repo_root, "kafka-topics.yaml.tpl", values),
        Path(f"kafka/users/{tenant_id}-flink-user.yaml"): render_template(repo_root, "kafka-user.yaml.tpl", values),
    }


def find_operator_watch_config(repo_root: Path) -> Path | None:
    for candidate in OPERATOR_WATCH_CONFIG_CANDIDATES:
        if (repo_root / candidate).exists():
            return candidate
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--tenant-display-name", required=True)
    parser.add_argument("--repository-name", required=True)
    parser.add_argument("--image-repository", default="")
    parser.add_argument("--initial-image-tag", required=True)
    parser.add_argument("--java-main-class", required=True)
    parser.add_argument("--jar-name", required=True)
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--owner-team", required=True)
    parser.add_argument("--input-topics", required=True)
    parser.add_argument("--output-topic", required=True)
    parser.add_argument("--consumer-group-id", default="")
    parser.add_argument("--kafka-user", default="")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    config = build_config(args)
    rendered_files = render_files(repo_root, config)

    existing = [path.as_posix() for path in rendered_files if (repo_root / path).exists()]
    if existing:
        raise SystemExit("Refusing to overwrite existing tenant files: " + ", ".join(existing))

    for relative_path, content in rendered_files.items():
        print(relative_path.as_posix())
        if not args.dry_run:
            destination = repo_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")

    operator_watch_config = find_operator_watch_config(repo_root)
    if operator_watch_config is None:
        operator_watch_status = "not-present"
        print("operator_watch_config=not-present")
    else:
        operator_watch_status = operator_watch_config.as_posix()
        print(f"operator_watch_config={operator_watch_status}")
        raise SystemExit(
            "An operator watch-namespace config file exists, but v1 does not "
            "know its schema. Update the generator before onboarding."
        )

    generated = "\n".join(path.as_posix() for path in rendered_files)
    write_output("generated_files", generated)
    write_output("generated_files_space", " ".join(path.as_posix() for path in rendered_files))
    write_output("operator_watch_config", operator_watch_status)
    write_output("tenant_id", config.tenant_id)
    write_output("image_repository", config.image_repository)
    write_output("image_tag", config.initial_image_tag)
    write_output("kafka_user", config.kafka_user)
    write_output("kafka_topics", ",".join([*config.input_topics, config.output_topic]))


if __name__ == "__main__":
    main()
