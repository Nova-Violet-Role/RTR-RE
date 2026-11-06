# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Blind pool worksheet for graded adjudication.

For every pooled candidate, print title, headings and intent-term snippets
from the real staged document. Candidate order is document-ID sorted and
no system, rank or score is shown: grades are assigned from content, not
from which system surfaced a document (PROTOCOL.md).
"""

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))

import bench_versus as bench
from graded_metrics import load_qrels, load_queries

STOP = {"what", "which", "with", "from", "that", "this", "does", "work", "used"}


def terms(query):
    words = re.findall(
        r"[a-z0-9][a-z0-9_-]{2,}", (query["text"] + " " + query["intent"]).lower()
    )
    return [w for w in dict.fromkeys(words) if w not in STOP]


def headings(text, limit=10):
    out = []
    for line in text.splitlines():
        s = line.strip()
        m = re.search(r"<title[^>]*>(.*?)</title>", s)
        if m:
            out.append(re.sub(r"<[^>]+>", " ", m.group(1)).strip())
        elif s.startswith("#"):
            out.append(s.lstrip("#").strip())
        if len(out) >= limit:
            break
    return out


def snippets(text, words, limit=3, width=180):
    lower = text.lower()
    out = []
    for w in words:
        i = lower.find(w)
        if i < 0:
            continue
        frag = re.sub(r"\s+", " ", text[max(0, i - 70) : i + width]).strip()
        if frag and frag not in out:
            out.append(frag)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="make_pool_worksheet")
    ap.add_argument(
        "--pool",
        type=Path,
        default=Path(__file__).parent.parent / "results" / "graded-pool.json",
    )
    ap.add_argument(
        "--out", type=Path, default=Path(__file__).parent / "pool-worksheet.md"
    )
    args = ap.parse_args()
    queries = load_queries(Path(__file__).parent / "queries.json")
    qrels = load_qrels(Path(__file__).parent / "qrels.json")
    pool = json.loads(args.pool.read_text(encoding="utf-8"))

    iso = Path(tempfile.mkdtemp(prefix="rtr-worksheet-"))
    bench.BENCH_ROOT = iso / "roots"
    bench.BENCH_ROOT.mkdir(parents=True)
    lines = [
        "<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->",
        "<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->",
        "# Blind pool worksheet (generated; adjudicate from content only)",
        "",
    ]
    try:
        staged_docs = {}
        for spec in bench.CORPORA:
            _base, proj, staged = bench.stage_corpus(spec, spec["name"])
            for name in staged:
                staged_docs[f"{spec['name']}/{name}"] = (
                    proj / "directives" / name
                ).read_text(encoding="utf-8")
        for qid in sorted(pool):
            q = queries[qid]
            words = terms(q)
            lines.append(f"## {qid} [{q['corpus']}/{q.get('taxon', '')}] {q['text']}")
            lines.append("")
            lines.append(f"Intent: {q['intent']}")
            lines.append("")
            for doc in pool[qid]["blind"]:
                text = staged_docs.get(doc, "")
                title = bench.extract_title(
                    text, "dita" if doc.endswith(".dita") else "md"
                )
                existing = qrels.get(qid, {}).get(doc)
                mark = f" existing-grade={existing}" if existing is not None else ""
                lines.append(f"### {doc}{mark}")
                lines.append(f"Title: {title}")
                hs = headings(text)
                if hs:
                    lines.append("Headings: " + " | ".join(hs[:8]))
                for frag in snippets(text, words):
                    lines.append(f"> {frag}")
                lines.append("")
    finally:
        shutil.rmtree(iso, ignore_errors=True)
    args.out.write_bytes("\n".join(lines).encode("utf-8"))
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
