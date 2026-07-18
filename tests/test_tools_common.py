import tempfile
import unittest
from pathlib import Path

from tools.common import capture_allowed, create_run_dir


class ToolsCommonTests(unittest.TestCase):
    def test_sensitive_stages_are_blocked_by_default(self):
        self.assertFalse(capture_allowed("gp-credentials", False))
        self.assertFalse(capture_allowed("capam-login", False))
        self.assertFalse(capture_allowed("windows-security", False))
        self.assertTrue(capture_allowed("device-list", False))

    def test_explicit_sensitive_capture_is_allowed(self):
        self.assertTrue(capture_allowed("capam-login", True))

    def test_run_directories_are_unique(self):
        with tempfile.TemporaryDirectory() as root:
            first = create_run_dir(root)
            second = create_run_dir(root)
            self.assertNotEqual(first, second)
            self.assertTrue(Path(first).is_dir())
            self.assertTrue(Path(second).is_dir())


if __name__ == "__main__":
    unittest.main()
