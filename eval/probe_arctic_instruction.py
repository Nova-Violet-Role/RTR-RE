"""Probe: does a model's query prompt recover its retrieval gap?

Isolated experiment, faithful to bench_versus:
- same staging (stage_corpus) and query derivation (per-corpus RNG)
- docs embedded plain (mirrors production indexing path)
- queries embedded plain vs with the model card's prompt
  ("Represent this sentence for searching relevant passages: ")
- pure cosine ranking, R@1/MRR per taxon and overall

The bench's engine embeds queries through the same embed_all() as documents,
so any prompt effect is exactly the delta this probe measures.
"""

import hashlib
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_versus import CORPORA, SEED, derive_dtd_queries, derive_queries, stage_corpus

PROMPT = "Represent this sentence for searching relevant passages: "
CORPUS_NAME = "dtd-family"
MODEL_NAME = "BAAI/bge-base-en-v1.5"
K = 10


def cosine_rank(qvec, docvecs):
    q = qvec / (np.linalg.norm(qvec) + 1e-12)
    sims = []
    for i, d in enumerate(docvecs):
        dn = np.linalg.norm(d)
        sims.append((i, float(np.dot(q, d) / (dn + 1e-12))))
    sims.sort(key=lambda t: t[1], reverse=True)
    return [i for i, _ in sims[:K]]


def metrics(rows):
    r1 = sum(1 for r in rows if r["got"][:1] == [r["expected"]]) / len(rows)
    mrr = sum(
        next((1.0 / (i + 1) for i, n in enumerate(r["got"]) if n == r["expected"]), 0.0)
        for r in rows
    ) / len(rows)
    by_taxon = {}
    for r in rows:
        by_taxon.setdefault(r["taxon"], []).append(r)
    out = {"R@1": round(r1, 4), "MRR": round(mrr, 4), "n": len(rows)}
    for taxon, rs in sorted(by_taxon.items()):
        tr1 = sum(1 for r in rs if r["got"][:1] == [r["expected"]]) / len(rs)
        out[taxon] = {"R@1": round(tr1, 4), "n": len(rs)}
    return out


def main():
    spec = next(s for s in CORPORA if s["name"] == CORPUS_NAME)
    base, proj, staged = stage_corpus(spec, CORPUS_NAME)
    crng = random.Random(
        SEED + int(hashlib.sha256(CORPUS_NAME.encode()).hexdigest()[:8], 16)
    )
    if spec["title"] == "dtd":
        queries = derive_dtd_queries(proj, crng)
    else:
        queries = derive_queries(proj, crng, spec["title"])
    print(f"[{CORPUS_NAME}] staged {len(staged)} files, {len(queries)} queries")

    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=MODEL_NAME)
    doc_files = sorted(Path(proj / "directives").iterdir())
    doc_texts = [f.read_text(encoding="utf-8") for f in doc_files if f.is_file()]
    doc_names = [f.name for f in doc_files if f.is_file()]
    docvecs = [np.asarray(v, dtype=np.float32) for v in model.embed(doc_texts)]
    print(f"embedded {len(docvecs)} docs (dim={docvecs[0].shape[0]})")

    rows_plain = []
    rows_prompt = []
    rows_selective = []
    for taxon, q, expected in queries:
        qv_plain = np.asarray(next(model.embed([q])), dtype=np.float32)
        qv_prompt = np.asarray(next(model.embed([PROMPT + q])), dtype=np.float32)
        if len(q.split()) > 1:
            qv_selective = qv_prompt
        else:
            qv_selective = qv_plain
        got_plain = [doc_names[i] for i in cosine_rank(qv_plain, docvecs)]
        got_prompt = [doc_names[i] for i in cosine_rank(qv_prompt, docvecs)]
        got_selective = [doc_names[i] for i in cosine_rank(qv_selective, docvecs)]
        rows_plain.append({"taxon": taxon, "expected": expected, "got": got_plain})
        rows_prompt.append({"taxon": taxon, "expected": expected, "got": got_prompt})
        rows_selective.append(
            {"taxon": taxon, "expected": expected, "got": got_selective}
        )

    for label, rows in (
        ("plain queries", rows_plain),
        ("with prompt", rows_prompt),
        ("selective (prompt only multiword)", rows_selective),
    ):
        print(f"\n{label}:")
        for k, v in metrics(rows).items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
