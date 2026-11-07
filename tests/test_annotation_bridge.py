"""The frame app can run without the separately installed annotation package."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from strawframe.annotation_bridge import annotation_command


class AnnotationBridgeTests(unittest.TestCase):
    def test_source_launcher_keeps_paths_with_spaces_as_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            script = root / "标注 工作台" / "annotate.py"
            script.parent.mkdir()
            script.touch()
            command = annotation_command(root / "图片 目录", root / "标注 结果", script)
            self.assertEqual(command[:2], [sys.executable, str(script)])
            self.assertEqual(
                command[2:],
                ["--images", str(root / "图片 目录"), "--output", str(root / "标注 结果")],
            )

    def test_missing_separate_app_is_actionable(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                annotation_command(folder, folder, Path(folder) / "missing.py")

    def test_frozen_frame_app_uses_python_launcher_for_source(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder).resolve() / "annotate.py"
            script.touch()
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "platform", "win32"),
                patch("strawframe.annotation_bridge.shutil.which", return_value="C:/Python/py.exe"),
            ):
                command = annotation_command(folder, folder, script)
            self.assertEqual(command[:3], ["C:/Python/py.exe", "-3", str(script)])

    def test_standalone_binary_does_not_require_python(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder).resolve() / "StrawAnnotationStudio.exe"
            binary.touch()
            with patch.object(sys, "frozen", True, create=True):
                self.assertEqual(annotation_command(folder, folder, binary)[0], str(binary))


if __name__ == "__main__":
    unittest.main()
