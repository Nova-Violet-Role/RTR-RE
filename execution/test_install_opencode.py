# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import install_opencode


class TestInstallOpencode(unittest.TestCase):
    def test_asset_resolves_and_is_the_keeper(self):
        asset = install_opencode.keeper_asset_path()
        self.assertTrue(asset.exists())
        body = asset.read_text(encoding="utf-8")
        self.assertIn("experimental.chat.messages.transform", body)
        self.assertIn("export default server", body)

    def test_install_copies_byte_identical_and_reports(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "opencode"
            result = install_opencode.install(cfg)
            dest = cfg / "plugin" / "rtr-re-keeper.js"
            self.assertTrue(dest.exists())
            self.assertEqual(
                dest.read_bytes(),
                install_opencode.keeper_asset_path().read_bytes(),
            )
            self.assertEqual(Path(result["plugin"]), dest)
            self.assertGreater(result["bytes"], 1000)

    def test_install_also_installs_preset_registry(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "opencode"
            result = install_opencode.install(cfg)
            reg = Path(result["registry"])
            self.assertTrue(reg.exists())
            self.assertEqual(
                reg.read_bytes(),
                install_opencode.registry_asset_path().read_bytes(),
            )

    def test_install_refuses_to_clobber_differing_file_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "opencode"
            install_opencode.install(cfg)
            dest = cfg / "plugin" / "rtr-re-keeper.js"
            dest.write_bytes(b"locally modified")
            with self.assertRaises(FileExistsError):
                install_opencode.install(cfg)
            install_opencode.install(cfg, force=True)
            self.assertNotEqual(dest.read_bytes(), b"locally modified")

    def test_snippet_wires_plugin_and_mcp_without_acp(self):
        snippet = install_opencode.config_snippet()
        self.assertIn("./plugin/rtr-re-keeper.js", snippet)
        self.assertIn("rtr-re-mcp", snippet)
        self.assertNotIn("acp", snippet.lower())

    def test_main_returns_2_on_clobber_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "opencode"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install_opencode.main(["--config-dir", str(cfg)]), 0)
                dest = cfg / "plugin" / "rtr-re-keeper.js"
                dest.write_bytes(b"changed")
                self.assertEqual(install_opencode.main(["--config-dir", str(cfg)]), 2)


if __name__ == "__main__":
    unittest.main()
