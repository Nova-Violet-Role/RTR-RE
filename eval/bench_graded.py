# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Official graded versus: RE:Symbiose vs RAG on frozen gold qrels.

Retrieves document rankings to depth 20 (chunk hits deduped by source),
builds a system-blind pool, and scores nDCG/ERR/MAP against
eval/graded/qrels.json. Isolation mirrors bench_versus v2: one fresh DB +
registry + lexikon per corpus, hashed staged manifest, no live roots.
"""

import argparse
import io
import contextlib
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))
sys.path.insert(0, str(Path(__file__).parent))

import bench_versus as bench
import memory_engine as mem
from graded_metrics import (
    average_precision,
    build_pool,
    err_at_k,
    graded_precision_at_k,
    load_qrels,
    load_queries,
    ndcg_at_k,
    validate_dataset,
)
from memory_engine import MemoryEngine

CUTOFFS = (3, 5, 10, 20)

GRADED_FILE_SUFFIXES = ".md,.nt,.yaml,.yml,.dita,.xml," + ",".join(bench.DTD_SUFFIXES)


def doc_ranking(engine, cfg, query, proj, chunk_k):
    filt = str(proj) if cfg["scoped"] else None
    t0 = time.time()
    try:
        res = engine.search(query, k=chunk_k, project=filt, hybrid=cfg["hybrid"])
        err = ""
    except Exception as e:
        res, err = [], f"{type(e).__name__}: {e}"
    docs = []
    for r in res:
        name = Path(r["metadata"]["source"]).name
        if name not in docs:
            docs.append(name)
    return docs, round((time.time() - t0) * 1000, 1), err


def skipped_corpora(specs, queries_all):
    """Names of corpora with no gold queries (J16: recorded, never silent)."""
    return sorted(
        spec["name"]
        for spec in specs
        if not [q for q in queries_all.values() if q["corpus"] == spec["name"]]
    )


def score_query(ranking, qrels, depth=20):
    ranking = list(dict.fromkeys(ranking))[:depth]
    judged = sum(1 for d in ranking if d in qrels)
    out = {"judged_returned": judged, "unjudged_returned": len(ranking) - judged}
    for k in CUTOFFS:
        out[f"ndcg@{k}"] = round(ndcg_at_k(ranking, qrels, k), 4)
    out["err@10"] = round(err_at_k(ranking, qrels, 10), 4)
    out["gprec@10"] = round(graded_precision_at_k(ranking, qrels, 10), 4)
    out["ap"] = round(average_precision(ranking, qrels), 4)
    return out


def aggregate(rows):
    keys = [f"ndcg@{k}" for k in CUTOFFS] + ["err@10", "gprec@10", "ap"]
    out = {"n": len(rows)}
    for key in keys:
        vals = [r["scores"][key] for r in rows]
        out[key] = round(statistics.fmean(vals), 4) if rows else 0.0
        out[f"ci95_{key}"] = bench.bootstrap_ci(vals) if rows else [0.0, 0.0]
    out["unjudged_returned"] = sum(r["scores"]["unjudged_returned"] for r in rows)
    out["p50_ms"] = sorted(r["ms"] for r in rows)[len(rows) // 2] if rows else 0
    return out


def write_md(path, payload):
    lines = [
        "<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->",
        "<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->",
        "# RE:Symbiose versus RAG — graded scoreboard (generated, do not edit)",
        "",
        f"Dataset {payload['dataset']} | depth {payload['depth']} | "
        f"queries {payload['queries']} | judgments {payload['judgments']}",
        "",
        "| System | nDCG@3 | nDCG@10 | nDCG@20 | ERR@10 | MAP | unjudged |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for system, data in payload["combined"].items():
        lines.append(
            f"| {system} | {data['ndcg@3']:.4f} | {data['ndcg@10']:.4f} | "
            f"{data['ndcg@20']:.4f} | {data['err@10']:.4f} | {data['ap']:.4f} | "
            f"{data['unjudged_returned']} |"
        )
    lines += ["", "Formulas and supervision: eval/graded/PROTOCOL.md.", ""]
    path.write_bytes("\n".join(lines).encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="bench_graded", description="Official graded RE:Symbiose vs RAG bench."
    )
    ap.add_argument("--systems", default="")
    ap.add_argument("--corpora", default="")
    ap.add_argument("--depth", type=int, default=20)
    ap.add_argument("--chunk-k", type=int, default=60)
    ap.add_argument(
        "--queries",
        type=Path,
        default=Path(__file__).parent / "graded" / "queries.json",
    )
    ap.add_argument(
        "--qrels", type=Path, default=Path(__file__).parent / "graded" / "qrels.json"
    )
    args = ap.parse_args()

    queries_all = load_queries(args.queries)
    qrels_all = load_qrels(args.qrels)
    dataset = json.loads(args.queries.read_text(encoding="utf-8")).get(
        "version", "unknown"
    )
    systems = [s.strip() for s in args.systems.split(",") if s.strip()] or list(
        bench.SYSTEMS
    )
    corpora = [c.strip() for c in args.corpora.split(",") if c.strip()]

    os.environ["OPENCODE_MEMORY_FILE_SUFFIXES"] = GRADED_FILE_SUFFIXES
    iso = Path(tempfile.mkdtemp(prefix="rtr-graded-iso-"))
    bench.BENCH_ROOT = iso / "roots"
    bench.BENCH_ROOT.mkdir(parents=True)
    saved = (
        mem.PROJECT_ROOTS,
        mem.REGISTRY_FILE,
        mem.EXTRA_ROOTS_FILE,
        mem.PROJECTS_DIR,
        mem.LEXIKON_GLOBAL_FILE,
    )
    mem.PROJECT_ROOTS = [bench.BENCH_ROOT]
    mem.PROJECTS_DIR = bench.BENCH_ROOT
    mem.EXTRA_ROOTS_FILE = iso / "extra_roots.json"
    mem.LEXIKON_GLOBAL_FILE = iso / "lexikon_global.json"

    results = {
        "dataset": dataset,
        "depth": args.depth,
        "queries": 0,
        "judgments": 0,
        "corpora": {},
        "combined": {},
        "skipped_corpora": [],
    }
    all_rows = {s: [] for s in systems}
    pool_input = {s: {} for s in systems}
    selected = [c for c in bench.CORPORA if not corpora or c["name"] in corpora]
    # J16: skipped corpora are recorded, never silent.
    results["skipped_corpora"] = skipped_corpora(selected, queries_all)
    for name in results["skipped_corpora"]:
        print(f"[{name}] skipped: gold has no queries for this corpus")
    try:
        for spec in [
            c for c in selected if c["name"] not in results["skipped_corpora"]
        ]:
            name = spec["name"]
            queries = [q for q in queries_all.values() if q["corpus"] == name]
            os.environ["OPENCODE_MEMORY_DB_DIR"] = str(iso / f"db-{name}")
            mem.REGISTRY_FILE = iso / f"registry-{name}.json"
            base, proj, staged = bench.stage_corpus(spec, name)
            corpus_qrels = {q["id"]: qrels_all.get(q["id"], {}) for q in queries}
            report = validate_dataset(
                {q["id"]: q for q in queries}, corpus_qrels, {name: staged}
            )
            print(
                f"[{name}] staged {len(staged)} queries {len(queries)} validation={report}"
            )
            engine = MemoryEngine()
            mem.resolve_project_dir(str(proj))
            os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = bench.INDEX_MODELS
            st = engine.index_all()
            engine.close()
            if st.get("status") == "error":
                print(f"[{name}] INDEX REFUSED: {st.get('message')}", file=sys.stderr)
                return 2
            print(f"[{name}] indexed new={st['new']} failed={st['failed']}")
            corp = {"files": len(staged), "queries": len(queries), "systems": {}}
            for system in systems:
                cfg = bench.SYSTEMS[system]
                os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = cfg["models"]
                eng = MemoryEngine()
                rows = []
                with contextlib.redirect_stderr(io.StringIO()):
                    for q in queries:
                        docs, ms, err = doc_ranking(
                            eng, cfg, q["text"], proj, args.chunk_k
                        )
                        doc_ids = [f"{name}/{d}" for d in docs]
                        pool_input[system][q["id"]] = doc_ids
                        rows.append(
                            {
                                "query_id": q["id"],
                                "corpus": name,
                                "taxon": q.get("taxon", ""),
                                "got": doc_ids,
                                "ms": ms,
                                "error": err,
                                "scores": score_query(
                                    doc_ids, qrels_all.get(q["id"], {}), args.depth
                                ),
                            }
                        )
                eng.close()
                all_rows[system].extend(rows)
                corp["systems"][system] = {"metrics": aggregate(rows), "rows": rows}
                m = corp["systems"][system]["metrics"]
                print(
                    f"[{name}] {system}: nDCG@10={m['ndcg@10']} ERR={m['err@10']} MAP={m['ap']}"
                )
            results["corpora"][name] = corp
            results["queries"] += len(queries)
            shutil.rmtree(base, ignore_errors=True)
    finally:
        (
            mem.PROJECT_ROOTS,
            mem.REGISTRY_FILE,
            mem.EXTRA_ROOTS_FILE,
            mem.PROJECTS_DIR,
            mem.LEXIKON_GLOBAL_FILE,
        ) = saved
        shutil.rmtree(iso, ignore_errors=True)

    results["judgments"] = sum(len(v) for v in qrels_all.values())
    results["combined"] = {s: aggregate(rows) for s, rows in all_rows.items()}
    results["pool"] = build_pool(pool_input, depth=args.depth)
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "graded.json").write_bytes(json.dumps(results, indent=2).encode("utf-8"))
    (out_dir / "graded-pool.json").write_bytes(
        json.dumps(results["pool"], indent=2).encode("utf-8")
    )
    write_md(out_dir / "graded.md", results)
    for system, m in results["combined"].items():
        print(
            f"[combined] {system}: nDCG@10={m['ndcg@10']} ERR@10={m['err@10']} MAP={m['ap']} unjudged={m['unjudged_returned']}"
        )
    print(f"wrote {out_dir / 'graded.json'} + graded.md + graded-pool.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
