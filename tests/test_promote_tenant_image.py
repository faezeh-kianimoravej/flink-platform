from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github" / "scripts"))

from promote_tenant_image import (  # noqa: E402
    PromotionError,
    PromotionRequest,
    plan_existing_promotion_prs,
    update_tenant_image_tag,
    validate_sha,
)


VALID_SHA = "0123456789abcdef0123456789abcdef01234567"
OLDER_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class PromoteTenantImageTests(unittest.TestCase):
    def make_repo(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        tenant_dir = root / "tenants" / "tenant-a"
        tenant_dir.mkdir(parents=True)
        (tenant_dir / "test-values.yaml").write_text("image:\n  tag: keep-test\n")
        (tenant_dir / "prod-values.yaml").write_text("image:\n  tag: keep-prod\n")
        (tenant_dir / "dev-values.yaml").write_text(
            "\n".join(
                [
                    "tenantName: tenant-a",
                    "namespace: tenant-a",
                    "",
                    "image:",
                    "  repository: ghcr.io/acme/tenant-a-flink-job",
                    "  # keep this comment",
                    f"  tag: {OLDER_SHA}",
                    "  pullPolicy: IfNotPresent",
                    "",
                    "job:",
                    "  className: com.example.Job",
                    "  jarURI: local:///opt/flink/usrlib/job.jar",
                    "",
                ]
            )
        )
        return temp_dir, root

    def request(self, image_tag: str = VALID_SHA) -> PromotionRequest:
        return PromotionRequest(
            tenant_id="tenant-a",
            repository_name="tenant-a-flink-job",
            image_repository="ghcr.io/acme/tenant-a-flink-job",
            image_tag=image_tag,
            source_commit_sha=image_tag,
            source_repository="acme/tenant-a-flink-job",
        )

    def request_with_repository(
        self,
        image_repository: str,
        repository_name: str = "tenant-a-flink-job",
        image_tag: str = VALID_SHA,
    ) -> PromotionRequest:
        return PromotionRequest(
            tenant_id="tenant-a",
            repository_name=repository_name,
            image_repository=image_repository,
            image_tag=image_tag,
            source_commit_sha=image_tag,
            source_repository="acme/tenant-a-flink-job",
        )

    def test_valid_sha_is_accepted(self) -> None:
        validate_sha(VALID_SHA)

    def test_latest_is_rejected(self) -> None:
        with self.assertRaises(PromotionError):
            validate_sha("latest")

    def test_malformed_sha_is_rejected(self) -> None:
        with self.assertRaises(PromotionError):
            validate_sha("v1.2.3")

    def test_missing_tenant_is_rejected(self) -> None:
        temp_dir, root = self.make_repo()
        with temp_dir:
            request = PromotionRequest(
                tenant_id="tenant-missing",
                repository_name="tenant-a-flink-job",
                image_repository="ghcr.io/acme/tenant-a-flink-job",
                image_tag=VALID_SHA,
                source_commit_sha=VALID_SHA,
                source_repository="acme/tenant-a-flink-job",
            )
            with self.assertRaises(PromotionError):
                update_tenant_image_tag(root, request, write=True)

    def test_repository_mismatch_is_rejected(self) -> None:
        temp_dir, root = self.make_repo()
        with temp_dir:
            request = PromotionRequest(
                tenant_id="tenant-a",
                repository_name="other-job",
                image_repository="ghcr.io/acme/other-job",
                image_tag=VALID_SHA,
                source_commit_sha=VALID_SHA,
                source_repository="acme/tenant-a-flink-job",
            )
            with self.assertRaises(PromotionError):
                update_tenant_image_tag(root, request, write=True)

    def test_owner_casing_difference_is_accepted(self) -> None:
        temp_dir, root = self.make_repo()
        with temp_dir:
            request = self.request_with_repository(
                "ghcr.io/ACME/tenant-a-flink-job"
            )
            update_tenant_image_tag(root, request, write=True)

    def test_repository_name_casing_difference_is_accepted(self) -> None:
        temp_dir, root = self.make_repo()
        with temp_dir:
            request = self.request_with_repository(
                "ghcr.io/acme/Tenant-A-Flink-Job",
                repository_name="Tenant-A-Flink-Job",
            )
            update_tenant_image_tag(root, request, write=True)

    def test_genuinely_different_repository_is_rejected(self) -> None:
        temp_dir, root = self.make_repo()
        with temp_dir:
            request = self.request_with_repository(
                "ghcr.io/acme/tenant-c-flink-job",
                repository_name="tenant-c-flink-job",
            )
            with self.assertRaises(PromotionError):
                update_tenant_image_tag(root, request, write=True)

    def test_repository_value_is_not_rewritten(self) -> None:
        temp_dir, root = self.make_repo()
        with temp_dir:
            dev_file = root / "tenants" / "tenant-a" / "dev-values.yaml"
            original_repository_line = (
                "  repository: ghcr.io/acme/tenant-a-flink-job"
            )
            request = self.request_with_repository(
                "ghcr.io/ACME/Tenant-A-Flink-Job",
                repository_name="Tenant-A-Flink-Job",
            )
            update_tenant_image_tag(root, request, write=True)
            updated = dev_file.read_text()
            self.assertIn(original_repository_line, updated)
            self.assertNotIn("repository: ghcr.io/ACME/Tenant-A-Flink-Job", updated)

    def test_only_dev_values_change_and_unrelated_yaml_is_preserved(self) -> None:
        temp_dir, root = self.make_repo()
        with temp_dir:
            test_file = root / "tenants" / "tenant-a" / "test-values.yaml"
            prod_file = root / "tenants" / "tenant-a" / "prod-values.yaml"
            dev_file = root / "tenants" / "tenant-a" / "dev-values.yaml"
            test_before = test_file.read_text()
            prod_before = prod_file.read_text()

            values_path, previous_tag, changed = update_tenant_image_tag(
                root, self.request(), write=True
            )

            self.assertEqual(values_path, dev_file)
            self.assertEqual(previous_tag, OLDER_SHA)
            self.assertTrue(changed)
            self.assertEqual(test_file.read_text(), test_before)
            self.assertEqual(prod_file.read_text(), prod_before)
            updated = dev_file.read_text()
            self.assertIn("  # keep this comment", updated)
            self.assertIn(f"  tag: {VALID_SHA}", updated)
            self.assertNotIn(OLDER_SHA, updated)

    def test_duplicate_promotion_is_idempotent(self) -> None:
        prs = [
            {
                "number": 10,
                "headRefName": f"promote/tenant-a/{VALID_SHA[:12]}",
                "url": "https://example.test/pr/10",
            }
        ]
        plan = plan_existing_promotion_prs(prs, "tenant-a", VALID_SHA)
        self.assertIsNotNone(plan["same_sha"])
        self.assertEqual(plan["older"], [])

    def test_outdated_promotion_is_marked_for_replacement(self) -> None:
        prs = [
            {
                "number": 11,
                "headRefName": f"promote/tenant-a/{OLDER_SHA[:12]}",
                "url": "https://example.test/pr/11",
            },
            {
                "number": 12,
                "headRefName": f"promote/tenant-b/{OLDER_SHA[:12]}",
                "url": "https://example.test/pr/12",
            },
        ]
        plan = plan_existing_promotion_prs(prs, "tenant-a", VALID_SHA)
        self.assertIsNone(plan["same_sha"])
        self.assertEqual([pr["number"] for pr in plan["older"]], [11])


if __name__ == "__main__":
    unittest.main()
