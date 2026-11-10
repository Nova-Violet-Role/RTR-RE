#!/usr/bin/env python3
"""RTR-RE installer — DTD conformance check.

Validates the shell markup (index.html) against the declared installer
DTD family: every element used in the markup must be declared in the UI
module, and the driver must resolve the module via its PUBLIC lineage.
Also validates the scene instances (dtd/scenes/*.xml) structurally and
checks the index.html scene embeds against the scene files, so the two
scene sources cannot drift apart.

This is the same discipline the retrieval pipeline applies to the DTD
corpus: the product's own gateway is a first-class family member.
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SHELL = Path(__file__).resolve().parent.parent
THEMES = ("instrument", "network", "forge")
SCENE_CHILDREN = ("camera", "core", "floor", "particles")


def declared_elements(dtd_dir):
    """Collect element names declared across the driver + modules."""
    declared = set()
    for pattern in ("*.dtd", "*.mod"):
        for path in Path(dtd_dir).glob(pattern):
            declared |= set(
                re.findall(
                    r"<!ELEMENT\s+([A-Za-z][\w-]*)\b",
                    path.read_text(encoding="utf-8"),
                )
            )
    return declared


def used_elements(html_path):
    """Collect element names used in the shell markup (tags)."""
    text = Path(html_path).read_text(encoding="utf-8")
    # strip script/style bodies so their content is not parsed as markup
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", text, flags=re.S)
    return set(re.findall(r"</?([A-Za-z][\w-]*)\b", text))


def embed_tags(html_path):
    """Collect element names used inside application/xml script embeds."""
    text = Path(html_path).read_text(encoding="utf-8")
    tags = set()
    for match in re.finditer(
        r'<script\s+type="application/xml"[^>]*>(.*?)</script>', text, re.S
    ):
        tags |= set(re.findall(r"</?([A-Za-z][\w-]*)\b", match.group(1)))
    return tags


def dynamic_tags(js_dir):
    """Collect element names the shell scripts create at runtime."""
    tags = set()
    for path in sorted(Path(js_dir).glob("*.js")):
        text = path.read_text(encoding="utf-8")
        tags |= set(re.findall(r"createElement\(\s*[\"']([\w-]+)[\"']", text))
        for match in re.finditer(r"\.innerHTML\s*=\s*(.+?);", text, re.S):
            tags |= set(re.findall(r"</?([A-Za-z][\w-]*)\b", match.group(1)))
    return tags


def collect_used(shell_root):
    """Union of markup, embed, and runtime-created element names."""
    root = Path(shell_root)
    used = used_elements(root / "index.html")
    used |= embed_tags(root / "index.html")
    if (root / "js").is_dir():
        used |= dynamic_tags(root / "js")
    return used


def check_scenes(shell_root):
    """Validate the scene instances structurally. Returns error strings."""
    errors = []
    scenes = Path(shell_root) / "dtd" / "scenes"
    if not scenes.is_dir():
        return [f"scenes dir missing: {scenes}"]
    files = sorted(scenes.glob("*.xml"))
    if not files:
        return ["no scene instances under dtd/scenes/"]
    for path in files:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            errors.append(f"{path.name}: not well-formed XML ({exc})")
            continue
        if root.tag != "scene":
            errors.append(f"{path.name}: root must be <scene>")
            continue
        children = tuple(child.tag for child in root)
        if children != SCENE_CHILDREN:
            errors.append(f"{path.name}: children must be {list(SCENE_CHILDREN)}")
        if root.get("theme") not in THEMES:
            errors.append(f"{path.name}: theme must be one of {list(THEMES)}")
        if root.get("version") != "1.0":
            errors.append(f"{path.name}: version must be 1.0")
    return errors


def _canon(elem):
    """Canonical scene form: structure + attribute values, no formatting."""
    return (
        elem.tag,
        tuple(sorted(elem.attrib.items())),
        tuple(_canon(child) for child in elem),
    )


def check_embed_parity(shell_root):
    """Check the index.html scene embeds against the scene files."""
    errors = []
    root = Path(shell_root)
    html_path = root / "index.html"
    if not html_path.exists():
        return [f"index.html missing: {html_path}"]
    html = html_path.read_text(encoding="utf-8")
    embeds = {}
    for match in re.finditer(
        r'<script\s+type="application/xml"\s+id="scene-([A-Za-z][\w-]*)"\s*>(.*?)</script>',
        html,
        re.S,
    ):
        theme, body = match.group(1), match.group(2)
        body = re.sub(r"^\s*<!\[CDATA\[", "", body)
        body = re.sub(r"\]\]>\s*$", "", body)
        body = re.sub(r"<\?xml[^?]*\?>\s*", "", body, count=1)
        try:
            embeds[theme] = ET.fromstring(body)
        except ET.ParseError as exc:
            errors.append(f"embed scene-{theme}: not well-formed ({exc})")
    scenes_dir = root / "dtd" / "scenes"
    if scenes_dir.is_dir():
        for path in sorted(scenes_dir.glob("*.xml")):
            theme = path.stem
            try:
                file_root = ET.parse(path).getroot()
            except ET.ParseError:
                continue  # reported by check_scenes
            if theme not in embeds:
                errors.append(
                    f"{path.name}: no matching embed scene-{theme} in index.html"
                )
            elif _canon(embeds[theme]) != _canon(file_root):
                errors.append(
                    f"{path.name}: embed scene-{theme} drifted from the scene file"
                )
    for theme in sorted(embeds):
        if not (root / "dtd" / "scenes" / f"{theme}.xml").exists():
            errors.append(f"embed scene-{theme}: no matching scene file")
    return errors


def main(root=None):
    shell = Path(root) if root is not None else SHELL
    failed = False

    html_path = shell / "index.html"
    if not html_path.exists():
        print(f"FAIL — index.html missing: {html_path}")
        return 1
    declared = declared_elements(shell / "dtd")
    used = collect_used(shell)
    undeclared = sorted(used - declared)
    unused = sorted(declared - used)

    print(f"declared: {len(declared)} elements")
    print(f"used:     {len(used)} elements")
    if undeclared:
        print(f"FAIL — used but not declared: {undeclared}")
        failed = True
    if unused:
        print(f"note — declared but unused: {unused}")
    for error in check_scenes(shell):
        print(f"FAIL — scene: {error}")
        failed = True
    for error in check_embed_parity(shell):
        print(f"FAIL — embed: {error}")
        failed = True
    if failed:
        return 1
    print("OK — shell markup conforms to the installer DTD family")
    return 0


if __name__ == "__main__":
    sys.exit(main())
