import unittest
from pathlib import Path
from unittest import mock

from actintrack_app import paths


class PathHelpersTest(unittest.TestCase):
    def test_not_frozen_in_development(self) -> None:
        self.assertFalse(paths.is_frozen())

    def test_app_root_contains_package(self) -> None:
        self.assertTrue((paths.app_root() / "actintrack_app").is_dir())

    def test_resource_root_is_app_root_in_development(self) -> None:
        self.assertEqual(paths.resource_root(), paths.app_root())

    def test_resource_path_joins_under_resource_root(self) -> None:
        self.assertEqual(
            paths.resource_path("README.md"),
            paths.resource_root() / "README.md",
        )

    def test_default_source_root_prefers_documents(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "Documents").mkdir()
            with mock.patch("pathlib.Path.home", return_value=home):
                self.assertEqual(paths.default_source_root(), home / "Documents")

    def test_default_source_root_falls_back_to_home(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with mock.patch("pathlib.Path.home", return_value=home):
                self.assertEqual(paths.default_source_root(), home)

    def test_default_workspace_uses_documents_when_present(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "Documents").mkdir()
            with mock.patch("pathlib.Path.home", return_value=home):
                root = paths.default_workspace_root()
                self.assertEqual(root, home / "Documents" / paths.WORKSPACE_DIR_NAME)
                self.assertTrue(root.is_dir())

    def test_default_workspace_falls_back_without_documents(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with mock.patch("pathlib.Path.home", return_value=home):
                root = paths.default_workspace_root()
                self.assertEqual(root, home / paths.WORKSPACE_DIR_NAME)
                self.assertTrue(root.is_dir())

    def test_default_workspace_is_not_app_install_dir(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with mock.patch("pathlib.Path.home", return_value=home):
                self.assertNotEqual(paths.default_workspace_root(), paths.app_root())


if __name__ == "__main__":
    unittest.main()
