import unittest
from pathlib import Path

from actintrack_app import paths
from actintrack_app.__version__ import __version__


class VersionTest(unittest.TestCase):
    def test_version_is_nonempty_string(self) -> None:
        self.assertIsInstance(__version__, str)
        self.assertTrue(__version__.strip())

    def test_version_has_dotted_parts(self) -> None:
        self.assertGreaterEqual(len(__version__.split(".")), 2)


class IconResourceTest(unittest.TestCase):
    def test_icon_path_returns_path_or_none(self) -> None:
        result = paths.icon_path()
        self.assertTrue(result is None or isinstance(result, Path))

    def test_icon_path_resolves_under_resource_root(self) -> None:
        result = paths.icon_path()
        if result is not None:
            self.assertTrue(result.is_file())
            self.assertTrue(
                str(result).startswith(str(paths.resource_root())),
                msg="icon should resolve under resource_root()",
            )

    def test_bundled_png_icon_is_present(self) -> None:
        png = paths.resource_path("packaging", "assets", "app", "actintrackcv.png")
        self.assertTrue(png.is_file(), msg=f"expected app icon at {png}")

    def test_icon_path_resolves_to_app_png(self) -> None:
        result = paths.icon_path()
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "actintrackcv.png")
        self.assertEqual(result.parent.name, "app")


if __name__ == "__main__":
    unittest.main()
