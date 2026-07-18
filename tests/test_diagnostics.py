import json
import tempfile
import unittest
from pathlib import Path

from diagnostics.timeline import TimelineWriter, redact
from tools.monitor_flow import _collect_values, _count_nodes


class TimelineTests(unittest.TestCase):
    def test_redacts_sensitive_keys_otp_and_known_secrets(self):
        value = redact(
            {
                "password": "unsafe",
                "message": "OTP 123456 and full secret-prefix123456",
            },
            ("secret-prefix", "secret-prefix123456"),
        )
        self.assertEqual(value["password"], "<redacted>")
        self.assertNotIn("123456", value["message"])
        self.assertNotIn("secret-prefix", value["message"])

    def test_writer_emits_ordered_jsonl(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "timeline.jsonl"
            writer = TimelineWriter(path, "test", "session", secrets=("private",))
            writer.emit("first", message="private")
            writer.emit("second", otp="123456")
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["sequence"] for record in records], [1, 2])
            self.assertEqual(records[0]["data"]["message"], "<redacted>")
            self.assertEqual(records[1]["data"]["otp"], "<redacted>")

    def test_monitor_mode_preserves_hash_digits(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "timeline.jsonl"
            writer = TimelineWriter(path, "monitor", "session", redact_otp=False)
            writer.emit("observation", fingerprint="abc123456def")
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["data"]["fingerprint"], "abc123456def")


class MonitorTreeTests(unittest.TestCase):
    def test_tree_helpers_collect_metadata(self):
        tree = [{"role": "dialog", "children": [{"role": "text", "name": "Username"}]}]
        self.assertEqual(_count_nodes(tree), 2)
        self.assertEqual(_collect_values(tree, "role"), {"dialog", "text"})
        self.assertEqual(_collect_values(tree, "name"), {"Username"})


if __name__ == "__main__":
    unittest.main()
