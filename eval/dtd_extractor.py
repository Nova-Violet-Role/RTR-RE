# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""DTD structural feature extractor — reusable instrument for the DTD study.

Parses any DTD/module/entity file and emits structural features: element
declarations, attribute lists (type/default), entity and parameter-entity
declarations, notations, content models (sequence/choice/repetition), nesting
depth, and line counts. Parameter entities are counted as data, never expanded
(LAW.AMP.13): a foreign tree cannot inject declarations into a run.

Deterministic: same input, same output. The corpus is the source of truth;
every number is read from the file, never recalled.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ELEM_RE = re.compile(r"<!ELEMENT\s+([^\s>]+)\s+\(?([^>]*)\)?")
ATTR_DECL_RE = re.compile(r"<!ATTLIST\s+([^\s>]+)")
ATTR_ITEM_RE = re.compile(
    r'\s+([^\s>]+)\s+(?:CDATA|ID|IDREF|IDREFS|NMTOKEN|NMTOKENS|ENTITY|ENTITIES|NOTATION|\([^)]*\))\s+(?:#REQUIRED|#IMPLIED|#FIXED|"[^"]*"|\'[^\']*\'|[^\s>]+)'
)
ENT_RE = re.compile(r"<!ENTITY\s+(?!%)([^\s>]+)")
PARAM_RE = re.compile(r"<!ENTITY\s+%\s+([^\s>]+)")
NOTATION_RE = re.compile(r"<!NOTATION\s+([^\s>]+)")
ENTITY_BLOCK_RE = re.compile(
    r"<!ENTITY\s+(?:%\s+)?[^\s>]+\s+(?:\"[^\"]*\"|'[^']*'|\[[^\]]*\])"
)
SEQ_RE = re.compile(r",")
CHOICE_RE = re.compile(r"\|")
REP_RE = re.compile(r"[\*\+\?]")
NEST_RE = re.compile(r"\([^()]*\)")


def mask_entity_bodies(text: str) -> str:
    """Remove entity declaration bodies so their values are never scanned as
    declarations (LAW.AMP.13): a parameter entity cannot inject elements."""
    return ENTITY_BLOCK_RE.sub("", text)


COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _attlist_spans(text: str) -> List[str]:
    """Yield each ATTLIST declaration body (quote-aware, so a '>' inside a
    quoted default value never ends the declaration early)."""
    spans: List[str] = []
    start = 0
    while True:
        i = text.find("<!ATTLIST", start)
        if i < 0:
            break
        j = i + len("<!ATTLIST")
        quote: Optional[str] = None
        while j < len(text):
            ch = text[j]
            if quote is not None:
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == ">":
                break
            j += 1
        spans.append(text[i : j + 1])
        start = j + 1
    return spans


def extract_attr_names(scanned: str) -> List[str]:
    """Attribute names scoped to ATTLIST declarations.

    The previous context-free ATTR_ITEM_RE.findall over the whole file
    captured junk tokens from comments, XML declarations and entity
    leftovers as "attribute names" (measured: 34/40 T7 queries were not
    real attributes). Scoping to declaration bodies and stripping
    comments fixes the instrument.
    """
    names: List[str] = []
    for decl in _attlist_spans(scanned):
        decl = COMMENT_RE.sub("", decl)
        names.extend(ATTR_ITEM_RE.findall(decl))
    return names


@dataclass
class ContentModel:
    has_sequence: bool = False
    has_choice: bool = False
    has_repetition: bool = False
    max_nesting: int = 0
    length: int = 0


@dataclass
class DTDProfile:
    path: str
    lines: int
    bytes: int
    sha256: str
    elements: int
    attributes: int
    attr_decls: int
    entities: int
    param_entities: int
    notations: int
    element_names: List[str] = field(default_factory=list)
    attribute_names: List[str] = field(default_factory=list)
    entity_names: List[str] = field(default_factory=list)
    param_entity_names: List[str] = field(default_factory=list)
    notation_names: List[str] = field(default_factory=list)
    content_models: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "lines": self.lines,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "elements": self.elements,
            "attributes": self.attributes,
            "attr_decls": self.attr_decls,
            "entities": self.entities,
            "param_entities": self.param_entities,
            "notations": self.notations,
            "element_names": self.element_names,
            "attribute_names": self.attribute_names,
            "entity_names": self.entity_names,
            "param_entity_names": self.param_entity_names,
            "notation_names": self.notation_names,
            "content_models": self.content_models,
        }


def content_model_shape(cm: str) -> ContentModel:
    cm = cm.strip()
    return ContentModel(
        has_sequence=bool(SEQ_RE.search(cm)),
        has_choice=bool(CHOICE_RE.search(cm)),
        has_repetition=bool(REP_RE.search(cm)),
        max_nesting=max((s.count("(") for s in NEST_RE.findall(cm)), default=0),
        length=len(cm),
    )


def extract_dtd_profile(path: Path) -> DTDProfile:
    """Extract the structural profile of one DTD-family file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        text = ""
    scanned = mask_entity_bodies(text)
    elems = ELEM_RE.findall(scanned)
    attr_decls = ATTR_DECL_RE.findall(scanned)
    attrs = extract_attr_names(scanned)
    ents = ENT_RE.findall(text)
    params = PARAM_RE.findall(text)
    nots = NOTATION_RE.findall(scanned)
    shapes = [content_model_shape(cm) for _, cm in elems]
    return DTDProfile(
        path=str(path),
        lines=text.count("\n") + 1,
        bytes=path.stat().st_size,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        elements=len(elems),
        attributes=len(attrs),
        attr_decls=len(attr_decls),
        entities=len(ents),
        param_entities=len(params),
        notations=len(nots),
        element_names=[name for name, _ in elems],
        attribute_names=attrs,
        entity_names=ents,
        param_entity_names=params,
        notation_names=nots,
        content_models={
            "sequences": sum(1 for s in shapes if s.has_sequence),
            "choices": sum(1 for s in shapes if s.has_choice),
            "repetitions": sum(1 for s in shapes if s.has_repetition),
            "max_nesting": max((s.max_nesting for s in shapes), default=0),
        },
    )


def extract_corpus(root: Path, suffixes=(".dtd", ".mod", ".ent")) -> List[DTDProfile]:
    """Extract profiles for every DTD-family file under root."""
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes
    )
    return [extract_dtd_profile(p) for p in files]
