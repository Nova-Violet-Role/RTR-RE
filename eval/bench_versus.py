# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""RE:Symbiose vs classic RAG — OFFICIAL versus tool on REAL documentation.

Full name: Role-Type-Retrieval-RE:Symbiotized. Licence: EUPL-1.2 OR
AGPL-3.0-or-later. Corpus: real NestedText studies + real DITA 2.0 spec
topics (staged copies, byte-identical, sha256 manifest in the results).
Systems: rag-dense / rag-hybrid on bge-small AND on bge-base (same-size
controls, so no model-size strawman), RTR ablations, rtr-full (arctic-m +
bge-base, expansion, RRF, DTD lanes). Same staged index, fully isolated
roots/registry/DB per run — procedural evaluation data nobody misjudges.

Taxonomy (taxionometry):
  T1 title-self ... file's own title must come back top-1
  T2 rare-term .... df==1 opaque term must resolve to its file
  T3 concept ..... mid-df keyword pair must recall its file in top-3
  T4 scoped ...... T1 queries under a project filter (isolation check)
  T5 paraphrase .. TRUE synonym absent corpus-wide (BM25 blind, dense must win)
  T6 ident ....... filename stems + opaque digit/underscore ids (exact lane)

Metrics: recall@1, recall@3, MRR per taxon per system + macro overall.
Deterministic (seeded). Writes eval/results/versus.json + eval/versus.mmd.

Run:  python eval/bench_versus.py   (with the deployment env for caches)
"""

import argparse
import contextlib
import hashlib
import io
import json
import os
import random
import re
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))

import memory_engine as mem
from memory_engine import MemoryEngine

SEED = 20260928
DTD_SUFFIXES = (".dtd", ".mod", ".ent")
CORPORA = [
    {
        "name": "nt-studies",
        "src": Path(
            r"C:\Microsoft Skill OPT and Skill LENS install via UV\dtd\full-study"
        ),
        "glob": "*.nt",
        "mode": "stratified",
        "n": 36,
        "title": "md",
    },
    {
        "name": "dita-spec",
        "src": Path(
            r"C:\Microsoft Skill OPT and Skill LENS install via UV\dtd\dita\specification\archSpec\base"
        ),
        "glob": "*.dita",
        "mode": "step",
        "step": 7,
        "n": 30,
        "title": "dita",
    },
    {
        "name": "dtd-commands",
        "src": Path.home() / ".config" / "opencode" / "commands",
        "glob": "*-dtd.md",
        "mode": "stratified",
        "n": 48,
        "title": "md",
    },
    {
        "name": "dtd-family",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples"),
        "suffixes": DTD_SUFFIXES,
        "mode": "stratified",
        "group_by": "dir",
        "n": 60,
        "title": "dtd",
        "prefix_rel": True,
    },
]

# Per-family DTD suites (TODO-36): one corpus per real family, staged from
# that family's own directory only, capped at 40 files so every suite is
# bounded. Queries are derived from each family's own vocabulary by
# derive_dtd_queries (T10 naturally yields nothing within a single family).
# Only run when explicitly named via --corpora; the default run is unchanged.
PER_FAMILY_CORPORA = [
    {
        "name": "dtd-jats",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\JATS-DTDs"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-daisy",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\daisy"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-docbook",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\docbook"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-dtds",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\dtds"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-mathml",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\mathml"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-office",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\office"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-dita-spec11",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\org.dita.specialization.dita11"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-dita12",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\org.oasis-open.dita.v1_2"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-dita13",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\org.oasis-open.dita.v1_3"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-xdita",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\org.oasis-open.xdita.v0_2_2"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-svg",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\svg"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-tei",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\tei"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-xhtml",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\xhtml"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
    {
        "name": "dtd-xhtml11",
        "src": Path(r"C:\DTD_FAMILY\.dtd-file-examples\xhtml11"),
        "suffixes": DTD_SUFFIXES,
        "mode": "step",
        "step": 1,
        "n": 40,
        "title": "dtd",
        "prefix_rel": True,
    },
]

ALL_CORPORA = CORPORA + PER_FAMILY_CORPORA

# Per-taxon query caps. Precedent defaults reproduce the historical 164;
# --intense explodes the table (more queries per taxon, same derivation).
CAPS = {"T2": 12, "T3": 12, "T4": 12, "T5": 12, "T6": 6}
INTENSE_CAPS = {"T2": 40, "T3": 10**9, "T4": 36, "T5": 24, "T6": 20}
# DTD taxon caps: raised so per-taxon verdicts are statistically meaningful
# (T7-T10 at n=12 or below flip 0.08-0.17 on a single query).
DTD_CAPS = {"T7": 40, "T8": 40, "T9": 40, "T10": 40, "T11": 40, "T12": 40}
K = 3

STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "such",
    "sources",
    "measured",
    "file",
    "files",
    "lists",
    "notes",
}

TITLE_SKIP = ("spdx", "copyright", "nestedtext", "sources:")

INDEX_MODELS = (
    "Snowflake/snowflake-arctic-embed-m,BAAI/bge-base-en-v1.5,BAAI/bge-small-en-v1.5"
)

SYSTEMS = {
    "rag-dense": {
        "models": "BAAI/bge-small-en-v1.5",
        "hybrid": False,
        "scoped": False,
    },
    "rag-hybrid": {
        "models": "BAAI/bge-small-en-v1.5",
        "hybrid": True,
        "scoped": False,
    },
    # Same-size controls: classic RAG on the SAME 768d model RTR ships,
    # so any RTR lead cannot be dismissed as a model-size strawman.
    "rag-dense-base": {
        "models": "BAAI/bge-base-en-v1.5",
        "hybrid": False,
        "scoped": False,
    },
    "rag-hybrid-base": {
        "models": "BAAI/bge-base-en-v1.5",
        "hybrid": True,
        "scoped": False,
    },
    "rtr-arctic": {
        "models": "Snowflake/snowflake-arctic-embed-m",
        "hybrid": True,
        "scoped": True,
    },
    "rtr-bge": {
        "models": "BAAI/bge-base-en-v1.5",
        "hybrid": True,
        "scoped": True,
    },
    "rtr-full": {
        "models": "Snowflake/snowflake-arctic-embed-m,BAAI/bge-base-en-v1.5",
        "hybrid": True,
        "scoped": True,
    },
}

# Candidate true-synonym pairs for the T5 paraphrase lane.
# Runtime-validated: source must occur, synonym must NOT occur corpus-wide
# (else BM25 contaminates the lane). Single-owner sources only.
SYNONYM_MAP = {
    "dispatch": "remit",
    "gateway": "portal",
    "nocturnal": "nightly",
    "fallback": "recourse",
    "latency": "lag",
    "throughput": "velocity",
    "ledger": "annals",
    "arbiter": "umpire",
    "bridge": "viaduct",
    "router": "forwarder",
    "budget": "stipend",
    "ceiling": "cap",
    "template": "exemplar",
    "orchestration": "choreography",
    "roundtrips": "tours",
    "dusk": "gloaming",
    "burrow": "warren",
    "moonrise": "eventide",
    "conduit": "raceway",
    "emit": "exhale",
    "consume": "devour",
    "transform": "transmute",
    "validate": "attest",
    "traverse": "trek",
    "collect": "amass",
    "render": "depict",
    "parse": "construe",
    "compile": "collate",
    "shard": "splinter",
    "merge": "amalgamate",
    "prune": "pare",
    "scaffold": "trestle",
    "survey": "canvass",
    "catalog": "gazetteer",
    "token": "counter",
    "sigil": "emblem",
    "matrix": "lattice",
    "terminal": "terminus",
    "mechanism": "contrivance",
    "contract": "covenant",
    "trio": "triad",
    "harvest": "glean",
    "conductor": "maestro",
    "plugin": "addon",
    "index": "concordance",
    "duo": "dyad",
    "polyglot": "multilingual",
    "nested": "embedded",
}


def tokens(text):
    return [t.lower() for t in re.findall(r"\w+", text) if len(t) > 2]


BENCH_ROOT = None  # set by main(): the only discovery root (full isolation)


def stage_corpus(spec, prefix):
    """Sample real docs -> temp bench project (original names, bytes intact)."""
    if spec.get("suffixes"):
        files = sorted(
            f
            for f in spec["src"].rglob("*")
            if f.is_file() and f.suffix.lower() in spec["suffixes"]
        )
    else:
        files = sorted(spec["src"].glob(spec["glob"]))
    if spec["mode"] == "stratified":
        groups = defaultdict(list)
        if spec.get("group_by") == "dir":
            for f in files:
                rel = f.relative_to(spec["src"])
                key = rel.parts[0] if len(rel.parts) > 1 else "(root)"
                groups[key].append(f)
        else:
            for f in files:
                groups[f.name.split("-")[0].split(".")[0]].append(f)
        chosen = []
        while len(chosen) < spec["n"] and groups:
            for g in sorted(groups):
                if groups[g] and len(chosen) < spec["n"]:
                    chosen.append(groups[g].pop(0))
            groups = {g: v for g, v in groups.items() if v}
    else:
        chosen = files[:: spec.get("step", 1)][: spec["n"]]
    # Project dir directly under the isolated root so the engine's project
    # key (first relative part) equals Path(proj).name — scoped filters
    # resolve. One level deeper measured 0.0 on every scoped arm.
    # Deterministic name (no random suffix): the staged dir name becomes
    # part of every indexed chunk text, so a random suffix made the
    # embeddings — and therefore the whole scoreboard — nondeterministic
    # across runs (measured: identical runs differed on 52-118/163 queries).
    base = BENCH_ROOT / f"bench-{prefix}"
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    proj = base
    d = proj / "directives"
    d.mkdir(parents=True)
    staged = []
    for f in chosen:
        # Byte copy: staged corpora must be byte-identical to the real
        # sources hashed in the manifest, never newline-translated.
        if spec.get("prefix_rel"):
            rel = f.relative_to(spec["src"])
            name = f"{rel.parts[0]}__{f.name}" if len(rel.parts) > 1 else f.name
        else:
            name = f.name
        shutil.copyfile(f, d / name)
        staged.append(name)
    return base, proj, staged


def extract_title(text, mode):
    if mode == "dita":
        m = re.search(r"<title[^>]*>(.*?)</title>", text, re.DOTALL)
        if m:
            t = re.sub(r"<[^>]+>", " ", m.group(1))
            t = re.sub(r"\s+", " ", t).strip()
            if t:
                return t
    if mode == "dtd":
        m = re.search(r"<!ELEMENT\s+([^\s>]+)", text)
        if m:
            return m.group(1)
    headers = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            headers.append(s.lstrip("#").strip())
    title = next((h for h in headers if not h.lower().startswith(TITLE_SKIP)), "")
    if not title and headers:
        title = max(headers, key=len)
    if not title:
        for line in text.splitlines():
            if line.strip():
                return line.strip()[:120]
    return title


def derive_queries(proj, rng, title_mode="md"):
    """Auto-derive taxon queries from staged files (deterministic)."""
    docs = {}
    for f in sorted((proj / "directives").iterdir()):
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        docs[f.name] = (extract_title(text, title_mode), text)
    df = defaultdict(int)
    tok = {n: tokens(t) for n, (_ti, t) in docs.items()}
    for n, ts in tok.items():
        for t in set(ts):
            df[t] += 1
    names = sorted(docs)
    queries = []
    for n in names:  # T1: title self-retrieval
        if docs[n][0]:
            queries.append(("T1", docs[n][0], n))
    rares = sorted(
        [t for t, c in df.items() if c == 1 and len(t) > 4 and t not in STOP]
    )
    rng.shuffle(rares)
    owner = {}
    for n, ts in tok.items():
        for t in set(ts):
            owner.setdefault(t, n)
    for t in rares[: CAPS["T2"]]:  # T2: rare-term lookup
        queries.append(("T2", t, owner[t]))
    mids = sorted(
        [t for t, c in df.items() if 2 <= c <= 4 and t not in STOP and len(t) > 3]
    )
    for n in names[: CAPS["T3"]]:  # T3: mid-df pair from same file
        cand = [t for t in dict.fromkeys(tok[n]) if t in mids]
        if len(cand) >= 2:
            queries.append(("T3", f"{cand[0]} {cand[1]}", n))
    for taxon, q, n in [x for x in queries if x[0] == "T1"][
        : CAPS["T4"]
    ]:  # T4: scoped T1
        queries.append(("T4", q, n))
    # T5: TRUE paraphrase lane — phrasal synonym queries, every term absent
    # corpus-wide so BM25 is blind for all systems. The validated pairs are
    # ALSO seeded into the bench project's lexikon (term=source wording,
    # alias=synonym): this simulates a deployment-mature glossary and isolates
    # pillar 1's lexikon lane — rag systems never read it (project=None).
    owners = defaultdict(list)
    for n, ts in tok.items():
        for t in set(ts):
            owners[t].append(n)
    valid_pairs = []
    for src, syn in SYNONYM_MAP.items():
        if src not in df or syn in df:
            continue
        if len(owners[src]) != 1:
            continue
        valid_pairs.append((src, syn, owners[src][0]))
    try:
        eng0 = MemoryEngine()
        for src, syn, owner_n in valid_pairs:
            stem = " ".join(
                t for t in re.findall(r"\w+", Path(owner_n).stem.lower()) if len(t) > 2
            )
            eng0.add_lexikon_term(
                str(proj),
                src,
                definition=f"{src} {stem}",
                aliases=[syn],
            )
        eng0.close()
    except Exception as e:
        print(f"lexikon seed failed: {e}", file=sys.stderr)
    derive_queries._lex_seeded_count = len(valid_pairs)
    by_owner = defaultdict(list)
    for src, syn, owner_n in valid_pairs:
        by_owner[owner_n].append(syn)
    for owner_n in sorted(by_owner):
        syns = by_owner[owner_n]
        if len(syns) >= 2:
            queries.append(("T5", " ".join(sorted(syns)[:3]), owner_n))
        if sum(1 for q in queries if q[0] == "T5") >= CAPS["T5"]:
            break
    # T6: identifier/path lookup (filename stems + opaque content ids)
    for n in names[: CAPS["T6"]]:
        queries.append(("T6", Path(n).stem, n))
    idtoks = sorted(
        [
            t
            for t, c in df.items()
            if c == 1 and len(t) > 5 and ("_" in t or any(ch.isdigit() for ch in t))
        ]
    )
    rng.shuffle(idtoks)
    for t in idtoks[: CAPS["T6"]]:
        queries.append(("T6", t, owner[t]))
    return queries


def derive_dtd_queries(proj, rng):
    """Auto-derive DTD-structural taxon queries from staged DTD files.

    Uses the shared extractor (eval/dtd_extractor.py) so queries target real
    declared structure: element names (T1/T2), attribute semantics (T7),
    entity/parameter-entity lanes (T8), content-model fragments (T9).
    Deterministic: seeded per-corpus RNG, same staged set -> same queries.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    import dtd_extractor as dx

    docs = {}
    for f in sorted((proj / "directives").iterdir()):
        if not f.is_file():
            continue
        docs[f.name] = dx.extract_dtd_profile(f)

    # Element-name document frequency across the staged corpus.
    df = defaultdict(int)
    for name, prof in docs.items():
        for el in set(prof.element_names):
            df[el] += 1
    attr_df = defaultdict(int)
    for name, prof in docs.items():
        for a in set(prof.attribute_names):
            attr_df[a] += 1
    ent_df = defaultdict(int)
    for name, prof in docs.items():
        for e in set(prof.entity_names + prof.param_entity_names):
            ent_df[e] += 1

    queries = []
    names = sorted(docs)
    # T1: root element self-retrieval (first declared element).
    for n in names:
        if docs[n].element_names:
            queries.append(("T1", docs[n].element_names[0], n))
    # T2: rare element names (df == 1, opaque length).
    rares = sorted(
        [t for t, c in df.items() if c == 1 and len(t) > 3 and t not in STOP]
    )
    rng.shuffle(rares)
    owner = {}
    for n, prof in docs.items():
        for t in set(prof.element_names):
            owner.setdefault(t, n)
    for t in rares[: CAPS["T2"]]:
        queries.append(("T2", t, owner[t]))
    # T7: attribute-semantic recall — rare attribute names.
    attr_rares = sorted(
        [t for t, c in attr_df.items() if c == 1 and len(t) > 3 and t not in STOP]
    )
    rng.shuffle(attr_rares)
    attr_owner = {}
    for n, prof in docs.items():
        for t in set(prof.attribute_names):
            attr_owner.setdefault(t, n)
    for t in attr_rares[: DTD_CAPS["T7"]]:
        queries.append(("T7", t, attr_owner[t]))
    # T8: entity-lane recall — rare entity/parameter-entity names.
    ent_rares = sorted(
        [t for t, c in ent_df.items() if c == 1 and len(t) > 3 and t not in STOP]
    )
    rng.shuffle(ent_rares)
    ent_owner = {}
    for n, prof in docs.items():
        for t in set(prof.entity_names + prof.param_entity_names):
            ent_owner.setdefault(t, n)
    for t in ent_rares[: DTD_CAPS["T8"]]:
        queries.append(("T8", t, ent_owner[t]))
    # T9: content-model fragment recall — distinctive sequence/choice text.
    for n in names[: DTD_CAPS["T9"]]:
        prof = docs[n]
        if prof.content_models["sequences"] or prof.content_models["choices"]:
            text = Path(proj / "directives" / n).read_text(
                encoding="utf-8", errors="replace"
            )
            m = re.search(r"<!ELEMENT\s+[^\s>]+\s+\(([^)]+)\)", text)
            if m and len(m.group(1).strip()) > 6:
                queries.append(("T9", m.group(1).strip(), n))
    # T10: cross-family generalization — a term occurring in exactly two files
    # from DIFFERENT families (df==2, cross-family), querying one of them.
    # Isolates whether retrieval can discriminate shared vocabulary across
    # families instead of collapsing on the strongest family match.
    fam_of = {}
    for n in names:
        fam_of[n] = n.split("__")[0] if "__" in n else "(root)"
    cross = defaultdict(list)
    for n, prof in docs.items():
        for el in set(prof.element_names):
            cross[el].append(n)
    cross_terms = sorted(
        t
        for t, owners in cross.items()
        if len(owners) == 2
        and fam_of[owners[0]] != fam_of[owners[1]]
        and len(t) > 3
        and t not in STOP
    )
    rng.shuffle(cross_terms)
    for t in cross_terms[: DTD_CAPS["T10"]]:
        queries.append(("T10", t, cross[t][0]))
    # T11: lineage discrimination — query the family keyword/owner from a
    # file's PUBLIC lineage (TODO-64 proposal A/E). Isolates whether the
    # LINEAGE inventory signal lets retrieval identify a family by its
    # declared identity rather than its element vocabulary.
    lineage_terms = []
    for n, prof in docs.items():
        for entry in prof.lineage:
            kw = entry.get("keyword") or ""
            if kw and kw not in STOP and len(kw) > 4:
                lineage_terms.append((kw, n))
    rng.shuffle(lineage_terms)
    for kw, n in lineage_terms[: DTD_CAPS["T11"]]:
        queries.append(("T11", kw, n))
    # T12: customization-layer recognition — query a module-switch name from
    # a driver's customization layer (TODO-64 proposal C/E). Isolates
    # whether the MODULE SWITCHES inventory signal makes the customization
    # intent retrievable.
    switch_terms = []
    for n, prof in docs.items():
        for s in prof.module_switches:
            nm = s.get("name") or ""
            if nm and len(nm) > 4:
                switch_terms.append((nm, n))
    rng.shuffle(switch_terms)
    for nm, n in switch_terms[: DTD_CAPS["T12"]]:
        queries.append(("T12", nm, n))
    # T6: identifier/path lookup (filename stems).
    for n in names[: CAPS["T6"]]:
        queries.append(("T6", Path(n).stem, n))
    return queries


def run_system(engine, system, queries, proj):
    cfg = SYSTEMS[system]
    os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = cfg["models"]
    rows = []
    for taxon, q, expected in queries:
        filt = str(proj) if (cfg["scoped"] or taxon == "T4") else None
        t0 = time.time()
        err = ""
        try:
            res = engine.search(q, k=K, project=filt, hybrid=cfg["hybrid"])
        except Exception as e:
            res = []
            err = f"{type(e).__name__}: {e}"
            print(f"query failed [{q}]: {err}", file=sys.stderr)
        names = [Path(r["metadata"]["source"]).name for r in res]
        rows.append(
            {
                "taxon": taxon,
                "query": q[:80],
                "expected": expected,
                "got": names,
                "ms": round((time.time() - t0) * 1000, 1),
                "error": err,
            }
        )
    return rows


def metrics(rows):
    out = {}
    by_taxon = defaultdict(list)
    for r in rows:
        by_taxon[r["taxon"]].append(r)
    for taxon, rs in sorted(by_taxon.items()):
        r1 = sum(1 for r in rs if r["got"][:1] == [r["expected"]]) / len(rs)
        r3 = sum(1 for r in rs if r["expected"] in r["got"][:3]) / len(rs)
        mrr = sum(
            next(
                (1.0 / (i + 1) for i, n in enumerate(r["got"]) if n == r["expected"]),
                0.0,
            )
            for r in rs
        ) / len(rs)
        out[taxon] = {
            "n": len(rs),
            "recall@1": round(r1, 4),
            "recall@3": round(r3, 4),
            "mrr": round(mrr, 4),
        }
    allq = len(rows)
    out["OVERALL"] = {
        "n": allq,
        "recall@1": round(
            sum(1 for r in rows if r["got"][:1] == [r["expected"]]) / allq, 4
        ),
        "recall@3": round(
            sum(1 for r in rows if r["expected"] in r["got"][:3]) / allq, 4
        ),
        "mrr": round(
            sum(
                next(
                    (
                        1.0 / (i + 1)
                        for i, n in enumerate(r["got"])
                        if n == r["expected"]
                    ),
                    0.0,
                )
                for r in rows
            )
            / allq,
            4,
        ),
        "p50_ms": sorted(r["ms"] for r in rows)[len(rows) // 2],
    }
    return out


def write_mermaid(path, combined, n_queries, n_errors):
    systems = list(combined)

    def ov(system):
        return combined[system]["metrics"]["OVERALL"]

    lines = [
        "%% SPDX-FileCopyrightText: Nova-Violet Role ORG",
        "%% SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later",
        "xychart-beta",
        f'    title "RE:Symbiose vs RAG — combined ({n_queries} queries, real corpora, {n_errors} errors)"',
        "    x-axis [" + ", ".join(f'"{s}"' for s in systems) + "]",
        '    y-axis "score" 0 --> 1',
        '    bar "R@1" ['
        + ", ".join(f"{ov(s)['recall@1']:.3f}" for s in systems)
        + "]",
        '    bar "R@3" ['
        + ", ".join(f"{ov(s)['recall@3']:.3f}" for s in systems)
        + "]",
        '    bar "MRR" [' + ", ".join(f"{ov(s)['mrr']:.3f}" for s in systems) + "]",
    ]
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def write_scoreboard(path, results):
    """Full exploded table: per corpus x taxon x system, precedent format."""
    lines = [
        "<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->",
        "<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->",
        "# RE:Symbiose versus RAG — full scoreboard (generated, do not edit)",
        "",
        f"Tool: {results.get('tool')} | seed {results.get('seed')} | "
        f"lexikon seeded {results.get('lexikon_seeded')}",
        "",
    ]
    for cname, corp in results["corpora"].items():
        lines.append(f"## {cname} ({corp['files']} files, {corp['queries']} queries)")
        lines.append("")
        lines.append("| System | Taxon | n | R@1 | R@3 | MRR |")
        lines.append("|---|---|---|---|---|---|")
        for system, data in corp["systems"].items():
            for taxon, m in sorted(data["metrics"].items()):
                lines.append(
                    f"| {system} | {taxon} | {m['n']} | {m['recall@1']:.4f} "
                    f"| {m['recall@3']:.4f} | {m['mrr']:.4f} |"
                )
        lines.append("")
    lines.append("## Combined")
    lines.append("")
    lines.append("| System | n | R@1 | R@3 | MRR | p50 ms | errors |")
    lines.append("|---|---|---|---|---|---|---|")
    for system, data in results["combined"].items():
        o = data["metrics"]["OVERALL"]
        lines.append(
            f"| {system} | {data['n']} | {o['recall@1']:.4f} | {o['recall@3']:.4f} "
            f"| {o['mrr']:.4f} | {o['p50_ms']} | {data['query_errors']} |"
        )
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def write_per_family_board(path, results):
    """Per-family DTD suite scoreboard (TODO-36): one row per family x
    system, R@1/R@3/MRR from the OVERALL metrics of each suite corpus."""
    family_names = {c["name"] for c in PER_FAMILY_CORPORA}
    families = [c for c in results["corpora"] if c in family_names]
    if not families:
        return
    systems = sorted({s for c in families for s in results["corpora"][c]["systems"]})
    lines = [
        "<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->",
        "<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->",
        "# DTD per-family suites — scoreboard (generated, do not edit)",
        "",
        f"Tool: {results.get('tool')} | seed {results.get('seed')}",
        "",
        "| Family | Files | Queries | System | n | R@1 | R@3 | MRR |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for fam in sorted(families):
        corp = results["corpora"][fam]
        for system in systems:
            if system not in corp["systems"]:
                continue
            o = corp["systems"][system]["metrics"]["OVERALL"]
            lines.append(
                f"| {fam} | {corp['files']} | {corp['queries']} | "
                f"{system} | {o['n']} | {o['recall@1']:.4f} | "
                f"{o['recall@3']:.4f} | {o['mrr']:.4f} |"
            )
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def cleanup_extra(base):
    try:
        if mem.EXTRA_ROOTS_FILE.exists():
            data = json.loads(mem.EXTRA_ROOTS_FILE.read_text(encoding="utf-8"))
            data = [p for p in data if base.name not in str(p)]
            if data:
                mem.EXTRA_ROOTS_FILE.write_text(
                    json.dumps(data, indent=2), encoding="utf-8"
                )
            else:
                mem.EXTRA_ROOTS_FILE.unlink()
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(
        prog="bench_versus",
        description="Official RE:Symbiose vs RAG versus tool (real corpora, isolated, hashed manifest).",
    )
    ap.add_argument("--systems", default="", help="comma list subset of systems")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--intense", action="store_true", help="exploded per-taxon caps")
    ap.add_argument("--corpora", default="", help="comma list subset of corpora")
    args = ap.parse_args()
    if args.intense:
        CAPS.update(INTENSE_CAPS)
    global BENCH_ROOT
    os.environ["OPENCODE_MEMORY_FILE_SUFFIXES"] = (
        ".md,.nt,.yaml,.yml,.dita,.xml,.dtd,.mod,.ent"
    )
    # Determinism (measured, TODO-31): chroma HNSW build/search is
    # nondeterministic by default — two identical runs differed on
    # 52-118/163 queries. Pin single-threaded construction and a
    # near-exact search so the scoreboard is reproducible.
    os.environ["OPENCODE_MEMORY_HNSW_NUM_THREADS"] = "1"
    os.environ["OPENCODE_MEMORY_HNSW_SEARCH_EF"] = "1000"
    # FULL isolation: DB, registry, extra roots and discovery roots all temp.
    # Precedent runs leaked live roots (measured: 36 staged -> 66 indexed).
    iso = Path(tempfile.mkdtemp(prefix="rtr-versus-iso-"))
    BENCH_ROOT = iso / "roots"
    BENCH_ROOT.mkdir(parents=True)
    db_tmp = iso / "db"
    os.environ["OPENCODE_MEMORY_DB_DIR"] = str(db_tmp)
    saved = (
        mem.PROJECT_ROOTS,
        mem.REGISTRY_FILE,
        mem.EXTRA_ROOTS_FILE,
        mem.PROJECTS_DIR,
        mem.LEXIKON_GLOBAL_FILE,
    )
    mem.PROJECT_ROOTS = [BENCH_ROOT]
    mem.PROJECTS_DIR = BENCH_ROOT
    mem.REGISTRY_FILE = iso / "registry.json"
    mem.EXTRA_ROOTS_FILE = iso / "extra_roots.json"
    # Global lexikon isolated: precedent runs expanded from the operator's
    # live glossary — an undeclared third corpus inside every RTR query.
    mem.LEXIKON_GLOBAL_FILE = iso / "lexikon_global.json"
    results = {
        "seed": args.seed,
        "tool": "RE:Symbiose versus v2 (isolated, same-size controls)",
        "corpora": {},
        "lexikon_seeded": 0,
        "manifest": {},
    }
    systems = [s.strip() for s in args.systems.split(",") if s.strip()] or list(SYSTEMS)
    corpora = [c.strip() for c in args.corpora.split(",") if c.strip()]
    all_rows = {s: [] for s in systems}
    try:
        available = ALL_CORPORA if corpora else CORPORA
        for spec in [c for c in available if not corpora or c["name"] in corpora]:
            # One fresh DB + registry per corpus: delete/add churn on one
            # persistent HNSW segment desyncs ids under many short-lived
            # engines (measured: bge arms return empty after corpus 1 in
            # full sequence while subset runs pass). Isolation per corpus
            # removes the purge entirely — cleaner and reproducible.
            os.environ["OPENCODE_MEMORY_DB_DIR"] = str(iso / f"db-{spec['name']}")
            mem.REGISTRY_FILE = iso / f"registry-{spec['name']}.json"
            base, proj, staged = stage_corpus(spec, spec["name"])
            print(f"[{spec['name']}] staged {len(staged)} real files -> {proj}")
            # Per-corpus RNG: subset runs must derive identical queries to
            # full runs (measured drift when one shared RNG threaded all).
            crng = random.Random(
                args.seed
                + int(hashlib.sha256(spec["name"].encode()).hexdigest()[:8], 16)
            )
            if spec["title"] == "dtd":
                queries = derive_dtd_queries(proj, crng)
            else:
                queries = derive_queries(proj, crng, spec["title"])
            print(f"[{spec['name']}] derived {len(queries)} queries")
            results["manifest"][spec["name"]] = [
                {
                    "file": n,
                    "sha256": hashlib.sha256(
                        (proj / "directives" / n).read_bytes()
                    ).hexdigest(),
                }
                for n in staged
            ]
            results["lexikon_seeded"] += getattr(derive_queries, "_lex_seeded_count", 0)
            engine = MemoryEngine()
            mem.resolve_project_dir(str(proj))
            os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = INDEX_MODELS
            st = engine.index_all()
            results["lexikon_seeded"] += st.get("lexikon_seeded", 0)
            if st.get("status") == "error":
                print(
                    f"[{spec['name']}] INDEX REFUSED: {st.get('message')}",
                    file=sys.stderr,
                )
                engine.close()
                sys.exit(2)
            print(f"[{spec['name']}] indexed: new={st['new']} failed={st['failed']}")
            engine.close()
            corp = {"files": len(staged), "queries": len(queries), "systems": {}}
            for system in systems:
                eng = MemoryEngine()
                errbuf = io.StringIO()
                with contextlib.redirect_stderr(errbuf):
                    rows = run_system(eng, system, queries, proj)
                eng.close()
                qerr = errbuf.getvalue().count("Query failed on ")
                for r in rows:
                    r["corpus"] = spec["name"]
                    all_rows[system].append(r)
                corp["systems"][system] = {
                    "metrics": metrics(rows),
                    "rows": rows,
                    "query_errors": qerr,
                }
                m = corp["systems"][system]["metrics"]["OVERALL"]
                print(
                    f"[{spec['name']}] {system}: R@1={m['recall@1']} "
                    f"R@3={m['recall@3']} MRR={m['mrr']} p50={m['p50_ms']}ms"
                )
            results["corpora"][spec["name"]] = corp
            shutil.rmtree(base, ignore_errors=True)
            cleanup_extra(base)
    finally:
        (
            mem.PROJECT_ROOTS,
            mem.REGISTRY_FILE,
            mem.EXTRA_ROOTS_FILE,
            mem.PROJECTS_DIR,
            mem.LEXIKON_GLOBAL_FILE,
        ) = saved
        shutil.rmtree(iso, ignore_errors=True)
    combined = {}
    for system, rows in all_rows.items():
        qerr = sum(
            results["corpora"][c]["systems"][system].get("query_errors", 0)
            for c in results["corpora"]
        )
        combined[system] = {
            "metrics": metrics(rows),
            "n": len(rows),
            "query_errors": qerr,
        }
    results["combined"] = combined
    for system, m in combined.items():
        o = m["metrics"]["OVERALL"]
        print(
            f"[combined] {system}: R@1={o['recall@1']} R@3={o['recall@3']} "
            f"MRR={o['mrr']}"
        )
    n_q = len(next(iter(all_rows.values()), []))
    n_err = sum(m["query_errors"] for m in combined.values())
    out = Path(__file__).parent / "results" / "versus.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(json.dumps(results, indent=2).encode("utf-8"))
    write_mermaid(Path(__file__).parent / "versus.mmd", combined, n_q, n_err)
    board = Path(__file__).parent / "results" / "versus.md"
    write_scoreboard(board, results)
    pfamily = Path(__file__).parent / "results" / "per-family-scoreboard.md"
    write_per_family_board(pfamily, results)
    print(f"wrote {out} + versus.mmd + {board} + {pfamily}")


if __name__ == "__main__":
    main()
