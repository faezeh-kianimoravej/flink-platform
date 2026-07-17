#!/usr/bin/env python3
"""Platform validation helpers for rendered Helm output and GitOps YAML."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DOCUMENTED_PLACEHOLDER_RE = re.compile(r"^TODO_REPLACE_WITH_[A-Z0-9_]+_COMMIT_SHA$")


class ValidationError(Exception):
    """Raised when platform validation fails."""


def fail(message: str) -> None:
    raise ValidationError(message)


def load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            documents = list(yaml.safe_load_all(handle))
    except yaml.YAMLError as exc:
        fail(f"{path}: invalid YAML: {exc}")
    except OSError as exc:
        fail(f"{path}: cannot read file: {exc}")

    return [doc for doc in documents if isinstance(doc, dict)]


def yaml_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix in {".yaml", ".yml"}:
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.yaml")))
            files.extend(sorted(path.rglob("*.yml")))
        else:
            fail(f"{path}: path does not exist")
    return sorted(set(files))


def parse_image(image: str) -> tuple[str, str]:
    if not image or ":" not in image:
        fail("FlinkDeployment spec.image must include repository and tag")
    repository, tag = image.rsplit(":", 1)
    if not repository:
        fail("FlinkDeployment image repository is empty")
    if not tag:
        fail("FlinkDeployment image tag is empty")
    return repository, tag


def environment_from_values_file(values_file: Path | None) -> str:
    if values_file is None:
        return "dev"
    name = values_file.name
    if name == "dev-values.yaml":
        return "dev"
    if name == "test-values.yaml":
        return "test"
    if name == "prod-values.yaml":
        return "prod"
    fail(f"{values_file}: expected dev-values.yaml, test-values.yaml, or prod-values.yaml")
    return "dev"


def validate_image_tag(tag: str, environment: str, context: str) -> None:
    if tag == "latest":
        fail(f"{context}: image tag must not be latest")
    if environment == "dev":
        if not SHA_RE.fullmatch(tag):
            fail(f"{context}: dev image tag must be a full 40-character lowercase Git SHA")
        return
    if DOCUMENTED_PLACEHOLDER_RE.fullmatch(tag):
        return
    if not SHA_RE.fullmatch(tag):
        fail(
            f"{context}: {environment} image tag must be either a documented "
            "TODO_REPLACE_WITH_*_COMMIT_SHA placeholder or a full 40-character "
            "lowercase Git SHA"
        )


def validate_flinkdeployment(
    document: dict[str, Any], source: Path, environment: str = "dev"
) -> None:
    metadata = document.get("metadata") or {}
    spec = document.get("spec") or {}
    job = spec.get("job") or {}

    namespace = metadata.get("namespace")
    if not namespace:
        fail(f"{source}: FlinkDeployment metadata.namespace is required")

    image = spec.get("image")
    if not isinstance(image, str):
        fail(f"{source}: FlinkDeployment spec.image is required")

    _repository, tag = parse_image(image)
    validate_image_tag(tag, environment, f"{source}: FlinkDeployment")

    if not job.get("jarURI"):
        fail(f"{source}: FlinkDeployment spec.job.jarURI is required")
    if not job.get("entryClass"):
        fail(f"{source}: FlinkDeployment spec.job.entryClass is required")


def validate_rendered_flinkdeployment(
    manifest: Path, values_file: Path | None = None
) -> None:
    environment = environment_from_values_file(values_file)
    documents = load_yaml_documents(manifest)
    flink_deployments = [
        doc for doc in documents if doc.get("kind") == "FlinkDeployment"
    ]
    if len(flink_deployments) != 1:
        fail(
            f"{manifest}: expected exactly one FlinkDeployment, "
            f"found {len(flink_deployments)}"
        )
    validate_flinkdeployment(flink_deployments[0], manifest, environment)


def validate_argocd_application(document: dict[str, Any], source: Path) -> None:
    metadata = document.get("metadata") or {}
    spec = document.get("spec") or {}
    source_spec = spec.get("source") or {}
    destination = spec.get("destination") or {}

    if not metadata.get("name"):
        fail(f"{source}: Argo CD Application metadata.name is required")
    if metadata.get("namespace") != "argocd":
        fail(f"{source}: Argo CD Application must live in the argocd namespace")
    if not source_spec.get("repoURL"):
        fail(f"{source}: Argo CD Application spec.source.repoURL is required")
    if not source_spec.get("targetRevision"):
        fail(f"{source}: Argo CD Application spec.source.targetRevision is required")
    if not source_spec.get("path"):
        fail(f"{source}: Argo CD Application spec.source.path is required")
    value_files = ((source_spec.get("helm") or {}).get("valueFiles") or [])
    if not value_files:
        fail(f"{source}: Argo CD Application must reference Helm valueFiles")
    if not destination.get("namespace"):
        fail(f"{source}: Argo CD Application spec.destination.namespace is required")
    if not destination.get("server"):
        fail(f"{source}: Argo CD Application spec.destination.server is required")


def validate_kafka_topic(document: dict[str, Any], source: Path) -> None:
    metadata = document.get("metadata") or {}
    labels = metadata.get("labels") or {}
    spec = document.get("spec") or {}

    if not metadata.get("name"):
        fail(f"{source}: KafkaTopic metadata.name is required")
    if metadata.get("namespace") != "kafka-system":
        fail(f"{source}: KafkaTopic must live in kafka-system")
    if not labels.get("strimzi.io/cluster"):
        fail(f"{source}: KafkaTopic must declare strimzi.io/cluster")
    if not isinstance(spec.get("partitions"), int) or spec["partitions"] < 1:
        fail(f"{source}: KafkaTopic spec.partitions must be a positive integer")
    if not isinstance(spec.get("replicas"), int) or spec["replicas"] < 1:
        fail(f"{source}: KafkaTopic spec.replicas must be a positive integer")


def validate_kafka_user(document: dict[str, Any], source: Path) -> None:
    metadata = document.get("metadata") or {}
    labels = metadata.get("labels") or {}
    spec = document.get("spec") or {}
    auth = spec.get("authentication") or {}
    authorization = spec.get("authorization") or {}

    if not metadata.get("name"):
        fail(f"{source}: KafkaUser metadata.name is required")
    if metadata.get("namespace") != "kafka-system":
        fail(f"{source}: KafkaUser must live in kafka-system")
    if not labels.get("strimzi.io/cluster"):
        fail(f"{source}: KafkaUser must declare strimzi.io/cluster")
    if not auth.get("type"):
        fail(f"{source}: KafkaUser spec.authentication.type is required")
    if not authorization.get("type"):
        fail(f"{source}: KafkaUser spec.authorization.type is required")
    if not isinstance(authorization.get("acls"), list) or not authorization["acls"]:
        fail(f"{source}: KafkaUser spec.authorization.acls must be a non-empty list")


def validate_semantics(files: Iterable[Path]) -> None:
    validators = {
        "Application": validate_argocd_application,
        "FlinkDeployment": validate_flinkdeployment,
        "KafkaTopic": validate_kafka_topic,
        "KafkaUser": validate_kafka_user,
    }
    for path in files:
        for document in load_yaml_documents(path):
            validator = validators.get(document.get("kind"))
            if validator:
                validator(document, path)


def validate_yaml_syntax(files: Iterable[Path]) -> None:
    for path in files:
        load_yaml_documents(path)


def command_validate_rendered(args: argparse.Namespace) -> int:
    values_file = Path(args.values_file) if args.values_file else None
    validate_rendered_flinkdeployment(Path(args.manifest), values_file)
    return 0


def command_validate_yaml(args: argparse.Namespace) -> int:
    files = yaml_files(Path(path) for path in args.paths)
    validate_yaml_syntax(files)
    print(f"Validated YAML syntax for {len(files)} files.")
    return 0


def command_validate_semantics(args: argparse.Namespace) -> int:
    files = yaml_files(Path(path) for path in args.paths)
    validate_semantics(files)
    print(f"Validated platform semantics for {len(files)} files.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(required=True)

    rendered = subparsers.add_parser(
        "validate-rendered", help="Validate one rendered Helm manifest."
    )
    rendered.add_argument("--manifest", required=True)
    rendered.add_argument("--values-file")
    rendered.set_defaults(func=command_validate_rendered)

    yaml_parser = subparsers.add_parser(
        "validate-yaml", help="Parse YAML syntax under files or directories."
    )
    yaml_parser.add_argument("paths", nargs="+")
    yaml_parser.set_defaults(func=command_validate_yaml)

    semantics = subparsers.add_parser(
        "validate-semantics", help="Run semantic checks for platform CRDs."
    )
    semantics.add_argument("paths", nargs="+")
    semantics.set_defaults(func=command_validate_semantics)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ValidationError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
