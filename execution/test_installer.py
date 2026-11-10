# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from installer.launchers.python_launcher import (
    animate_params,
    execute_plan,
    linux_player_cmd,
    plan_for,
    read_scene,
    validated_int,
    windows_media_command,
)


class PlanForTest(unittest.TestCase):
    def test_quick_plan(self):
        self.assertEqual(
            plan_for({"preset": "quick"}),
            [
                ("preset", "re-symbiose-mugen (400k/200k/200)"),
                ("engine", "rtr-full · dual-ONNX"),
                ("profile", "local-system · T8/P80"),
                ("plugin", "keeper + ctrl+p palette"),
                ("memory", ".opencode/memory/ (DTD-shaped)"),
            ],
        )

    def test_custom_plan(self):
        plan = plan_for({"preset": "custom", "components": ["cli", "plugin"]})
        self.assertEqual(plan[0], ("components", "cli, plugin"))
        self.assertEqual(len(plan), 5)

    def test_hardcore_plan(self):
        plan = plan_for(
            {
                "preset": "hardcore",
                "presetName": "re-symbiose-mugen",
                "threads": 8,
                "parking": 40,
                "modality": "rtr-full",
            }
        )
        self.assertEqual(
            plan,
            [
                ("preset", "re-symbiose-mugen"),
                ("threads", "8"),
                ("parking", "40%"),
                ("modality", "rtr-full"),
                ("engine", "rtr-full · dual-ONNX"),
                ("plugin", "keeper + ctrl+p palette"),
                ("memory", ".opencode/memory/ (DTD-shaped)"),
            ],
        )


class ExecutePlanTest(unittest.TestCase):
    def test_writes_keeper_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            ok = execute_plan({"preset": "quick"}, str(project), None)
            self.assertTrue(ok)
            cfg = json.loads(
                (project / ".opencode" / "rtr-re-keeper.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(cfg["preset"], "re-symbiose-mugen")
            self.assertEqual(cfg["cpuProfile"], "local-system")
            self.assertTrue(cfg["enabled"])

    def test_pip_failure_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "bogus.whl"
            wheel.write_text("not a wheel", encoding="utf-8")
            project = Path(tmp) / "proj"
            ok = execute_plan({"preset": "quick"}, str(project), str(wheel))
            self.assertFalse(ok)
            self.assertTrue((project / ".opencode" / "rtr-re-keeper.json").exists())


class LinuxPlayerTest(unittest.TestCase):
    def test_chain_prefers_mpg123_then_mpv_then_ffplay(self):
        with mock.patch("installer.launchers.python_launcher.shutil.which") as which:
            which.side_effect = lambda n: f"/usr/bin/{n}"
            self.assertEqual(linux_player_cmd("x.mp3")[0], "mpg123")
            which.side_effect = lambda n: "/usr/bin/mpv" if n == "mpv" else None
            cmd = linux_player_cmd("x.mp3")
            self.assertEqual(cmd[0], "mpv")
            self.assertIn("--no-video", cmd)
            which.side_effect = lambda n: None
            self.assertIsNone(linux_player_cmd("x.mp3"))


class WindowsMediaTest(unittest.TestCase):
    def test_command_keeps_host_alive_for_track(self):
        cmd = windows_media_command("C:/x/obsession-quick.mp3")
        self.assertIn("WMPlayer.OCX", cmd)
        self.assertIn("playState", cmd)
        self.assertIn("C:/x/obsession-quick.mp3", cmd)


class AnimateParamsTest(unittest.TestCase):
    def test_instrument_baseline(self):
        p = animate_params({"particles": {"count": 900, "speed": 0.6, "mix": 0.6}})
        self.assertAlmostEqual(p["density"], 0.06)
        self.assertAlmostEqual(p["sleep"], 1.0 / 12.0)
        self.assertAlmostEqual(p["ratio"], 0.6)

    def test_degenerate_falls_back_to_defaults(self):
        p = animate_params({})
        self.assertAlmostEqual(p["density"], 0.06)
        p = animate_params(
            {"particles": {"count": "xx", "speed": float("nan"), "mix": None}}
        )
        self.assertAlmostEqual(p["density"], 0.06)
        self.assertAlmostEqual(p["sleep"], 1.0 / 12.0)
        self.assertAlmostEqual(p["ratio"], 0.6)


def _js_citation(text):
    block = re.search(r"EASTER_CITATION =\s*((?:\"[^\"]*\"\s*\+\s*)*\"[^\"]*\")", text)
    return "".join(re.findall(r"\"([^\"]*)\"", block.group(1)))


class EggParityTest(unittest.TestCase):
    def test_citation_identical_across_all_three_copies(self):
        from installer.launchers.python_launcher import EASTER_CITATION

        node = (ROOT / "installer" / "launchers" / "node_launcher.mjs").read_text(
            encoding="utf-8"
        )
        shell = (ROOT / "installer" / "shell" / "js" / "presets.js").read_text(
            encoding="utf-8"
        )
        self.assertEqual(_js_citation(node), EASTER_CITATION)
        self.assertEqual(_js_citation(shell), EASTER_CITATION)

    def test_coda_names_every_term(self):
        from installer.launchers.python_launcher import EASTER_CITATION

        for term in (
            "MiDi-MoE-Symbiogen-000",
            "Symbiogen-003 Automata",
            "Symbiogen-004 Errata",
            "IRC bridge",
            "weight-transfer units",
            "MIDI frequency transfer",
            "personality transposition",
        ):
            self.assertIn(term, EASTER_CITATION)


class ReadSceneTest(unittest.TestCase):
    def test_missing_theme_returns_empty_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(read_scene("nope", scenes_dir=tmp), {})
            self.assertIn("unreadable", err.getvalue())

    def test_garbage_fields_fall_back_per_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "bad.xml").write_text(
                '<scene version="1.0" theme="bad"><camera drift="xx"/><core/></scene>',
                encoding="utf-8",
            )
            scene = read_scene("bad", scenes_dir=tmp)
            self.assertAlmostEqual(scene["camera"]["drift"], 0.0012)
            self.assertEqual(scene["core"]["glow"], [128, 128, 255])
            self.assertAlmostEqual(scene["particles"]["speed"], 0.6)


class ValidatedIntTest(unittest.TestCase):
    def test_arms(self):
        self.assertEqual(validated_int("", 8, 1, 64), (True, 8))
        self.assertEqual(validated_int("12", 8, 1, 64), (True, 12))
        self.assertEqual(validated_int("abc", 8, 1, 64), (False, None))
        self.assertEqual(validated_int("99", 8, 1, 64), (False, None))
        self.assertEqual(validated_int(None, 8, 1, 64), (True, 8))


class InstallerE2ETest(unittest.TestCase):
    def test_quick_flow_completes_and_writes_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            env = {**os.environ, "RTRRE_INSTALL_NO_AUDIO": "1"}
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "installer" / "launchers" / "python_launcher.py"),
                    "--project",
                    str(project),
                ],
                input="1\ny\n\n\n",
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            cfg = json.loads(
                (project / ".opencode" / "rtr-re-keeper.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(cfg["preset"], "re-symbiose-mugen")

    def test_hardcore_flow_retries_then_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            env = {**os.environ, "RTRRE_INSTALL_NO_AUDIO": "1"}
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "installer" / "launchers" / "python_launcher.py"),
                    "--project",
                    str(project),
                ],
                input="3\nabc\n8\nxx\n40\n\n\ny\n\n\n",
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            self.assertGreaterEqual(proc.stdout.count("whole number"), 2)
            self.assertTrue((project / ".opencode" / "rtr-re-keeper.json").exists())

    def test_hardcore_flow_writes_chosen_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            env = {**os.environ, "RTRRE_INSTALL_NO_AUDIO": "1"}
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "installer" / "launchers" / "python_launcher.py"),
                    "--project",
                    str(project),
                ],
                input="3\n16\n60\nwide\nrtr-bge\ny\n\n\n",
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            cfg = json.loads(
                (project / ".opencode" / "rtr-re-keeper.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(cfg["preset"], "wide")
            self.assertEqual(cfg["threadsPerModel"], 16)
            self.assertEqual(cfg["parkingPercent"], 60)
            self.assertEqual(cfg["modality"], "rtr-bge")


if __name__ == "__main__":
    unittest.main()
