# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Graded relevance metrics + gold dataset loading (protocol v1).

Frozen formulas (eval/graded/PROTOCOL.md): gain = 2^grade - 1 for
grades 0..3; DCG discount 1/log2(rank+1), rank from 1; ERR stopping
probability (2^g - 1) / 2^3; MAP binarizes at grade >= 2. Rankings are
deduplicated preserving first rank before every metric. Unjudged docs
occupy ranks, gain 0, and are counted separately by callers.
"""

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MAX_GRADE = 3


def gain(grade: int) -> int:
    if grade not in (0, 1, 2, 3):
        raise ValueError(f"grade must be 0..3, got {grade!r}")
    return (1 << grade) - 1


def _dedupe(ranking: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for doc in ranking or []:
        doc = str(doc)
        if doc not in seen:
            seen.add(doc)
            out.append(doc)
    return out


def _dcg(grades: List[int], k: int) -> float:
    return sum(gain(g) / math.log2(rank + 1) for rank, g in enumerate(grades[:k], 1))


def ndcg_at_k(ranking: Iterable[str], qrels: Mapping[str, int], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    judged_grades = [int(g) for g in qrels.values()]
    ideal = _dcg(sorted(judged_grades, reverse=True), k)
    if ideal <= 0:
        return 0.0
    got = [int(qrels.get(doc, 0)) for doc in _dedupe(ranking)]
    return _dcg(got, k) / ideal


def err_at_k(ranking: Iterable[str], qrels: Mapping[str, int], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    total = 0.0
    survive = 1.0
    for rank, doc in enumerate(_dedupe(ranking)[:k], 1):
        p = gain(int(qrels.get(doc, 0))) / float(1 << MAX_GRADE)
        total += survive * p / rank
        survive *= 1.0 - p
    return total


def graded_precision_at_k(
    ranking: Iterable[str], qrels: Mapping[str, int], k: int
) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    docs = _dedupe(ranking)[:k]
    return sum(gain(int(qrels.get(d, 0))) for d in docs) / float(gain(MAX_GRADE) * k)


def average_precision(
    ranking: Iterable[str], qrels: Mapping[str, int], threshold: int = 2
) -> float:
    relevant = {d for d, g in qrels.items() if int(g) >= threshold}
    if not relevant:
        return 0.0
    hits = 0
    total = 0.0
    for rank, doc in enumerate(_dedupe(ranking), 1):
        if doc in relevant:
            hits += 1
            total += hits / rank
    return total / len(relevant)


def build_pool(
    rankings_by_system: Mapping[str, Mapping[str, List[str]]], depth: int = 20
) -> Dict[str, Dict[str, Any]]:
    """Union pool per query. Blind list is doc-ID sorted; provenance apart."""
    if depth <= 0:
        raise ValueError("depth must be positive")
    pool: Dict[str, Dict[str, Any]] = {}
    for system, per_query in rankings_by_system.items():
        for query_id, ranking in per_query.items():
            entry = pool.setdefault(query_id, {"blind": [], "provenance": {}})
            for rank, doc in enumerate(_dedupe(ranking)[:depth], 1):
                entry["provenance"].setdefault(doc, {})[system] = rank
    for entry in pool.values():
        entry["blind"] = sorted(entry["provenance"])
    return pool


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"{path}: invalid JSON: {e}")
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be an object")
    return data


def load_queries(path: Path) -> Dict[str, Dict[str, Any]]:
    data = _load_json(Path(path))
    out: Dict[str, Dict[str, Any]] = {}
    for i, q in enumerate(data.get("queries") or []):
        if not isinstance(q, dict) or not str(q.get("id") or "").strip():
            raise ValueError(f"queries[{i}] missing id")
        qid = str(q["id"])
        if qid in out:
            raise ValueError(f"duplicate query id {qid}")
        if (
            not str(q.get("text") or "").strip()
            or not str(q.get("corpus") or "").strip()
        ):
            raise ValueError(f"query {qid} needs text and corpus")
        out[qid] = dict(q)
    if not out:
        raise ValueError("no queries")
    return out


def load_qrels(path: Path) -> Dict[str, Dict[str, int]]:
    data = _load_json(Path(path))
    out: Dict[str, Dict[str, int]] = {}
    seen = set()
    for i, j in enumerate(data.get("judgments") or []):
        if not isinstance(j, dict):
            raise ValueError(f"judgments[{i}] must be an object")
        qid = str(j.get("query_id") or "")
        doc = str(j.get("doc_id") or "")
        if not qid or not doc:
            raise ValueError(f"judgments[{i}] needs query_id and doc_id")
        if (qid, doc) in seen:
            raise ValueError(f"duplicate judgment {qid} {doc}")
        seen.add((qid, doc))
        grade = j.get("grade")
        if grade not in (0, 1, 2, 3):
            raise ValueError(f"judgments[{i}] grade must be 0..3, got {grade!r}")
        out.setdefault(qid, {})[doc] = int(grade)
    if not out:
        raise ValueError("no judgments")
    return out


def validate_dataset(
    queries: Mapping[str, Mapping[str, Any]],
    qrels: Mapping[str, Mapping[str, int]],
    manifest: Mapping[str, Iterable[str]] | None = None,
) -> Dict[str, Any]:
    errors: List[str] = []
    hist = Counter()
    for qid, docs in qrels.items():
        if qid not in queries:
            errors.append(f"qrel query {qid} has no query")
            continue
        corpus = str(queries[qid].get("corpus") or "")
        known = set((manifest or {}).get(corpus) or [])
        for doc, grade in docs.items():
            hist[str(grade)] += 1
            if (
                manifest is not None
                and doc.split("/", 1)[-1] not in known
                and doc not in known
            ):
                errors.append(f"{qid}: doc {doc} not in {corpus} manifest")
    for qid in queries:
        if qid not in qrels:
            errors.append(f"query {qid} has no judgments")
    return {
        "errors": sorted(errors),
        "queries": len(queries),
        "judged_queries": len(qrels),
        "judgments": int(sum(hist.values())),
        "grade_histogram": dict(sorted(hist.items())),
    }
