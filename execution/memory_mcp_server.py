# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import sys
import os
import json
import re
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

try:
    import memory_engine as mem
    from memory_engine import MemoryEngine
except ImportError:  # flat dev layout (tests put execution/ on sys.path)
    from . import memory_engine as mem
    from .memory_engine import MemoryEngine
from fastmcp import FastMCP

try:
    from tui_renderer import TUIRenderer
except ImportError:  # installed package layout (execution.*)
    from .tui_renderer import TUIRenderer

try:
    import context_budget
    import span_indexer
    import symbiose_worker as sw
except ImportError:  # installed package layout (execution.*)
    from . import context_budget, span_indexer
    from . import symbiose_worker as sw

engine = MemoryEngine()

mcp = FastMCP("memory")

_INBOX_LOCK = threading.Lock()


def _error_text(exc: Exception) -> str:
    """Readable error text: bare exceptions (MemoryError, KeyError())
    stringify empty, which rendered panels as a blank 'Error: '."""
    return str(exc) or repr(exc)


def _wiki_paths(project: str) -> dict | str:
    """Detect which wiki naming convention a project uses.
    Returns {inbox, concepts} or an error string."""
    directives = mem.resolve_project_dir(project) / "directives"
    if not directives.exists():
        return f"Error: No directives/ folder in {project}"

    design_inbox = directives / "design_wiki.md"
    design_concepts = directives / "design_wiki_concepts"
    wiki_inbox = directives / "wiki_inbox.md"
    wiki_concepts = directives / "wiki_concepts"

    if design_inbox.exists() or design_concepts.exists():
        return {
            "inbox": design_inbox,
            "concepts": design_concepts,
            "variant": "design_wiki",
        }

    return {
        "inbox": wiki_inbox,
        "concepts": wiki_concepts,
        "variant": "wiki",
    }


@mcp.tool()
def memory_discover(project: str) -> str:
    """Discover wiki files and naming convention for a project."""
    paths = _wiki_paths(project)
    if isinstance(paths, str):
        return TUIRenderer.render_panel(f"Discover: {project}", [paths], status="info")

    inbox = paths["inbox"]
    concepts = paths["concepts"]

    lines = []
    if inbox.exists():
        size = len(inbox.read_text(encoding="utf-8"))
        lines.append(f"Inbox: {inbox.name} ({size} chars)")
    else:
        lines.append(f"Inbox: {inbox.name} (not yet created)")

    if concepts.exists():
        subdirs = sorted(d.name for d in concepts.iterdir() if d.is_dir())
        if subdirs:
            lines.append(f"Concepts ({len(subdirs)} subcategories):")
            for s in subdirs:
                files = [f.name for f in (concepts / s).iterdir() if f.suffix == ".md"]
                lines.append(f"  {s}/ ({len(files)} files)")
        else:
            lines.append("Concepts: (empty)")
    else:
        lines.append("Concepts: (not yet created)")

    lines.append(f"Convention variant: {paths['variant']}")
    return TUIRenderer.render_panel(f"Discover: {project}", lines, status="stats")


@mcp.tool()
def memory_search(query: str, k: int = 3, project: str = "") -> str:
    """Semantic & Hybrid search across indexed wikis."""
    try:
        results = engine.search(query, k=k, project=project or None)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Search Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    if not results:
        return TUIRenderer.render_panel(
            "Search: 0 results",
            [f"No matching documents for: '{query}'"],
            status="search",
        )

    lines = [f'Query: "{query}"', f"Candidates returned: {len(results)}", ""]

    for idx, res in enumerate(results):
        meta = res["metadata"]
        lines.append(
            f"{idx + 1}. [{meta['rel_path']}] (Similarity: {res['score']:.4f})"
        )
        lines.append(f"   Title: {meta.get('title', 'Unknown')}")
        lines.append(f"   Excerpt: {res['document'][:180].replace(chr(10), ' ')}...")
        lines.append("")

    return TUIRenderer.render_panel("Semantic Search Results", lines, status="search")


@mcp.tool()
def memory_list(project: str = "") -> str:
    """List indexed memory files."""
    try:
        registry = engine.load_registry()
    except Exception as e:
        return TUIRenderer.render_panel(
            "List Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    if not registry:
        return TUIRenderer.render_panel(
            "List: 0 files", ["No files indexed in the local database."], status="info"
        )

    files_by_project = {}
    want = mem.project_filter_key(project) if project else ""
    for file_path, hash_val in registry.items():
        proj, rel, _ = mem.describe_indexed_path(file_path)
        if want and proj != want:
            continue
        files_by_project.setdefault(proj, []).append((rel, hash_val[:8]))

    if not files_by_project:
        return TUIRenderer.render_panel(
            f"List: {project}",
            [f"No files indexed for project '{project}'"],
            status="info",
        )

    lines = []
    for proj in sorted(files_by_project):
        lines.append(f"📁 {proj}/ ({len(files_by_project[proj])} files):")
        for rel_path, h in sorted(files_by_project[proj]):
            lines.append(f"  📄 {rel_path} (sha: {h})")

    return TUIRenderer.render_panel("Indexed Files List", lines, status="stats")


@mcp.tool()
def memory_delete(path: str) -> str:
    """Delete a memory file from storage and index."""
    refused = engine._require_writer("memory_delete")
    if refused is not None:
        return TUIRenderer.render_panel(
            "Delete Refused", [refused["message"]], status="error"
        )
    p = Path(path)
    full_path = p if p.is_absolute() else mem.PROJECTS_DIR / path
    if not full_path.exists():
        return TUIRenderer.render_panel(
            "Delete Failure", [f"Error: {path} does not exist."], status="error"
        )
    if str(full_path) not in engine.load_registry():
        return TUIRenderer.render_panel(
            "Delete Refused",
            [f"Error: {path} is not indexed; refusing to delete outside the index."],
            status="error",
        )
    try:
        for col in engine.rtr_collections().values():
            existing = col.get(where={"source": str(full_path)})
            if existing and existing["ids"]:
                col.delete(ids=existing["ids"])
        full_path.unlink()
        registry = engine.load_registry()
        if str(full_path) in registry:
            del registry[str(full_path)]
            engine.save_registry(registry)
        return TUIRenderer.render_panel(
            "Memory Deleted",
            [f"Successfully removed {path} from filesystem and DB."],
            status="ok",
        )
    except Exception as e:
        return TUIRenderer.render_panel(
            "Delete Failure", [f"Error deleting {path}: {e}"], status="error"
        )


@mcp.tool()
def memory_inbox_write(project: str, content: str) -> str:
    """Append a learning block to the project's memory inbox."""
    paths = _wiki_paths(project)
    if isinstance(paths, str):
        return TUIRenderer.render_panel("Inbox Append Failure", [paths], status="error")

    inbox = paths["inbox"]
    inbox.parent.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d %H:%M")
    block = f"\n## Ingest {timestamp}\n\n{content.strip()}\n"
    if not inbox.exists():
        label = "Design Wiki" if paths["variant"] == "design_wiki" else "Wiki"
        try:
            with open(inbox, "x", encoding="utf-8") as f:
                f.write(f"# {label} Inbox\n")
        except FileExistsError:
            pass
    with _INBOX_LOCK:
        with open(inbox, "a", encoding="utf-8") as f:
            f.write(block)

    return TUIRenderer.render_panel(
        "Inbox Appended",
        [f"Appended entry to {inbox.name} successfully."],
        status="write",
    )


@mcp.tool()
def memory_inbox_read(project: str) -> str:
    """Read the current project's memory inbox content."""
    paths = _wiki_paths(project)
    if isinstance(paths, str):
        return TUIRenderer.render_panel("Inbox Read Failure", [paths], status="error")

    if not paths["inbox"].exists():
        return TUIRenderer.render_panel(
            "Inbox Empty", ["Inbox file does not exist yet."], status="info"
        )

    lines = paths["inbox"].read_text(encoding="utf-8").split("\n")
    return TUIRenderer.render_panel(
        f"Inbox: {project}",
        lines[:15] + (["... (truncated)"] if len(lines) > 15 else []),
        status="ok",
    )


@mcp.tool()
def memory_write(project: str, filename: str, content: str) -> str:
    """Write concept file directly and compute relations."""
    paths = _wiki_paths(project)
    if isinstance(paths, str):
        return TUIRenderer.render_panel("Write Failure", [paths], status="error")

    refused = engine._require_writer("memory_write")
    if refused is not None:
        return TUIRenderer.render_panel(
            "Write Refused", [refused["message"]], status="error"
        )

    concepts_dir = paths["concepts"]
    concepts_dir.mkdir(parents=True, exist_ok=True)

    try:
        filename = mem.safe_concept_filename(filename)
    except ValueError as e:
        return TUIRenderer.render_panel(
            "Write Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    filepath = concepts_dir / filename
    filepath.write_text(content.strip(), encoding="utf-8")

    related_links = []
    try:
        query = filename.replace(".md", "").replace("_", " ")
        results = engine.search(query=query, k=4, project=None)
        seen = set()
        for res in results:
            src = Path(res["metadata"]["source"])
            if src == filepath or src in seen:
                continue
            seen.add(src)
            if res["score"] > 0.50:
                rel = os.path.relpath(src, start=concepts_dir).replace("\\", "/")
                related_links.append(
                    f"- [{src.name}]({rel}) (Similarity: {res['score']:.2f})"
                )
    except Exception:
        pass

    if related_links:
        filepath.write_text(
            filepath.read_text(encoding="utf-8")
            + "\n\n## Related Knowledge\n"
            + "\n".join(related_links)
            + "\n",
            encoding="utf-8",
        )

    s = engine.index_all()

    lines = [
        f"Saved to: {filepath.name}",
        f"Index status: {s['new']} new, {s['updated']} updated",
        f"Auto-linked relations: {len(related_links)}",
    ]
    for r in related_links:
        lines.append(f"  {r}")

    return TUIRenderer.render_panel("Direct Wiki Write", lines, status="write")


@mcp.tool()
def memory_organize(project: str) -> str:
    """Extract, link, and structure concepts from the project's inbox."""
    paths = _wiki_paths(project)
    if isinstance(paths, str):
        return TUIRenderer.render_panel("Organize Failure", [paths], status="error")

    refused = engine._require_writer("memory_organize")
    if refused is not None:
        return TUIRenderer.render_panel(
            "Organize Refused", [refused["message"]], status="error"
        )

    inbox = paths["inbox"]
    concepts_dir = paths["concepts"]
    concepts_dir.mkdir(parents=True, exist_ok=True)

    if not inbox.exists():
        return TUIRenderer.render_panel(
            "Organize", ["No inbox found to organize."], status="info"
        )

    source = inbox.read_text(encoding="utf-8").strip()
    if not source or len(source) < 20:
        return TUIRenderer.render_panel("Organize", ["Inbox is empty."], status="info")

    sections = re.split(r"\n##\s+", source)
    if len(sections) <= 1:
        return TUIRenderer.render_panel(
            "Organize", ["No concept sections found in inbox."], status="info"
        )

    sections.pop(0)
    processed = []
    skipped = []

    for section in sections:
        lines = section.strip().split("\n")
        title = lines[0].strip() if lines else "untitled"
        body = "\n".join(lines[1:]).strip()
        if not title or not body:
            skipped.append(section.strip())
            continue

        safe_name = (
            re.sub(r"[^a-zA-Z0-9_\-\s]", "", title).strip().replace(" ", "_").lower()
        )
        if not safe_name:
            safe_name = f"concept_{int(time.time())}"

        cats = sorted(d.name for d in concepts_dir.iterdir() if d.is_dir())
        best_cat = None
        best_score = 0.0
        if cats:
            try:
                cat_embs = list(
                    engine.model.embed(
                        [f"concept about {c.replace('_', ' ')}" for c in cats]
                    )
                )
                concept_emb = list(engine.model.embed([f"{title}: {body[:200]}"]))[0]
                for i, emb in enumerate(cat_embs):
                    sim = sum(a * b for a, b in zip(concept_emb, emb)) / (
                        (sum(a * a for a in concept_emb) ** 0.5)
                        * (sum(b * b for b in emb) ** 0.5)
                        + 1e-10
                    )
                    if sim > best_score:
                        best_score = sim
                        best_cat = cats[i]
            except Exception:
                pass

        cat_dir = concepts_dir / (
            best_cat if best_cat and best_score > 0.55 else f"topic_{safe_name}"
        )
        cat_dir.mkdir(parents=True, exist_ok=True)

        existing_files = sorted(cat_dir.glob("*.md"))

        related_links = []
        try:
            results = engine.search(
                query=f"{title}: {body[:200]}", k=3, project=project
            )
            seen = set()
            for res in results:
                src = Path(res["metadata"]["source"])
                if src in seen:
                    continue
                seen.add(src)
                if res["score"] > 0.60:
                    rel = os.path.relpath(src, start=cat_dir).replace("\\", "/")
                    related_links.append(f"- [{src.stem.replace('_', ' ')}]({rel})")
        except Exception:
            pass

        content = f"# {title}\n\n{body}\n"
        if related_links:
            content += "\n## Related\n" + "\n".join(related_links) + "\n"
        content += (
            f"\n---\n*Organized from inbox on {time.strftime('%Y-%m-%d %H:%M')}*\n"
        )

        concept_file = cat_dir / f"{safe_name}.md"
        concept_file.write_text(content, encoding="utf-8")

        link_ref = f"[[{safe_name}]]"
        for ef in existing_files:
            if link_ref not in ef.read_text(encoding="utf-8"):
                ef.write_text(
                    ef.read_text(encoding="utf-8").rstrip()
                    + f"\n- {link_ref} — {title}\n",
                    encoding="utf-8",
                )

        processed.append(f"  {concept_file.name} -> {cat_dir.name}/")

    label = "Design Wiki" if paths["variant"] == "design_wiki" else "Wiki"
    if skipped:
        leftovers = "".join(f"\n## {s}\n" for s in skipped)
        inbox.write_text(f"# {label} Inbox\n{leftovers}", encoding="utf-8")
        cleared_line = f"Inbox filed; {len(skipped)} section(s) kept (unprocessable)."
    else:
        inbox.write_text(f"# {label} Inbox\n", encoding="utf-8")
        cleared_line = "Inbox cleared and filed."
    s = engine.index_all()

    lines = (
        [
            cleared_line,
            f"Filed concepts ({len(processed)}):",
        ]
        + processed
        + [f"Index updated: {s['new']} new, {s['updated']} updated"]
    )
    return TUIRenderer.render_panel(
        "Graph Maintainer Complete", lines, status="organize"
    )


@mcp.tool()
def memory_stats() -> str:
    """Retrieve corpus statistics."""
    try:
        stats = engine.stats()
    except Exception as e:
        return TUIRenderer.render_panel(
            "Stats Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    lines = [
        f"Total Files Indexed:  {stats['total_files']}",
        f"Total Vector Chunks:  {stats['total_chunks']}",
        f"Vector Database Size: {stats['db_size_mb']:.2f} MB",
        "",
        "Project Breakdown:",
    ]
    for proj, count in sorted(stats["projects"].items()):
        lines.append(f"  - {proj}: {count} files")

    return TUIRenderer.render_panel("Memory Database Status", lines, status="stats")


@mcp.tool()
def memory_index(force: bool = False, project: str = "", repair: bool = False) -> str:
    """Force incremental re-indexing (project ref also registers out-of-roots dirs). repair=True rebuilds the hash registry from Chroma contents without re-embedding."""
    if repair:
        try:
            res = engine.repair_registry()
        except Exception as e:
            return TUIRenderer.render_panel(
                "Repair Failure", [f"Error: {_error_text(e)}"], status="error"
            )
        return TUIRenderer.render_panel(
            "Registry Repaired",
            [
                f"Relinked: {res.get('repaired', 0)} files",
                f"Total:    {res.get('total', 0)} files",
            ],
            status="index",
        )
    start = time.time()
    try:
        s = engine.index_all(force=force, projects=[project] if project else [])
    except Exception as e:
        return TUIRenderer.render_panel(
            "Indexing Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    duration = time.time() - start
    if s.get("status") == "error":
        return TUIRenderer.render_panel(
            "Indexing Refused",
            [s.get("message", "Refused."), f"Duration:      {duration:.2f}s"],
            status="index",
        )
    lines = [
        f"Files Scanned: {s['scanned']}",
        f"New Indexed:   {s['new']}",
        f"Updated:       {s['updated']}",
        f"Unchanged:     {s['unchanged']}",
        f"Failed:        {s['failed']}",
        f"Duration:      {duration:.2f}s",
    ]
    return TUIRenderer.render_panel("Incremental Indexing", lines, status="index")


@mcp.tool()
def memory_init_project(project: str, variant: str = "wiki") -> str:
    """Bootstrap standard Harness Engineering structures in a project directory."""
    try:
        res = engine.init_project(project, variant)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Bootstrap Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    lines = [res["message"], "", "Created Directories:"]
    for d in res["created_directories"]:
        lines.append(f"  📁 {d}")

    lines.append("")
    lines.append("Created Baseline Documents:")
    for f in res["created_files"]:
        lines.append(f"  📄 {f}")

    return TUIRenderer.render_panel("Harness Bootstrapping", lines, status="bootstrap")


@mcp.tool()
def memory_consolidate(project: str) -> str:
    """Clean, merge, and de-duplicate redundant concept markdown files."""
    try:
        res = engine.consolidate_wiki(project)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Consolidation Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    if res.get("status") == "error":
        return TUIRenderer.render_panel(
            "Consolidation Error", [res["message"]], status="error"
        )

    lines = [res["message"], "", "Consolidation Log:"]
    if res.get("merged"):
        for m in res["merged"]:
            lines.append(f"  🧹 {m}")
    else:
        lines.append("  No duplicate files discovered.")

    return TUIRenderer.render_panel("Corpus Consolidation", lines, status="organize")


@mcp.tool()
def memory_session_start(project: str) -> str:
    """Automate Session Start (Phase 1): Restores previous working state using Harness state logs."""
    try:
        res = engine.restore_session_state(project)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Restoration Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    if res.get("status") == "error":
        return TUIRenderer.render_panel(
            "Restoration Error", [res["message"]], status="error"
        )

    lines = [
        "Project context parsed successfully.",
        f'Query context: "{res["query_context"]}..."',
        "---",
        "Active Goals:",
    ]

    if res["active_goals"]:
        for g in res["active_goals"]:
            lines.append(f"  🎯 {g}")
    else:
        lines.append("  No active goals parsed.")

    lines.append("")
    lines.append("Blockers / Open Issues:")
    if res["blockers"]:
        for b in res["blockers"]:
            lines.append(f"  ⚠️ {b}")
    else:
        lines.append("  No blockers discovered.")

    lines.append("")
    lines.append("Recent Discoveries / Decisions:")
    if res["recent_discoveries"]:
        for d in res["recent_discoveries"]:
            lines.append(f"  💡 {d}")
    else:
        lines.append("  No recent discoveries recorded.")

    lines.append("")
    lines.append("Pre-fetched Relevant Memory Concepts:")
    if res["recommended_files"]:
        for f in res["recommended_files"]:
            lines.append(f"  📄 {f}")
    else:
        lines.append("  No high-signal historical concepts matched.")

    return TUIRenderer.render_panel(
        f"Session Start: {project}", lines, status="restore"
    )


@mcp.tool()
def memory_explain_search(query: str, k: int = 3, project: str = "") -> str:
    """Explain search rankings with a clean mathematical score breakdown table."""
    try:
        results = engine.explain_search(query, k=k, project=project or None)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Explain Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    if not results:
        return TUIRenderer.render_panel(
            "Explain: 0 results",
            [f"No matching documents for: '{query}'"],
            status="explain",
        )

    lines = [f'Query: "{query}"', "Mathematical Score Breakdown Table:", ""]

    for idx, res in enumerate(results):
        lines.append(f"{idx + 1}. File: {res['rel_path']}")
        lines.append(f"   Final Score: {res['final']:.4f}")
        w = res["weights"]
        # Table of details (actual mix weights, not defaults)
        lines.append("   ┌────────────┬────────┬──────────┐")
        lines.append("   │ Metric     │ Value  │ Weight   │")
        lines.append("   ├────────────┼────────┼──────────┤")
        lines.append(f"   │ Dense      │ {res['dense']:.4f} │ x{w['dense']:.2f}    │")
        lines.append(f"   │ BM25       │ {res['bm25']:.4f} │ x{w['bm25']:.2f}    │")
        lines.append(
            f"   │ Recency    │ {res['recency']:.4f} │ x{w['recency']:.2f}    │"
        )
        lines.append(
            f"   │ Importance │ {res['importance']:.4f} │ x{w['importance']:.2f}    │"
        )
        lines.append("   └────────────┴────────┴──────────┘")
        lines.append("")

    return TUIRenderer.render_panel(
        "Observability: Explain Search", lines, status="explain"
    )


@mcp.tool()
def memory_reflect_session(project: str, conversation_text: str = "") -> str:
    """Generate a structured session reflection report under directives/sessions/."""
    try:
        res = engine.reflect_session(project, conversation_text)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Reflection Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    events = res.get("knowledge_events", [])
    lines = [
        f"Session reflection generated report: {Path(res['report_path']).name}",
        "",
        "Knowledge Events Extracted:",
    ]
    for ev in events if events else []:
        lines.append(
            f"  - [{ev.get('type', 'observation').upper()}] {ev.get('concept', 'General')} — {ev.get('evidence', '')}"
        )
    if not events:
        lines.append("  - None")

    return TUIRenderer.render_panel("Session Reflection Logged", lines, status="ok")


@mcp.tool()
def memory_materialize_concepts(project: str) -> str:
    """Materialize parsed session learnings into ID-based (concept_NNN) markdown concept nodes."""
    try:
        res = engine.materialize_concepts(project)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Materialization Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    if res.get("status") == "error":
        return TUIRenderer.render_panel(
            "Materialization Error", [res["message"]], status="error"
        )

    lines = [
        res.get("message", "Concept materialization pipeline completed."),
        "",
        "Materialization Log:",
    ]
    if res.get("materialized"):
        for m in res["materialized"]:
            lines.append(f"  ✨ {m}")
    else:
        lines.append("  No new or modified concepts found to materialize.")

    return TUIRenderer.render_panel("Concept Materialization", lines, status="ok")


@mcp.tool()
def memory_update_graph(project: str) -> str:
    """Analyze concept nodes and establish reciprocal bidirectional Obsidian-style [[wikilinks]]."""
    try:
        res = engine.update_concept_graph(project)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Graph Update Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    if res.get("status") == "error":
        return TUIRenderer.render_panel(
            "Graph Update Error", [res["message"]], status="error"
        )

    lines = [
        res.get("message", "Graph structure updated."),
        f"Total links added or normalized: {res.get('links_added_or_normalized', 0)}",
    ]
    return TUIRenderer.render_panel(
        "Bidirectional Graph Auto-Linker", lines, status="organize"
    )


@mcp.tool()
def memory_reference_add(project: str, conversation_text: str = "") -> str:
    """Bounded memory-reference insert: embed exactly this conversation text
    into the chroma collections as a memory reference. This is the compact's
    path — it never scans the corpus, never reindexes roots, and never runs
    janitor/lexikon/graph; it only persists the compacted conversation so
    memory_search can retrieve it (measured: the full session_commit
    orchestrator on a fresh DB grew to ~20 GB and crashed the host)."""
    try:
        res = engine.add_memory_reference(project, conversation_text)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Memory Reference Add Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    if res.get("status") == "error":
        return TUIRenderer.render_panel(
            "Memory Reference Add Failure",
            [res.get("message", "unknown")],
            status="error",
        )
    return TUIRenderer.render_panel(
        "Memory Reference Added",
        [
            f"Chunks added: {res.get('chunks_added', 0)}",
            f"Project: {project}",
            "Retrievable via memory_search.",
        ],
        status="success",
    )


@mcp.tool()
def memory_session_commit(
    project: str, conversation_text: str = "", full_reindex: bool = False
) -> str:
    """End Session Master Orchestrator: runs reflect, materialize, update graph, and vector index in one step."""
    try:
        res = engine.session_commit(project, conversation_text, full_reindex)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Session Commit Failure", [f"Error: {_error_text(e)}"], status="error"
        )

    if res.get("status") == "error":
        return TUIRenderer.render_panel(
            "Session Commit Refused", [res.get("message", "Refused.")], status="error"
        )

    events = res.get("knowledge_events", [])
    event_counts = {}
    for ev in events:
        t = ev.get("type", "observation")
        event_counts[t] = event_counts.get(t, 0) + 1

    lines = [
        "Master session commit succeeded.",
        f"Report: {Path(res['report_path']).name}",
        "",
        "Extracted Knowledge Events:",
    ]
    if event_counts:
        for t, count in sorted(event_counts.items()):
            lines.append(f"  - {t.title()}: {count} events")
    else:
        lines.append("  - None")

    lines.extend(
        [
            "",
            "Graph & Index Evolution:",
            f"  Materialized:      {len(res['materialized_log'])} concepts",
            f"  Bidirectional links: {res['links_updated']} links updated",
            f"  Vector Index stats: {res['index_stats']['new']} new, {res['index_stats']['updated']} updated chunks",
            f"  Lexikon: {res.get('lexikon_message', '')}",
            f"  Janitor freed: {res.get('janitor_freed', 0)} chunks",
            f"  Index refusal: {res['index_refusal']}"
            if res.get("index_refusal")
            else "  Index: incremental, unchanged files skipped",
        ]
    )
    return TUIRenderer.render_panel("Session Commit Complete", lines, status="ok")


@mcp.tool()
def memory_lexikon_add(
    project: str, term: str, definition: str = "", aliases: str = ""
) -> str:
    """Hand-add a Lexikon/Glossary term (project or _global user lexikon)."""
    alias_list = [a.strip() for a in aliases.split(",") if a.strip()]
    try:
        res = engine.add_lexikon_term(project, term, definition, alias_list)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Lexikon Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    if res.get("status") == "error":
        return TUIRenderer.render_panel(
            "Lexikon Error", [res["message"]], status="error"
        )
    return TUIRenderer.render_panel("Lexikon Updated", [res["message"]], status="write")


@mcp.tool()
def memory_lexikon_show(project: str) -> str:
    """Show merged Lexikon/Glossary terms (_global + project)."""
    try:
        lex = engine.get_lexikon(project)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Lexikon Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    if not lex:
        return TUIRenderer.render_panel(
            "Lexikon Empty", ["No terms yet."], status="info"
        )
    lines = [f"Terms: {len(lex)}", ""]
    for key in sorted(lex)[:20]:
        e = lex[key] if isinstance(lex[key], dict) else {}
        aliases = ", ".join(e.get("aliases", []) or [])
        extra = f" (aka: {aliases})" if aliases else ""
        lines.append(f"  - {e.get('term', key)}{extra} [{e.get('source', '?')}]")
    if len(lex) > 20:
        lines.append(f"  ... and {len(lex) - 20} more")
    return TUIRenderer.render_panel(f"Lexikon: {project}", lines, status="stats")


@mcp.tool()
def memory_lexikon_build(project: str) -> str:
    """Derive project Lexikon from concept registry and session reports."""
    try:
        res = engine.build_lexikon(project)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Lexikon Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    if res.get("status") == "error":
        return TUIRenderer.render_panel(
            "Lexikon Error", [res["message"]], status="error"
        )
    return TUIRenderer.render_panel("Lexikon Built", [res["message"]], status="ok")


@mcp.tool()
def memory_janitor(dry_run: bool = False) -> str:
    """Delete orphan chunks whose source files no longer exist on disk."""
    try:
        res = engine.janitor(dry_run=dry_run)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Janitor Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    lines = [f"Total chunks freed: {res['freed']}", ""]
    for name, info in sorted(res["collections"].items()):
        if "error" in info:
            lines.append(f"  - {name}: ERROR {info['error']}")
        else:
            lines.append(f"  - {name}: {info['chunks']} chunks, freed {info['freed']}")
    return TUIRenderer.render_panel("Janitor", lines, status="organize")


@mcp.tool()
def memory_repair(dry_run: bool = False) -> str:
    """Repair the memory loop: conform the registry, purge orphans, report.

    The one update-conformance path: registry relinks from Chroma truth,
    janitor frees dead chunks and prunes dead roots, and the report names
    every piece. Dry run measures without writing.
    """
    recall = [
        "Symbiotising in process — accessing the digital world,",
        "growing piece by piece until every span is home.",
        "",
    ]
    if engine.read_only:
        return TUIRenderer.render_panel(
            "Repair Refused",
            ["The database lock is held elsewhere; repair needs the writer."],
            status="error",
        )
    try:
        rep = engine.repair_registry()
    except Exception as e:
        return TUIRenderer.render_panel(
            "Repair Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    if rep.get("status") == "error":
        return TUIRenderer.render_panel(
            "Repair Failure", [rep.get("message", "unknown")], status="error"
        )
    try:
        jan = engine.janitor(dry_run=dry_run)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Repair Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    lines = list(recall)
    lines.append(f"Registry relinked: {rep.get('repaired', 0)} files")
    lines.append(f"Registry total: {rep.get('total', 0)} files")
    lines.append(f"Chunks freed: {jan.get('freed', 0)}")
    if jan.get("pruned_roots"):
        lines.append(f"Roots pruned: {len(jan['pruned_roots'])}")
    if dry_run:
        lines.append("Dry run: measured only, nothing written.")
    return TUIRenderer.render_panel("Repair", lines, status="organize")


_symbiose_workers: dict = {}


def _symbiose_for(project: str) -> sw.SymbioseWorker:
    """One background worker per project, sinking to its keeper memory root."""
    key = str(mem.resolve_project_dir(project)) if project else "_default"
    w = _symbiose_workers.get(key)
    if w is None:
        w = sw.open_project_worker(key)
        _symbiose_workers[key] = w
    return w


@mcp.tool()
def memory_symbiose_submit(project: str, messages_json: str) -> str:
    """Submit messages (JSON array) for background RE:Symbiose eviction.

    Returns a ticket immediately; compression never pauses the live turn.
    Evicted read+written spans sink verbatim to <project>/.opencode/memory/.
    """
    try:
        ticket = sw.submit_json(_symbiose_for(project), messages_json)
    except ValueError as e:
        return TUIRenderer.render_panel(
            "Symbiose Submit Refused", [f"Error: {_error_text(e)}"], status="error"
        )
    lines = [
        f"Ticket: {ticket['id']}",
        f"Hash:   {ticket['hash']}",
        f"Status: {ticket['status']}",
        "Poll with memory_symbiose_poll; live messages are never mutated.",
    ]
    return TUIRenderer.render_panel("RE:Symbiose Submitted", lines, status="ok")


@mcp.tool()
def memory_symbiose_poll(project: str, ticket_id: int) -> str:
    """Poll a symbiose ticket: pending/ready/failed/cooldown/cached/unknown."""
    try:
        worker = _symbiose_for(project)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Symbiose Poll Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    try:
        # Same project key as _symbiose_for: the drain sweeps the worker's own root.
        key = str(mem.resolve_project_dir(project)) if project else "_default"
        memory_dir = Path(key) / ".opencode" / "memory"
        drain_report = sw.drain_submit_sidecars(
            worker, memory_dir, limit=25, wait_timeout=5
        )
        drain_lines = sw.drain_panel_lines(drain_report)
    except Exception as e:
        drain_lines = [f"Drain error: {e}"]
    try:
        t = worker.poll(ticket_id)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Symbiose Poll Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    lines = drain_lines + [f"{k}: {v}" for k, v in sorted(t.items())]
    return TUIRenderer.render_panel("RE:Symbiose Ticket", lines, status="stats")


@mcp.tool()
def memory_symbiose_drain(project: str, limit: int = 5) -> str:
    """Drain keeper submit sidecars through the Compressor (TODO-38 auto path).

    Submits pending rtrre-*.submit.json sidecars oldest-first, waits each
    ticket ready, and deletes consumed sidecars. Bounded per sweep; the
    report names consumed, left, and quarantined files.
    """
    try:
        # Same project key as _symbiose_for: the drain sweeps the worker's own root.
        key = str(mem.resolve_project_dir(project)) if project else "_default"
        memory_dir = Path(key) / ".opencode" / "memory"
        report = sw.drain_submit_sidecars(
            _symbiose_for(project), memory_dir, limit=limit
        )
    except Exception as e:
        return TUIRenderer.render_panel(
            "Symbiose Drain Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    return TUIRenderer.render_panel(
        "RE:Symbiose Drain", sw.drain_panel_lines(report), status="ok"
    )


@mcp.tool()
def memory_symbiose_compress(
    project: str, messages_json: str, target_tokens: int
) -> str:
    """Fire the Compressor directly with a per-ticket target (RRD-75/79).

    The target is the verbatim tail; the trigger stays preset/env.
    Returns a ticket immediately; compression never pauses the live turn.
    Thinking and tool parts ride the messages untouched into the budget.
    """
    try:
        ticket = sw.compress_json(_symbiose_for(project), messages_json, target_tokens)
    except ValueError as e:
        return TUIRenderer.render_panel(
            "Symbiose Compress Refused", [f"Error: {_error_text(e)}"], status="error"
        )
    lines = [
        f"Ticket: {ticket['id']}",
        f"Hash:   {ticket['hash']}",
        f"Status: {ticket['status']}",
        f"Target: {target_tokens} (per-ticket override; trigger stays preset/env)",
        "Poll with memory_symbiose_poll; live messages are never mutated.",
    ]
    return TUIRenderer.render_panel("RE:Symbiose Fired", lines, status="ok")


@mcp.tool()
def memory_keeper_evict_now(project: str, mode: str, amount: int) -> str:
    """Arm a keeper one-shot eviction (fires on the next exchange).

    mode tokens: evict ~amount tokens oldest-first. mode messages:
    evict amount oldest messages. Protections still hold; the flag
    self-clears after firing. Writes the watched keeper config file.
    """
    if mode not in ("tokens", "messages"):
        return TUIRenderer.render_panel(
            "Evict Refused",
            [f"Error: mode must be tokens or messages, got {mode!r}."],
            status="error",
        )
    try:
        amount = int(amount)
        if amount <= 0:
            raise ValueError("amount must be positive")
    except (ValueError, TypeError):
        return TUIRenderer.render_panel(
            "Evict Refused",
            [f"Error: amount must be a positive integer, got {amount!r}."],
            status="error",
        )
    try:
        project_dir = mem.resolve_project_dir(project)
    except Exception as e:
        return TUIRenderer.render_panel(
            "Evict Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    cfg_path = project_dir / ".opencode" / "rtr-re-keeper.json"
    try:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        current = {}
        if cfg_path.exists():
            current = json.loads(cfg_path.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                current = {}
        key = "evictTokensNow" if mode == "tokens" else "evictMessagesNow"
        current[key] = amount
        cfg_path.write_text(
            json.dumps(current, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    except Exception as e:
        return TUIRenderer.render_panel(
            "Evict Failure", [f"Error: {_error_text(e)}"], status="error"
        )
    return TUIRenderer.render_panel(
        "One-Shot Armed",
        [
            f"Keeper will evict {amount} {mode} on the next exchange.",
            f"Config: {cfg_path.name}",
        ],
        status="ok",
    )


@mcp.tool()
def memory_doctor() -> str:
    """Process health: RSS, live threads with top frames, uptime.

    Stdlib-only py-spy companion: when the server burns CPU or RAM,
    this names the hot threads without attaching a profiler.
    """
    import threading
    import time as _time

    rss = mem.process_rss_mb()
    frames = mem.thread_top_frames(limit=3)
    uptime = _time.time() - _SERVER_STARTED_AT
    lines = [
        f"RSS: {rss:.0f} MB",
        f"Uptime: {uptime:.0f}s",
        f"Threads: {len(frames)}",
        "",
    ]
    for name in sorted(frames):
        lines.append(f"  {name}: {' <- '.join(frames[name])}")
    return TUIRenderer.render_panel("Process Doctor", lines, status="stats")


@mcp.tool()
def memory_context_plan(total_tokens: int, message_count: int) -> str:
    """Report the RE:Symbiose budget decision for a session size.

    Pure arithmetic over effective config (env or plan defaults);
    loads no embedding model and never mutates live messages.
    """
    try:
        cfg = context_budget.symbiose_config()
    except ValueError as e:
        return TUIRenderer.render_panel(
            "Context Config Refused", [f"Error: {_error_text(e)}"], status="error"
        )
    over = total_tokens > cfg["trigger_tokens"]
    src = cfg["sources"]
    lines = [
        f"Trigger (Compact Target): {cfg['trigger_tokens']} tokens ({src['trigger_tokens']})",
        f"Target (verbatim tail):   {cfg['target_tokens']} tokens ({src['target_tokens']})",
        f"Max verbatim messages:    {cfg['max_keep_messages']} ({src['max_keep_messages']})",
        f"Max summary chars:        {cfg['max_summary_chars']} ({src['max_summary_chars']})",
        f"Max restore chars:        {cfg['max_restore_chars']} ({src['max_restore_chars']})",
        f"Session tokens:           {total_tokens} across {message_count} messages",
        "Decision: compress in background (Keeper selects, Compressor evicts, Manager retrieves)"
        if over
        else "Decision: keep verbatim (below trigger)",
    ]
    return TUIRenderer.render_panel("RE:Symbiose Plan", lines, status="stats")


def _keeper_status_path(project: str) -> Path:
    """Keeper status file for a project (env override or project-local)."""
    override = os.environ.get("RTR_RE_KEEPER_STATUS", "").strip()
    if override:
        return Path(override).expanduser()
    return mem.resolve_project_dir(project) / ".opencode" / "rtr-re-keeper-status.json"


def rtr_status_payload(project: str = "") -> dict:
    """One truthful health/WIP snapshot: Keeper, Compressor, Manager.

    Missing evidence is reported as absent/stale, never invented: a
    missing keeper status file means the native Keeper has not run in
    that project — it is not proof of anything else.
    """
    payload: dict = {
        "keeper": {"active": False, "detail": "absent"},
        "compressor": {},
        "manager": {},
    }
    if project:
        try:
            status_path = _keeper_status_path(project)
            if status_path.exists():
                try:
                    data = json.loads(status_path.read_text(encoding="utf-8"))
                except Exception as e:
                    data = {"parse_error": str(e)}
                try:
                    age_s = time.time() - status_path.stat().st_mtime
                except OSError:
                    age_s = -1.0
                payload["keeper"] = {
                    "active": True,
                    "detail": "status file present",
                    "path": str(status_path),
                    "age_seconds": round(age_s, 1),
                    "parse_error": data.get("parse_error"),
                    "enabled": data.get("enabled"),
                    "trigger_tokens": data.get("triggerTokens"),
                    "target_tokens": data.get("targetTokens"),
                    "max_keep_messages": data.get("maxKeepMessages"),
                    "last_decision": data.get("decision"),
                    "last_time": data.get("time"),
                    "last_evicted": data.get("evicted"),
                    "last_sink": data.get("sinkPath"),
                    "last_error": data.get("error"),
                    "version": data.get("version"),
                }
            else:
                payload["keeper"] = {
                    "active": False,
                    "detail": "absent: no keeper status file — native Keeper has not run in this project",
                    "path": str(status_path),
                }
        except Exception as e:
            payload["keeper"] = {"active": False, "detail": f"status read failed: {e}"}
    try:
        cfg = context_budget.symbiose_config()
        payload["compressor"] = {
            "trigger_tokens": cfg["trigger_tokens"],
            "target_tokens": cfg["target_tokens"],
            "max_keep_messages": cfg["max_keep_messages"],
            "sources": cfg["sources"],
            "worker": _symbiose_for(project).stats() if project else "no project scope",
        }
    except Exception as e:
        payload["compressor"] = {"error": str(e)}
    try:
        stats = engine.stats()
        payload["manager"] = {
            "total_files": stats.get("total_files"),
            "total_chunks": stats.get("total_chunks"),
            "db_size_mb": round(float(stats.get("db_size_mb", 0.0)), 2),
            "projects": stats.get("projects", {}),
        }
    except Exception as e:
        payload["manager"] = {"error": str(e)}
    return payload


@mcp.tool()
def memory_rtr_status(project: str = "") -> str:
    """RE:Symbiose health viewport: Keeper status, Compressor bounds +
    ticket health, Manager index state. Missing evidence reads absent,
    never invented."""
    payload = rtr_status_payload(project)
    k, c, m = payload["keeper"], payload["compressor"], payload["manager"]
    lines = ["RE:Symbiose live status", ""]
    lines.append(
        f"Keeper: {'ACTIVE' if k.get('active') else 'ABSENT'} — {k.get('detail')}"
    )
    if k.get("active"):
        lines.append(
            f"  bounds trigger={k.get('trigger_tokens')} target={k.get('target_tokens')} "
            f"max_keep={k.get('max_keep_messages')}"
        )
        lines.append(
            f"  last: {k.get('last_decision')} at {k.get('last_time')} "
            f"(evicted {k.get('last_evicted')}, age {k.get('age_seconds')}s)"
        )
        if k.get("last_sink"):
            lines.append(f"  sink: {k['last_sink']}")
        if k.get("last_error"):
            lines.append(f"  error: {k['last_error']}")
    if "error" in c:
        lines.append(f"Compressor: error {c['error']}")
    else:
        lines.append(
            f"Compressor: trigger={c.get('trigger_tokens')} target={c.get('target_tokens')} "
            f"(sources {c.get('sources')})"
        )
        lines.append(f"  worker: {c.get('worker')}")
    if "error" in m:
        lines.append(f"Manager: error {m['error']}")
    else:
        lines.append(
            f"Manager: {m.get('total_files')} files, {m.get('total_chunks')} chunks, "
            f"{m.get('db_size_mb')} MB"
        )
    return TUIRenderer.render_panel("RE:Symbiose Status", lines, status="stats")


_span_indexer = None


_SERVER_STARTED_AT = time.time()


def _ensure_span_indexer():
    """Start the background span indexer once (main entrypoint only).

    Imports never start it, so unit tests stay side-effect free; the
    running server gets automatic span indexing on the holder engine.
    """
    global _span_indexer
    if _span_indexer is None and span_indexer.autoindex_enabled():
        _span_indexer = span_indexer.SpanIndexer(
            engine, lambda: list(mem.PROJECT_ROOTS) + mem._load_extra_roots()
        )
        _span_indexer.start()
    return _span_indexer


def _should_warm_models(env=None) -> bool:
    """Warm ONNX models at server boot unless explicitly disabled.

    The lazy-load spike (cold models materializing mid-request) cost
    first upserts seconds plus a ~900MB RSS jump; a daemon pays it once
    at boot instead. Opt out with OPENCODE_MEMORY_WARM_MODELS=0. Imports
    never warm (tests stay fast); only main() warms.
    """
    src = os.environ if env is None else env
    raw = str(src.get("OPENCODE_MEMORY_WARM_MODELS", "") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


SCHEMA_MARKER_NAME = "rtr-re-schema.json"
MIGRATION_REPORT_NAME = "rtr-re-migration.json"


def _version_tuple(raw: str) -> tuple:
    parts = []
    for chunk in str(raw or "").strip().split("."):
        try:
            parts.append((0, int(chunk)))
        except ValueError:
            parts.append((1, chunk))
    return tuple(parts) if parts else ((0, 0),)


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("rtr-role-type-retrieval")
    except Exception:
        return "0.0.0-dev"


def _should_auto_migrate(env=None) -> bool:
    src = os.environ if env is None else env
    raw = str(src.get("OPENCODE_MEMORY_AUTO_MIGRATE", "") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def maybe_migrate_db(db_dir=None, package_version=None) -> dict:
    """The one update-conformance path (TODO-13): version skew self-amends.

    Compares the package version against the marker beside the DB:
    fresh empty DB writes the marker and skips; a populated DB without a
    marker (every pre-migration database, including RTR-era hybrids) is
    treated as old and amends; older marker amends; same-or-newer skips.
    Never raises into startup.
    """
    import time

    home = Path(db_dir) if db_dir is not None else mem.DB_DIR
    marker = home / SCHEMA_MARKER_NAME
    pkg = package_version or _package_version()
    outcome: dict = {"package": pkg, "action": "skip", "reason": "healthy"}
    try:
        stored = None
        if marker.exists():
            try:
                stored = json.loads(marker.read_text(encoding="utf-8")).get("version")
            except Exception:
                stored = None
        if stored is None:
            try:
                populated = any(col.count() > 0 for col in engine.collections.values())
            except Exception:
                populated = False
            if not populated:
                marker.write_text(
                    json.dumps(
                        {"version": pkg, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
                    )
                    + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                outcome.update({"action": "stamp", "reason": "fresh"})
                return outcome
            stored = "0.0.0-legacy"
        if _version_tuple(stored) >= _version_tuple(pkg):
            return outcome
        rep = engine.repair_registry()
        jan = engine.janitor(dry_run=False)
        report = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "from": stored,
            "to": pkg,
            "recall": "Symbiotising in process — accessing the digital world.",
            "repaired": rep.get("repaired", 0),
            "registry_total": rep.get("total", 0),
            "freed": jan.get("freed", 0),
            "pruned_roots": jan.get("pruned_roots", []),
        }
        (home / MIGRATION_REPORT_NAME).write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        marker.write_text(
            json.dumps({"version": pkg, "ts": report["ts"]}) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        outcome.update(
            {"action": "amend", "reason": f"{stored}->{pkg}", "report": report}
        )
    except Exception as e:  # noqa: BLE001
        outcome.update({"action": "error", "reason": f"{type(e).__name__}: {e}"})
    return outcome


def main():
    """Console-script entrypoint for uvx: run the MCP server over stdio."""
    if _should_warm_models():
        _ = engine.models
    if _should_auto_migrate():
        outcome = maybe_migrate_db()
        print(
            f"[rtr-re-mcp] migration: {outcome['action']} ({outcome['reason']})",
            file=sys.stderr,
        )
    _ensure_span_indexer()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
