#!/usr/bin/env python3
"""Validate and update one tenant dev image tag without rewriting YAML."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
TENANT_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


class PromotionError(Exception):
    """Raised when an image promotion request is invalid."""


@dataclass(frozen=True)
class PromotionRequest:
    tenant_id: str
    repository_name: str
    image_repository: str
    image_tag: str
    source_commit_sha: str
    source_repository: str

    @property
    def short_sha(self) -> str:
        return self.image_tag[:12]

    @property
    def image_reference(self) -> str:
        return f"{self.image_repository}:{self.image_tag}"


def validate_sha(value: str, field: str = "image_tag") -> None:
    if not value:
        raise PromotionError(f"{field} is required")
    if value == "latest":
        raise PromotionError(f"{field} must not be latest")
    if not SHA_RE.fullmatch(value):
        raise PromotionError(f"{field} must be a full 40-character lowercase Git SHA")


def validate_tenant_id(tenant_id: str) -> None:
    if not tenant_id or not TENANT_RE.fullmatch(tenant_id):
        raise PromotionError(
            "tenant_id must contain only lowercase letters, numbers, and hyphens"
        )


def normalize_ghcr_repository(repository: str) -> str:
    return repository.lower()


def validate_request(request: PromotionRequest) -> None:
    validate_tenant_id(request.tenant_id)
    validate_sha(request.image_tag, "image_tag")
    validate_sha(request.source_commit_sha, "source_commit_sha")
    if request.image_tag != request.source_commit_sha:
        raise PromotionError("image_tag must match source_commit_sha")
    if not request.repository_name:
        raise PromotionError("repository_name is required")
    normalized_image_repository = normalize_ghcr_repository(request.image_repository)
    normalized_repository_name = request.repository_name.lower()
    if not normalized_image_repository.startswith("ghcr.io/"):
        raise PromotionError("image_repository must be a GHCR repository")
    if normalized_image_repository.rsplit("/", 1)[-1] != normalized_repository_name:
        raise PromotionError("repository_name must match the image repository name")
    if not request.source_repository or "/" not in request.source_repository:
        raise PromotionError("source_repository must be in owner/repository format")


def tenant_dev_values_path(repo_root: Path, tenant_id: str) -> Path:
    validate_tenant_id(tenant_id)
    return repo_root / "tenants" / tenant_id / "dev-values.yaml"


def load_values(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PromotionError(f"{path}: tenant dev-values.yaml does not exist")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise PromotionError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise PromotionError(f"{path}: expected a YAML mapping")
    return data


def configured_image_repository(values: dict[str, Any], path: Path) -> str:
    image = values.get("image")
    if not isinstance(image, dict):
        raise PromotionError(f"{path}: image mapping is required")
    repository = image.get("repository")
    if not repository:
        raise PromotionError(f"{path}: image.repository is required")
    return str(repository)


def configured_image_tag(values: dict[str, Any], path: Path) -> str:
    image = values.get("image")
    if not isinstance(image, dict):
        raise PromotionError(f"{path}: image mapping is required")
    tag = image.get("tag")
    if not tag:
        raise PromotionError(f"{path}: image.tag is required")
    return str(tag)


def update_image_tag_text(original: str, new_tag: str) -> str:
    lines = original.splitlines(keepends=True)
    in_image = False
    image_indent: int | None = None
    replaced = False
    tag_re = re.compile(r"^(\s*tag:\s*)([^#\r\n]*?)(\s*(?:#.*)?)(\r?\n?)$")

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if re.match(r"^image:\s*(?:#.*)?(?:\r?\n)?$", line):
            in_image = True
            image_indent = indent
            continue

        if in_image and image_indent is not None and indent <= image_indent:
            in_image = False
            image_indent = None

        if in_image:
            match = tag_re.match(line)
            if match:
                lines[index] = f"{match.group(1)}{new_tag}{match.group(3)}{match.group(4)}"
                replaced = True
                break

    if not replaced:
        raise PromotionError("image.tag line was not found in dev-values.yaml")
    return "".join(lines)


def update_tenant_image_tag(
    repo_root: Path, request: PromotionRequest, write: bool
) -> tuple[Path, str, bool]:
    validate_request(request)
    values_path = tenant_dev_values_path(repo_root, request.tenant_id)
    values = load_values(values_path)
    actual_repository = configured_image_repository(values, values_path)
    current_tag = configured_image_tag(values, values_path)

    if normalize_ghcr_repository(actual_repository) != normalize_ghcr_repository(
        request.image_repository
    ):
        raise PromotionError(
            f"{values_path}: image.repository is {actual_repository!r}, "
            f"expected {request.image_repository!r}"
        )

    if current_tag == request.image_tag:
        return values_path, current_tag, False

    original = values_path.read_text(encoding="utf-8")
    updated = update_image_tag_text(original, request.image_tag)
    if write:
        values_path.write_text(updated, encoding="utf-8", newline="")
    return values_path, current_tag, True


def plan_existing_promotion_prs(
    existing_prs: list[dict[str, Any]], tenant_id: str, image_tag: str
) -> dict[str, list[dict[str, Any]] | dict[str, Any] | None]:
    short_sha = image_tag[:12]
    prefix = f"promote/{tenant_id}/"
    same_branch = f"{prefix}{short_sha}"
    tenant_prs = [
        pr for pr in existing_prs if str(pr.get("headRefName", "")).startswith(prefix)
    ]
    same_sha = next(
        (pr for pr in tenant_prs if pr.get("headRefName") == same_branch), None
    )
    older = [pr for pr in tenant_prs if pr.get("headRefName") != same_branch]
    return {"same_sha": same_sha, "older": older}


def write_github_output(outputs: dict[str, str]) -> None:
    env_path = __import__("os").environ.get("GITHUB_OUTPUT")
    if env_path:
        with Path(env_path).open("a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")


def request_from_args(args: argparse.Namespace) -> PromotionRequest:
    return PromotionRequest(
        tenant_id=args.tenant_id,
        repository_name=args.repository_name,
        image_repository=args.image_repository,
        image_tag=args.image_tag,
        source_commit_sha=args.source_commit_sha,
        source_repository=args.source_repository,
    )


def command_promote(args: argparse.Namespace) -> int:
    request = request_from_args(args)
    values_path, previous_tag, changed = update_tenant_image_tag(
        Path(args.repo_root), request, args.write
    )
    outputs = {
        "tenant_id": request.tenant_id,
        "short_sha": request.short_sha,
        "values_file": values_path.as_posix(),
        "previous_tag": previous_tag,
        "image_reference": request.image_reference,
        "changed": str(changed).lower(),
    }
    write_github_output(outputs)
    print(json.dumps(outputs, indent=2))
    return 0


def command_plan_prs(args: argparse.Namespace) -> int:
    validate_tenant_id(args.tenant_id)
    validate_sha(args.image_tag, "image_tag")
    existing = json.loads(Path(args.existing_prs_json).read_text(encoding="utf-8"))
    plan = plan_existing_promotion_prs(existing, args.tenant_id, args.image_tag)
    outputs = {
        "same_sha": "true" if plan["same_sha"] else "false",
        "older_numbers": ",".join(str(pr["number"]) for pr in plan["older"]),
        "older_branches": ",".join(str(pr["headRefName"]) for pr in plan["older"]),
    }
    write_github_output(outputs)
    print(json.dumps(outputs, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(required=True)

    promote = subparsers.add_parser("promote")
    promote.add_argument("--repo-root", default=".")
    promote.add_argument("--tenant-id", required=True)
    promote.add_argument("--repository-name", required=True)
    promote.add_argument("--image-repository", required=True)
    promote.add_argument("--image-tag", required=True)
    promote.add_argument("--source-commit-sha", required=True)
    promote.add_argument("--source-repository", required=True)
    promote.add_argument("--write", action="store_true")
    promote.set_defaults(func=command_promote)

    plan_prs = subparsers.add_parser("plan-prs")
    plan_prs.add_argument("--tenant-id", required=True)
    plan_prs.add_argument("--image-tag", required=True)
    plan_prs.add_argument("--existing-prs-json", required=True)
    plan_prs.set_defaults(func=command_plan_prs)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (PromotionError, json.JSONDecodeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
