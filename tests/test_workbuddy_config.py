import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/configure_workbuddy.py"
spec = importlib.util.spec_from_file_location("workbuddy_config", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WorkBuddyConfigTests(unittest.TestCase):
    def test_apply_preserves_other_services_and_backs_up(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, output = root / "mcp.json", root / "generated.json"
            original = {"mcpServers": {"other": {"command": "existing", "env": {"TOKEN": "test-secret"}}}, "custom": True}
            target.write_text(json.dumps(original))
            with patch.object(sys, "argv", [str(SCRIPT), "--apply", "--config", str(target), "--output", str(output)]):
                module.main()
            data = json.loads(target.read_text())
            self.assertEqual(data["mcpServers"]["other"], original["mcpServers"]["other"])
            self.assertTrue(data["custom"])
            self.assertIn("privacyguard", data["mcpServers"])
            backups = list(root.glob("mcp.json.privacyguard-backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text()), original)
            with patch.object(sys, "argv", [str(SCRIPT), "--apply", "--config", str(target), "--output", str(output)]):
                module.main()
            self.assertEqual(len(list(root.glob("mcp.json.privacyguard-backup-*"))), 1)

    def test_generated_entry_is_path_expanded_and_ready_for_mcp_servers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper, entry = root / "wrapper.json", root / "entry.json"
            with patch.object(sys, "argv", [str(SCRIPT), "--output", str(wrapper), "--entry-output", str(entry)]):
                module.main()
            expected = json.loads(wrapper.read_text())["mcpServers"]["privacyguard"]
            pasted = json.loads("{" + entry.read_text() + "}")
            self.assertEqual(pasted["privacyguard"], expected)
            self.assertNotIn("YOUR_NAME", entry.read_text())
            self.assertTrue(expected["command"].startswith("/"))
            self.assertEqual(entry.stat().st_mode & 0o777, 0o600)

    def test_conflict_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "mcp.json"
            raw = '{"mcpServers":{"privacyguard":{"command":"user-owned"}}}'
            target.write_text(raw)
            with patch.object(sys, "argv", [str(SCRIPT), "--apply", "--config", str(target), "--output", str(Path(directory)/"generated.json")]):
                with self.assertRaises(SystemExit):
                    module.main()
            self.assertEqual(target.read_text(), raw)


if __name__ == "__main__":
    unittest.main()
