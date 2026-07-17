from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github" / "scripts"))

from validate_platform import (  # noqa: E402
    ValidationError,
    validate_rendered_flinkdeployment,
)


VALID_SHA = "0123456789abcdef0123456789abcdef01234567"


class PlatformValidationTests(unittest.TestCase):
    def write_manifest(self, path: Path, image_tag: str = VALID_SHA) -> None:
        path.write_text(
            "\n".join(
                [
                    "apiVersion: flink.apache.org/v1beta1",
                    "kind: FlinkDeployment",
                    "metadata:",
                    "  name: tenant-a-flink-job",
                    "  namespace: tenant-a",
                    "spec:",
                    f"  image: ghcr.io/acme/tenant-a-flink-job:{image_tag}",
                    "  job:",
                    "    jarURI: local:///opt/flink/usrlib/job.jar",
                    "    entryClass: com.example.Job",
                    "",
                ]
            )
        )

    def test_rendered_flinkdeployment_with_valid_sha_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "rendered.yaml"
            values = Path(temp_dir) / "dev-values.yaml"
            values.write_text("")
            self.write_manifest(manifest)
            validate_rendered_flinkdeployment(manifest, values)

    def test_dev_placeholder_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "rendered.yaml"
            values = Path(temp_dir) / "dev-values.yaml"
            values.write_text("")
            self.write_manifest(manifest, "TODO_REPLACE_WITH_TENANT_A_COMMIT_SHA")
            with self.assertRaises(ValidationError):
                validate_rendered_flinkdeployment(manifest, values)

    def test_dev_latest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "rendered.yaml"
            values = Path(temp_dir) / "dev-values.yaml"
            values.write_text("")
            self.write_manifest(manifest, "latest")
            with self.assertRaises(ValidationError):
                validate_rendered_flinkdeployment(manifest, values)

    def test_rendered_flinkdeployment_rejects_malformed_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "rendered.yaml"
            values = Path(temp_dir) / "dev-values.yaml"
            values.write_text("")
            self.write_manifest(manifest, "v1.2.3")
            with self.assertRaises(ValidationError):
                validate_rendered_flinkdeployment(manifest, values)

    def test_test_placeholder_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "rendered.yaml"
            values = Path(temp_dir) / "test-values.yaml"
            values.write_text("")
            self.write_manifest(manifest, "TODO_REPLACE_WITH_TENANT_A_COMMIT_SHA")
            validate_rendered_flinkdeployment(manifest, values)

    def test_prod_valid_sha_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "rendered.yaml"
            values = Path(temp_dir) / "prod-values.yaml"
            values.write_text("")
            self.write_manifest(manifest, VALID_SHA)
            validate_rendered_flinkdeployment(manifest, values)

    def test_test_latest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "rendered.yaml"
            values = Path(temp_dir) / "test-values.yaml"
            values.write_text("")
            self.write_manifest(manifest, "latest")
            with self.assertRaises(ValidationError):
                validate_rendered_flinkdeployment(manifest, values)

    def test_prod_malformed_tag_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "rendered.yaml"
            values = Path(temp_dir) / "prod-values.yaml"
            values.write_text("")
            self.write_manifest(manifest, "v1.2.3")
            with self.assertRaises(ValidationError):
                validate_rendered_flinkdeployment(manifest, values)

    def test_prod_arbitrary_placeholder_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "rendered.yaml"
            values = Path(temp_dir) / "prod-values.yaml"
            values.write_text("")
            self.write_manifest(manifest, "TODO_SHA")
            with self.assertRaises(ValidationError):
                validate_rendered_flinkdeployment(manifest, values)

    def test_every_values_file_renders(self) -> None:
        root = Path(__file__).resolve().parents[1]
        values_files = sorted(root.glob("tenants/*/*-values.yaml"))
        self.assertGreater(len(values_files), 0)
        for values_file in values_files:
            result = subprocess.run(
                [
                    "helm",
                    "template",
                    values_file.parent.name,
                    "charts/flink-job",
                    "-f",
                    str(values_file),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with tempfile.TemporaryDirectory() as temp_dir:
                manifest = Path(temp_dir) / "rendered.yaml"
                manifest.write_text(result.stdout)
                validate_rendered_flinkdeployment(manifest, values_file)

    def test_invalid_helm_values_fail_render_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "rendered.yaml"
            values = Path(temp_dir) / "dev-values.yaml"
            values.write_text("")
            self.write_manifest(manifest, "not-a-sha")
            with self.assertRaises(ValidationError):
                validate_rendered_flinkdeployment(manifest, values)


if __name__ == "__main__":
    unittest.main()
