# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from installer.shell.tools.conformance import (
    check_embed_parity,
    check_scenes,
    collect_used,
    declared_elements,
    dynamic_tags,
    embed_tags,
    main,
)

SHELL = ROOT / "installer" / "shell"


def make_tree(scenes, index_html, js_files=None):
    tmp = Path(tempfile.mkdtemp())
    (tmp / "dtd" / "scenes").mkdir(parents=True)
    for name, body in scenes.items():
        (tmp / "dtd" / "scenes" / name).write_text(body, encoding="utf-8")
    (tmp / "index.html").write_text(index_html, encoding="utf-8")
    if js_files:
        (tmp / "js").mkdir(parents=True)
        for name, body in js_files.items():
            (tmp / "js" / name).write_text(body, encoding="utf-8")
    return tmp


INSTRUMENT = (SHELL / "dtd" / "scenes" / "instrument.xml").read_text(encoding="utf-8")


class RealTreeTest(unittest.TestCase):
    def test_shipped_shell_conforms(self):
        self.assertEqual(check_scenes(SHELL), [])
        self.assertEqual(check_embed_parity(SHELL), [])
        self.assertEqual(main(SHELL), 0)


class SceneStructureTest(unittest.TestCase):
    def test_malformed_scene_fails(self):
        tree = make_tree({"bad.xml": "<scene><oops>"}, "<html></html>")
        errors = check_scenes(tree)
        self.assertTrue(any("bad.xml" in e for e in errors))

    def test_wrong_children_fail(self):
        body = '<scene version="1.0" theme="instrument"><camera/></scene>'
        tree = make_tree({"x.xml": body}, "<html></html>")
        self.assertTrue(check_scenes(tree))


class EmbedParityTest(unittest.TestCase):
    def test_drifted_embed_fails(self):
        drifted = INSTRUMENT.replace('drift="0.0012"', 'drift="9.9999"')
        html = (
            '<html><script type="application/xml" '
            'id="scene-instrument"><![CDATA[' + drifted + "]]></script></html>"
        )
        tree = make_tree({"instrument.xml": INSTRUMENT}, html)
        self.assertTrue(any("instrument" in e for e in check_embed_parity(tree)))

    def test_matching_embed_passes(self):
        html = (
            '<html><script type="application/xml" '
            'id="scene-instrument"><![CDATA[' + INSTRUMENT + "]]></script></html>"
        )
        tree = make_tree({"instrument.xml": INSTRUMENT}, html)
        self.assertEqual(check_embed_parity(tree), [])


class UsedSourcesTest(unittest.TestCase):
    def test_real_tree_fully_wired(self):
        self.assertEqual(declared_elements(SHELL / "dtd") - collect_used(SHELL), set())

    def test_embed_tags_found(self):
        html = (
            '<html><script type="application/xml" '
            'id="scene-instrument"><![CDATA[' + INSTRUMENT + "]]></script></html>"
        )
        tree = make_tree({"instrument.xml": INSTRUMENT}, html)
        tags = embed_tags(tree / "index.html")
        for name in ("scene", "camera", "core", "floor", "particles"):
            self.assertIn(name, tags)

    def test_dynamic_tags_found(self):
        js = (
            'const el = document.createElement("plan-item");\n'
            'el.innerHTML = `<k class="k">${k}</k>`;\n'
        )
        tree = make_tree({}, "<html></html>", {"x.js": js})
        tags = dynamic_tags(tree / "js")
        self.assertIn("plan-item", tags)
        self.assertIn("k", tags)


class ThreadModesTest(unittest.TestCase):
    def test_threads_select_mirrors_registry_modes(self):
        html = (SHELL / "index.html").read_text(encoding="utf-8")
        match = re.search(r'<select[^>]*id="hcThreads"[^>]*>(.*?)</select>', html, re.S)
        self.assertIsNotNone(match, "hcThreads must be a discrete select")
        options = [
            int(o) for o in re.findall(r'<option[^>]*value="(\d+)"', match.group(1))
        ]
        registry = json.loads(
            (ROOT / "execution" / "rtr_presets.json").read_text(encoding="utf-8")
        )
        self.assertEqual(options, registry["threadModes"])
        selected = re.search(r'<option[^>]*value="(\d+)"[^>]*selected', match.group(1))
        self.assertIsNotNone(selected)
        self.assertEqual(selected.group(1), "8")


if __name__ == "__main__":
    unittest.main()
