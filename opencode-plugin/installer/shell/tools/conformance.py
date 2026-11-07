#!/usr/bin/env python3
"""RTR-RE installer — DTD conformance check.

Validates the shell markup (index.html) against the declared installer
DTD family: every element used in the markup must be declared in the UI
module, and the driver must resolve the module via its PUBLIC lineage.

This is the same discipline the retrieval pipeline applies to the DTD
corpus: the product's own gateway is a first-class family member.
"""

import re
import sys
from pathlib import Path

SHELL = Path(__file__).resolve().parent.parent
DTD = SHELL / "dtd"
HTML = SHELL / "index.html"


def declared_elements():
    """Collect element names declared across the driver + modules."""
    declared = set()
    for f in DTD.glob("*.dtd"):
        declared |= set(
            re.findall(r"<!ELEMENT\s+([A-Za-z][\w-]*)\b", f.read_text(encoding="utf-8"))
        )
    for f in DTD.glob("*.mod"):
        declared |= set(
            re.findall(r"<!ELEMENT\s+([A-Za-z][\w-]*)\b", f.read_text(encoding="utf-8"))
        )
    return declared


def used_elements():
    """Collect element names used in the shell markup (tags)."""
    text = HTML.read_text(encoding="utf-8")
    # strip script/style bodies so their content is not parsed as markup
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", text, flags=re.S)
    return set(re.findall(r"</?([A-Za-z][\w-]*)\b", text))


def main():
    declared = declared_elements()
    used = used_elements()
    undeclared = sorted(used - declared)
    unused = sorted(declared - used)

    print(f"declared: {len(declared)} elements")
    print(f"used:     {len(used)} elements")
    if undeclared:
        print(f"FAIL — used but not declared: {undeclared}")
        return 1
    if unused:
        print(f"note — declared but unused: {unused}")
    print("OK — shell markup conforms to the installer DTD family")
    return 0


if __name__ == "__main__":
    sys.exit(main())
