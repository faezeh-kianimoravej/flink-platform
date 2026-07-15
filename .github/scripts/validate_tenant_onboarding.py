#!/usr/bin/env python3
"""Validate a tenant onboarding change before it becomes GitOps state."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised in environments without PyYAML
    raise SystemExit("PyYAML is required. Install it with: python -m pip install pyyaml") from exc


TENANT_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
IMAGE_PREFIX = "ghcr.io/faezeh-kianimoravej/"
TENANT_PATH_PATTERNS = [
    re.compile(r"^namespaces/([^/]+)\.yaml$"),
    re.compile(r"^rbac/([^/]+)-rbac\.yaml$"),
    re.compile(r"^tenants/([^/]+)/dev-values\.yaml$"),
    re.compile(r"^argocd/([^/]+)-flink-job\.yaml$"),
    re.compile(r"^kafka/topics/([^/]+)-topics\.yaml$"),
    re.compile(r"^kafka/users/([^/]+)-flink-user\.yaml$"),
]
OPERATOR_WATCH_CONFIG_CANDIDATES = {
    "operator/flink-kubernetes-operator-values.yaml",
    "operator/values.yaml",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def run(command: list[str], cwd: Path) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError:
        fail(f"Required command not found: {command[0]}")
    except subprocess.CalledProcessError as exc:
        print(exc.stdout)
        fail(f"Command failed: {' '.join(command)}")
    return completed.stdout


def git_lines(args: list[str], cwd: Path) -> list[str]:
    output = run(["git", *args], cwd)
    return [line.strip() for line in output.splitlines() if line.strip()]


def changed_files(repo_root: Path, base_ref: str | None, head_ref: str | None) -> list[str]:
    if base_ref and head_ref:
        return git_lines(["diff", "--name-only", f"{base_ref}..{head_ref}"], repo_root)

    tracked = git_lines(["diff", "--name-only"], repo_root)
    untracked = git_lines(["ls-files", "--others", "--exclude-standard"], repo_root)
    return sorted(set(tracked + untracked))


def infer_tenant_id(files: list[str]) -> str:
    tenants: set[str] = set()
    for file_name in files:
        normalized = file_name.replace("\\", "/")
        for pattern in TENANT_PATH_PATTERNS:
            match = pattern.fullmatch(normalized)
            if match:
                tenants.add(match.group(1))

    if len(tenants) != 1:
        fail(f"Expected exactly one onboarded tenant in changed files, found: {sorted(tenants)}")
    return next(iter(tenants))


def allowed_files(tenant_id: str) -> set[str]:
    return {
        f"namespaces/{tenant_id}.yaml",
        f"rbac/{tenant_id}-rbac.yaml",
        f"tenants/{tenant_id}/dev-values.yaml",
        f"argocd/{tenant_id}-flink-job.yaml",
        f"kafka/topics/{tenant_id}-topics.yaml",
        f"kafka/users/{tenant_id}-flink-user.yaml",
        *OPERATOR_WATCH_CONFIG_CANDIDATES,
    }


def validate_change_scope(repo_root: Path, tenant_id: str, files: list[str]) -> None:
    allowed = allowed_files(tenant_id)
    unexpected = [file for file in files if file.replace("\\", "/") not in allowed]
    if unexpected:
        fail("Unexpected changed files for tenant onboarding: " + ", ".join(unexpected))

    protected = [file for file in files if "/tenant-a/" in file or "/tenant-b/" in file]
    protected += [
        file
        for file in files
        if file in {
            "namespaces/tenant-a.yaml",
            "namespaces/tenant-b.yaml",
            "rbac/tenant-a-rbac.yaml",
            "rbac/tenant-b-rbac.yaml",
            "argocd/tenant-a-flink-job.yaml",
            "argocd/tenant-b-flink-job.yaml",
            "kafka/topics/tenant-a-topics.yaml",
            "kafka/topics/tenant-b-topics.yaml",
            "kafka/users/tenant-a-flink-user.yaml",
            "kafka/users/tenant-b-flink-user.yaml",
        }
    ]
    if protected:
        fail("tenant-a and tenant-b files must remain unchanged: " + ", ".join(sorted(set(protected))))

    for required in sorted(allowed_files(tenant_id) - OPERATOR_WATCH_CONFIG_CANDIDATES):
        if not (repo_root / required).exists():
            fail(f"Missing generated file: {required}")


def load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except yaml.YAMLError as exc:
        fail(f"YAML syntax error in {path}: {exc}")
    return [doc for doc in documents if doc is not None]


def load_single_yaml(path: Path) -> dict[str, Any]:
    docs = load_yaml_documents(path)
    if len(docs) != 1:
        fail(f"Expected exactly one YAML document in {path}, found {len(docs)}")
    return docs[0]


def nested(data: dict[str, Any], keys: list[str], label: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            fail(f"Missing {label}: {'.'.join(keys)}")
        current = current[key]
    return current


def validate_values(repo_root: Path, tenant_id: str) -> dict[str, Any]:
    values_path = repo_root / f"tenants/{tenant_id}/dev-values.yaml"
    values = load_single_yaml(values_path)
    if values.get("tenantName") != tenant_id:
        fail("values tenantName does not match tenant_id.")
    if values.get("namespace") != tenant_id:
        fail("values namespace does not match tenant_id.")

    image = nested(values, ["image"], "image")
    repository = image.get("repository", "")
    tag = image.get("tag", "")
    if not isinstance(repository, str) or not repository.startswith(IMAGE_PREFIX):
        fail(f"image.repository must be under {IMAGE_PREFIX}.")
    if tag == "latest" or not isinstance(tag, str) or not SHA_RE.fullmatch(tag):
        fail("image.tag must be a full immutable 40-character lowercase Git SHA.")

    class_name = nested(values, ["job", "className"], "job className")
    if not isinstance(class_name, str) or not class_name:
        fail("job.className must be set.")

    kafka = nested(values, ["kafka"], "kafka")
    input_topics = kafka.get("inputTopics", [])
    output_topic = kafka.get("outputTopic")
    consumer_group = kafka.get("consumerGroupId")
    if not isinstance(input_topics, list) or len(input_topics) < 2:
        fail("kafka.inputTopics must contain at least two topics.")
    for topic in [*input_topics, output_topic]:
        if not isinstance(topic, str) or not topic.startswith(f"{tenant_id}-"):
            fail(f"Kafka topic must begin with {tenant_id}-: {topic}")
    if not isinstance(consumer_group, str) or not consumer_group.startswith(f"{tenant_id}-"):
        fail("kafka.consumerGroupId must be tenant-prefixed.")

    security = nested(values, ["kafka", "security"], "kafka security")
    kafka_user = security.get("userSecretName")
    if not isinstance(kafka_user, str) or not kafka_user.startswith(f"{tenant_id}-"):
        fail("kafka.security.userSecretName must be tenant-prefixed.")
    if security.get("username") != kafka_user:
        fail("kafka.security.username must match userSecretName.")
    if nested(values, ["governance", "kafkaUser"], "governance kafkaUser") != kafka_user:
        fail("governance.kafkaUser must match the Kafka Secret name.")

    return values


def validate_namespace(repo_root: Path, tenant_id: str) -> None:
    namespace = load_single_yaml(repo_root / f"namespaces/{tenant_id}.yaml")
    if namespace.get("kind") != "Namespace":
        fail("namespace manifest must be kind Namespace.")
    if nested(namespace, ["metadata", "name"], "namespace name") != tenant_id:
        fail("namespace metadata.name does not match tenant_id.")
    labels = nested(namespace, ["metadata", "labels"], "namespace labels")
    if labels.get("platform.example.com/tenant") != tenant_id:
        fail("namespace tenant label does not match tenant_id.")


def validate_rbac(repo_root: Path, tenant_id: str) -> None:
    docs = load_yaml_documents(repo_root / f"rbac/{tenant_id}-rbac.yaml")
    kinds = [doc.get("kind") for doc in docs]
    if kinds != ["ServiceAccount", "Role", "RoleBinding"]:
        fail(f"RBAC manifest must contain ServiceAccount, Role, RoleBinding. Got: {kinds}")
    for doc in docs:
        metadata = nested(doc, ["metadata"], "RBAC metadata")
        if metadata.get("namespace") != tenant_id:
            fail("Every tenant RBAC object must be namespace-scoped to the tenant.")
    role = docs[1]
    if nested(role, ["metadata", "name"], "Role name") != f"{tenant_id}-flink-operator-role":
        fail("Role name does not match tenant_id.")
    binding = docs[2]
    subjects = binding.get("subjects", [])
    expected_subjects = {
        ("ServiceAccount", "flink-kubernetes-operator", "platform-system"),
        ("ServiceAccount", "flink", tenant_id),
    }
    actual_subjects = {(item.get("kind"), item.get("name"), item.get("namespace")) for item in subjects}
    if expected_subjects - actual_subjects:
        fail("RoleBinding must bind the platform operator and tenant flink service accounts.")


def validate_argocd(repo_root: Path, tenant_id: str) -> None:
    app = load_single_yaml(repo_root / f"argocd/{tenant_id}-flink-job.yaml")
    if app.get("kind") != "Application":
        fail("Argo CD manifest must be kind Application.")
    if nested(app, ["metadata", "namespace"], "Application namespace") != "argocd":
        fail("Argo CD Application must live in argocd namespace.")
    spec = nested(app, ["spec"], "Application spec")
    if nested(spec, ["source", "path"], "Application source path") != "charts/flink-job":
        fail("Argo CD Application must use charts/flink-job.")
    value_files = nested(spec, ["source", "helm", "valueFiles"], "Application valueFiles")
    if value_files != [f"../../tenants/{tenant_id}/dev-values.yaml"]:
        fail("Argo CD Application must use the tenant dev values file.")
    if nested(spec, ["destination", "namespace"], "Application destination namespace") != tenant_id:
        fail("Argo CD Application must target the tenant namespace.")
    sync_options = nested(spec, ["syncPolicy", "syncOptions"], "Application sync options")
    if "CreateNamespace=false" not in sync_options:
        fail("Argo CD Application must use CreateNamespace=false.")


def validate_kafka(repo_root: Path, tenant_id: str, values: dict[str, Any]) -> None:
    input_topics = nested(values, ["kafka", "inputTopics"], "input topics")
    output_topic = nested(values, ["kafka", "outputTopic"], "output topic")
    consumer_group = nested(values, ["kafka", "consumerGroupId"], "consumer group")
    kafka_user = nested(values, ["kafka", "security", "userSecretName"], "Kafka user Secret")
    expected_topics = [*input_topics, output_topic]

    topic_docs = load_yaml_documents(repo_root / f"kafka/topics/{tenant_id}-topics.yaml")
    topic_names = [nested(doc, ["metadata", "name"], "KafkaTopic name") for doc in topic_docs]
    if topic_names != expected_topics:
        fail(f"KafkaTopic names must match values topics. Got: {topic_names}")
    for doc in topic_docs:
        if doc.get("kind") != "KafkaTopic":
            fail("Kafka topics manifest may only contain KafkaTopic resources.")
        if nested(doc, ["metadata", "namespace"], "KafkaTopic namespace") != "kafka-system":
            fail("KafkaTopic resources must live in kafka-system.")

    user = load_single_yaml(repo_root / f"kafka/users/{tenant_id}-flink-user.yaml")
    if user.get("kind") != "KafkaUser":
        fail("Kafka user manifest must be kind KafkaUser.")
    if nested(user, ["metadata", "name"], "KafkaUser name") != kafka_user:
        fail("KafkaUser metadata.name must match values Kafka user.")
    if nested(user, ["metadata", "namespace"], "KafkaUser namespace") != "kafka-system":
        fail("KafkaUser must live in kafka-system.")

    acls = nested(user, ["spec", "authorization", "acls"], "KafkaUser ACLs")
    topic_acl_names = {
        acl["resource"]["name"]
        for acl in acls
        if acl.get("resource", {}).get("type") == "topic"
    }
    group_acl_names = {
        acl["resource"]["name"]
        for acl in acls
        if acl.get("resource", {}).get("type") == "group"
    }
    if set(expected_topics) - topic_acl_names:
        fail("KafkaUser must have ACLs for every tenant topic.")
    for name in topic_acl_names | group_acl_names:
        if not name.startswith(f"{tenant_id}-"):
            fail(f"KafkaUser ACL resource is not tenant-prefixed: {name}")
    if consumer_group not in group_acl_names:
        fail("KafkaUser must grant access to the tenant consumer group.")


def validate_rendered_flinkdeployment(repo_root: Path, tenant_id: str, values: dict[str, Any]) -> None:
    run(["helm", "lint", "charts/flink-job"], repo_root)
    rendered = run(
        ["helm", "template", f"{tenant_id}-dev", "charts/flink-job", "-f", f"tenants/{tenant_id}/dev-values.yaml"],
        repo_root,
    )
    documents = [doc for doc in yaml.safe_load_all(rendered) if doc]
    deployments = [doc for doc in documents if doc.get("kind") == "FlinkDeployment"]
    if len(deployments) != 1:
        fail(f"Expected one rendered FlinkDeployment, found {len(deployments)}.")
    deployment = deployments[0]

    expected_image = f"{nested(values, ['image', 'repository'], 'image repository')}:{nested(values, ['image', 'tag'], 'image tag')}"
    if nested(deployment, ["metadata", "namespace"], "FlinkDeployment namespace") != tenant_id:
        fail("Rendered FlinkDeployment namespace does not match tenant.")
    if nested(deployment, ["spec", "image"], "FlinkDeployment image") != expected_image:
        fail("Rendered FlinkDeployment image does not match requested image.")
    if nested(deployment, ["spec", "job", "entryClass"], "FlinkDeployment entryClass") != nested(values, ["job", "className"], "job class"):
        fail("Rendered FlinkDeployment main class does not match requested class.")

    expected_secret = nested(values, ["kafka", "security", "userSecretName"], "Kafka Secret")
    containers = nested(deployment, ["spec", "podTemplate", "spec", "containers"], "podTemplate containers")
    env = containers[0].get("env", [])
    password_env = [item for item in env if item.get("name") == "KAFKA_PASSWORD"]
    if len(password_env) != 1:
        fail("Rendered FlinkDeployment must have one KAFKA_PASSWORD env var.")
    secret_name = nested(password_env[0], ["valueFrom", "secretKeyRef", "name"], "Kafka password secret")
    if secret_name != expected_secret:
        fail("Rendered FlinkDeployment must reference the namespace-local Kafka Secret.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", default="")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="")
    parser.add_argument("--check-git-diff", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    files = changed_files(repo_root, args.base_ref or None, args.head_ref or None)
    tenant_id = args.tenant_id.strip() or infer_tenant_id(files)
    if not TENANT_RE.fullmatch(tenant_id):
        fail("tenant_id must match ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

    if args.check_git_diff:
        validate_change_scope(repo_root, tenant_id, files)

    values = validate_values(repo_root, tenant_id)
    validate_namespace(repo_root, tenant_id)
    validate_rbac(repo_root, tenant_id)
    validate_argocd(repo_root, tenant_id)
    validate_kafka(repo_root, tenant_id, values)
    validate_rendered_flinkdeployment(repo_root, tenant_id, values)
    print(f"Tenant onboarding validation passed for {tenant_id}.")


if __name__ == "__main__":
    main()
