import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.window_identity import identity_matches
from adapters.windows_discovery import _valid


class IdentityTests(unittest.TestCase):
    def test_same_hwnd_with_new_pid_is_rejected(self):
        expected = {"id": 7, "pid": 11, "process_name": "target.exe"}
        current = {"id": 7, "pid": 12, "process_name": "target.exe"}
        self.assertFalse(identity_matches(expected, current))

    def test_legacy_hwnd_only_identity_remains_supported(self):
        self.assertTrue(identity_matches({"id": 7}, {"id": 7, "pid": 12}))

    def test_same_pid_with_new_process_generation_is_rejected(self):
        expected = {"id": 7, "pid": 11, "process_created": 100}
        current = {"id": 7, "pid": 11, "process_created": 200}
        self.assertFalse(identity_matches(expected, current))


class DiscoveryTests(unittest.TestCase):
    def test_valid_requires_exact_basename_and_regular_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "PanGPA.exe"
            path.write_bytes(b"test")
            self.assertEqual(_valid(path, "PanGPA.exe"), path.resolve())
            self.assertIsNone(_valid(path, "CAPAMClient.exe"))
