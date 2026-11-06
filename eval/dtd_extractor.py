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
ELEM_DECL_RE = re.compile(r"<!ELEMENT\s+([^\s>]+)\s+(.*?)>", re.S)
ATTR_ITEM_TYPE_RE = re.compile(
    r"\s+([^\s>]+)\s+(CDATA|ID|IDREF|IDREFS|NMTOKEN|NMTOKENS|ENTITY|ENTITIES|NOTATION|\([^)]*\))"
)
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


def _decl_spans(text: str, kind: str) -> List[str]:
    """Yield each top-level declaration body of the given kind, quote-aware.

    A declaration runs from '<!KIND' to its matching '>' with single/double
    quotes respected, so a '>' inside a quoted entity value never splits a
    declaration. This is what makes entity bodies data: a declaration
    nested inside an entity value is consumed by the outer declaration and
    never surfaces as its own declaration (LAW.AMP.13).
    """
    spans: List[str] = []
    marker = "<!" + kind
    start = 0
    while True:
        i = text.find(marker, start)
        if i < 0:
            break
        j = i + len(marker)
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


def _attlist_spans(text: str) -> List[str]:
    """Yield each ATTLIST declaration body (quote-aware, so a '>' inside a
    quoted default value never ends the declaration early)."""
    return _decl_spans(text, "ATTLIST")


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


def extract_attr_types(scanned: str) -> Dict[str, str]:
    """Attribute name -> declared type, scoped to ATTLIST declarations.

    The type is the token after the attribute name (CDATA, ID, enumerated
    list, ...). First declaration wins; later duplicates are ignored.
    """
    types: Dict[str, str] = {}
    for decl in _attlist_spans(scanned):
        decl = COMMENT_RE.sub("", decl)
        for name, typ in ATTR_ITEM_TYPE_RE.findall(decl):
            types.setdefault(name, typ)
    return types


def extract_content_model_fragments(scanned: str, limit: int = 100) -> List[str]:
    """Distinctive content-model fragments from ELEMENT declarations.

    Each fragment is the normalized content model text (whitespace
    collapsed) of one element declaration, deduplicated and capped. These
    are the strings T9 queries are drawn from, so listing them in the
    inventory header gives the dense model a declaration context for the
    fragment.
    """
    out: List[str] = []
    seen = set()
    for _name, cm in ELEM_DECL_RE.findall(scanned):
        frag = " ".join(cm.split())
        if len(frag) > 6 and frag not in seen:
            seen.add(frag)
            out.append(frag)
            if len(out) >= limit:
                break
    return out


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
    content_model_fragments: List[str] = field(default_factory=list)
    attribute_types: Dict[str, str] = field(default_factory=dict)

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
            "content_model_fragments": self.content_model_fragments,
            "attribute_types": self.attribute_types,
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
    ents: List[str] = []
    params: List[str] = []
    for decl in _decl_spans(text, "ENTITY"):
        rest = decl[len("<!ENTITY") :].lstrip()
        if not rest:
            continue
        if rest.startswith("%"):
            rest = rest[1:].lstrip()
            params.append(rest.split()[0])
        else:
            ents.append(rest.split()[0])
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
        content_model_fragments=extract_content_model_fragments(scanned),
        attribute_types=extract_attr_types(scanned),
    )


def extract_corpus(root: Path, suffixes=(".dtd", ".mod", ".ent")) -> List[DTDProfile]:
    """Extract profiles for every DTD-family file under root."""
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes
    )
    return [extract_dtd_profile(p) for p in files]
