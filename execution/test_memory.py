import unittest
from unittest.mock import patch

# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import json
import tempfile
import shutil
import os
import sys
from pathlib import Path

# Add execution directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

# Import memory_engine to allow path interception
import memory_engine
from memory_engine import MemoryEngine
from tui_renderer import TUIRenderer


class TestMemoryRAG(unittest.TestCase):
    def setUp(self):
        # Create a unique temp test directory for each test run to prevent SQLite lock collisions
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_projects = self.test_dir / "projects"
        self.test_db = self.test_dir / "db"
        self.test_registry = self.test_dir / "registry.json"

        # Intercept paths in memory_engine
        memory_engine.PROJECTS_DIR = self.test_projects
        memory_engine.PROJECT_ROOTS = [self.test_projects]
        memory_engine.DB_DIR = self.test_db
        memory_engine.REGISTRY_FILE = self.test_registry
        # Live extra roots would leak real projects into discovery
        # (measured 2026-10-26: 236 files vs expected 3).
        memory_engine.EXTRA_ROOTS_FILE = self.test_dir / "extra_roots.json"

        self.test_projects.mkdir(parents=True, exist_ok=True)
        self.test_db.mkdir(parents=True, exist_ok=True)

        # Setup dummy projects
        self.p1 = self.test_projects / "youtube-shorts"
        self.p1_directives = self.p1 / "directives"
        self.p1_concepts = self.p1_directives / "wiki_concepts"
        self.p1_concepts.mkdir(parents=True, exist_ok=True)

        self.p2 = self.test_projects / "research-slide"
        self.p2_directives = self.p2 / "directives"
        self.p2_directives.mkdir(parents=True, exist_ok=True)

        # Write dummy wiki files
        self.f1 = self.p1_directives / "wiki_inbox.md"
        with open(self.f1, "w", encoding="utf-8") as f:
            f.write(
                "# Youtube Hooks\n\nUse a visual pattern interrupt in the first 3 seconds.\n\n## Buffer API\n\nBuffer GraphQL API uses OIDC tokens."
            )

        self.f2 = self.p1_concepts / "voice_over.md"
        with open(self.f2, "w", encoding="utf-8") as f:
            f.write("# TTS Synthesizer\n\nPiper TTS works best at 22kHz sampling rate.")

        self.f3 = self.p2_directives / "design_wiki.md"
        with open(self.f3, "w", encoding="utf-8") as f:
            f.write(
                "# Layout Rules\n\nUse HSL harmonized grids for premium look.\n\n## Typography\n\nInter or Roboto from Google Fonts."
            )

        self.engine = MemoryEngine()

    def tearDown(self):
        # 1. Close DB connections BEFORE deleting directory (public close:
        # writer lock + Chroma client evicted from the shared cache).
        self.engine.close()
        self.engine._models = {}

        # 2. Delete the unique test directory safely
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_discovery(self):
        discovered = self.engine.discover_wikis()
        paths = [d["path"] for d in discovered]

        self.assertEqual(len(discovered), 3)
        self.assertIn(str(self.f1), paths)
        self.assertIn(str(self.f2), paths)
        self.assertIn(str(self.f3), paths)

        projects = [d["project"] for d in discovered]
        self.assertIn("youtube-shorts", projects)
        self.assertIn("research-slide", projects)

    def test_chunking(self):
        chunks = self.engine.chunk_markdown(
            self.f1, "youtube-shorts/directives/wiki_inbox.md"
        )
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["title"], "Youtube Hooks")
        self.assertEqual(chunks[1]["title"], "Buffer API")

    def test_incremental_indexing(self):
        stats1 = self.engine.index_all()
        self.assertEqual(stats1["new"], 3)

        stats2 = self.engine.index_all()
        self.assertEqual(stats2["unchanged"], 3)

        with open(self.f1, "a", encoding="utf-8") as f:
            f.write("\n## New Section\nSome fresh learning added.")

        stats3 = self.engine.index_all()
        self.assertEqual(stats3["updated"], 1)

    def test_hybrid_search(self):
        self.engine.index_all()

        # Exact match check via hybrid search
        results = self.engine.search("Piper TTS", hybrid=True)
        self.assertGreater(len(results), 0)
        self.assertIn("Piper TTS", results[0]["document"])

        results_dense = self.engine.search("Piper TTS", hybrid=False)
        self.assertGreater(len(results_dense), 0)

    def test_struct_lane_bonus_is_bounded_and_off_by_default(self):
        # Lane.lean contract: bonus <= EXACT_LANE_WEIGHT shared cap, and
        # with the lane off the fused scores are the legacy scores.
        self.engine.index_all()
        query = "voice_over synthesizer"
        base_rows = self.engine._fused_multi([query], k=3, hybrid=False)
        by_source = {r["metadata"]["source"]: r for r in base_rows}
        target_src = [s for s in by_source if "voice_over" in s]
        self.assertTrue(target_src)
        target_src = target_src[0]
        base_score = by_source[target_src]["score"]
        fake = {target_src: [{"term": "voice_over", "line": 1}]}
        with (
            patch.dict(os.environ, {"OPENCODE_MEMORY_STRUCT_LANE": "rg"}),
            patch.object(memory_engine, "structural_hits", return_value=fake),
        ):
            lane_rows = self.engine._fused_multi([query], k=3, hybrid=False)
        lane_by = {r["metadata"]["source"]: r for r in lane_rows}
        lane_target = lane_by[target_src]
        self.assertGreaterEqual(lane_target["score"], base_score)
        self.assertLessEqual(
            lane_target["score"] - base_score,
            memory_engine.EXACT_LANE_WEIGHT + 1e-9,
        )
        self.assertGreaterEqual(lane_target["struct_hits"], 1)
        for src, row in by_source.items():
            if src != target_src:
                self.assertAlmostEqual(lane_by[src]["score"], row["score"], places=6)
        off_rows = self.engine._fused_multi([query], k=3, hybrid=False)
        off_by = {r["metadata"]["source"]: r for r in off_rows}
        self.assertAlmostEqual(off_by[target_src]["score"], base_score, places=6)
        self.assertEqual(off_by[target_src]["struct_hits"], 0)

    def test_project_filter_key_maps_refs_like_index_time(self):
        # Dummy3 T1 measured defect: memory_index accepted the root name
        # as a project ref while search filtered project=<root name> and
        # silently returned zero results for indexed facts.
        self.assertIsNone(memory_engine.project_filter_key("projects"))
        self.assertIsNone(memory_engine.project_filter_key(str(self.test_projects)))
        self.assertEqual(
            memory_engine.project_filter_key(str(self.p1)), "youtube-shorts"
        )
        self.assertEqual(
            memory_engine.project_filter_key("youtube-shorts"), "youtube-shorts"
        )

    def test_same_parent_extra_roots_resolve_exact_project_keys(self):
        # Live Session Start defect (2026-11-04): extra roots sharing
        # one parent were emitted as overlapping parent scopes, so the
        # first sibling (Opencode-memory under C:\) claimed files from
        # every later sibling (RTR-RE). Exact project dirs must win over
        # parent scopes regardless of registration order.
        parent = self.test_dir / "shared-parent"
        sibling_a = parent / "alpha-memory"
        sibling_b = parent / "beta-project"
        sibling_a.mkdir(parents=True)
        sibling_b.mkdir(parents=True)
        extras = json.dumps([str(sibling_a), str(sibling_b)])
        Path(memory_engine.EXTRA_ROOTS_FILE).write_text(extras, encoding="utf-8")

        file_b = sibling_b / "directives" / "sessions" / "note.md"
        self.assertEqual(
            memory_engine.describe_indexed_path(str(file_b))[0], "beta-project"
        )
        self.assertEqual(
            memory_engine.project_filter_key(str(sibling_b)), "beta-project"
        )
        self.assertEqual(
            memory_engine.project_filter_key(str(sibling_a)), "alpha-memory"
        )

    def test_resolve_project_dir_root_name_returns_the_root(self):
        # Dummy3 T3 measured leak: submit(project=<root name>) resolved to
        # PROJECTS_DIR/<name> outside the isolated roots, so the eviction
        # sink landed in the live home tree and was never indexed.
        resolved = memory_engine.resolve_project_dir(self.test_projects.name)
        self.assertEqual(resolved, self.test_projects)

    def test_search_with_root_name_finds_indexed_docs(self):
        self.engine.index_all()
        results = self.engine.search("Piper TTS", project="projects")
        self.assertGreater(len(results), 0)
        self.assertIn("Piper TTS", results[0]["document"])

    def test_close_and_reopen_same_db_serves_search(self):
        # A closed engine must release its Chroma client (evicted from the
        # process-wide cache), and a new engine on the same DB must serve
        # the already-indexed chunks. Pre-fix, close() only released the
        # writer lock, so a client closed by hand stayed cached in
        # _CLIENTS forever and every later engine on that path inherited
        # the dead client (RustBindingsAPI has no attribute 'bindings').
        self.engine.index_all()
        chunks_before = self.engine.stats()["total_chunks"]
        self.assertGreater(chunks_before, 0)

        self.engine.close()
        self.assertNotIn(str(self.test_db), MemoryEngine._CLIENTS)

        reopened = MemoryEngine()
        try:
            self.assertEqual(reopened.stats()["total_chunks"], chunks_before)
            results = reopened.search("Piper TTS")
            self.assertGreater(len(results), 0)
            self.assertIn("Piper TTS", results[0]["document"])
        finally:
            self.engine = reopened

    def test_search_expands_wikilinked_concepts(self):
        # A hit carrying [[wikilinks]] expands to chunks mentioning the
        # linked concept. The expansion query must use the document
        # filter: chromadb>=1.5 rejects $contains under metadata
        # `where` in get() ("got $contains in get"), which live MCP
        # search proved 2026-10-27 while explain (no expansion) worked.
        linker = self.p1_concepts / "linker.md"
        with open(linker, "w", encoding="utf-8") as f:
            f.write(
                "# Zebra Quasar\n\nZebraquasar token links onward to [[Piper TTS]] for speech."
            )
        self.engine.index_all()
        results = self.engine.search("Zebraquasar")
        self.assertGreater(len(results), 0)
        self.assertTrue(
            any("voice_over" in r["metadata"].get("rel_path", "") for r in results),
            f"wikilink expansion did not surface voice_over: {results}",
        )

    def test_search_skips_unused_gate_pass(self):
        calls = []

        def fake_fused(subqueries, k=3, project=None, hybrid=True):
            calls.append(list(subqueries))
            return [
                {
                    "id": "chunk-1",
                    "document": "Piper TTS",
                    "metadata": {"linked_concepts": ""},
                    "score": 1.0,
                }
            ]

        self.engine.build_expansions = lambda query, project=None: ([], [])
        self.engine._fused_multi = fake_fused
        with patch.dict(os.environ, {"OPENCODE_MEMORY_PRF": "0"}):
            results = self.engine.search("Piper TTS")
        self.assertEqual(len(results), 1)
        self.assertEqual(calls, [["Piper TTS"]])

    def test_project_init(self):
        res = self.engine.init_project("new-harness-project", variant="wiki")
        self.assertEqual(res["status"], "success")

        proj_dir = self.test_projects / "new-harness-project"
        self.assertTrue(proj_dir.exists())
        self.assertTrue((proj_dir / "directives" / "wiki_concepts").exists())
        self.assertTrue((proj_dir / "AGENTS.md").exists())
        self.assertTrue((proj_dir / "CLAUDE.md").exists())
        self.assertTrue((proj_dir / "state" / "workflow_state.json").exists())

    def test_consolidation(self):
        # Create duplicates
        dup1 = self.p1_concepts / "voice_over_tips.md"
        with open(dup1, "w", encoding="utf-8") as f:
            f.write(
                "# Voice Over Tips\n\nDetailed guidance about Piper TTS voice output."
            )

        self.engine.index_all()

        # Consolidate
        res = self.engine.consolidate_wiki("youtube-shorts")
        self.assertEqual(res["status"], "success")
        self.assertTrue(len(res["merged"]) >= 1)

        # Verify f2 content got updated
        with open(self.f2, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Voice Over Tips", content)

        # Verify dup1 is deleted
        self.assertFalse(dup1.exists())

    def test_tui_rendering(self):
        panel = TUIRenderer.render_panel(
            "Test Panel", ["Line 1", "Line 2"], status="ok"
        )
        self.assertIn("╔══", panel)
        self.assertIn("Test Panel", panel)
        self.assertIn("🟢 SUCCESS", panel)

    def test_recency_decay(self):
        import time

        now = time.time()
        score_now = self.engine.compute_recency_score(str(now))
        # 14 days ago
        two_weeks_ago = now - (14 * 24 * 3600)
        score_old = self.engine.compute_recency_score(str(two_weeks_ago))

        self.assertAlmostEqual(score_now, 1.0, places=2)
        # Should decay to approximately math.exp(-0.05 * 14) = 0.496
        self.assertLess(score_old, 0.6)
        self.assertGreater(score_old, 0.4)

    def test_importance_scoring(self):
        score_crit = self.engine.compute_importance_score("critical")
        score_high = self.engine.compute_importance_score("high")
        score_low = self.engine.compute_importance_score("low")

        self.assertEqual(score_crit, 1.0)
        self.assertEqual(score_high, 0.7)
        self.assertEqual(score_low, 0.2)

        # Test path mapping
        self.assertEqual(
            self.engine.derive_importance_rating("AGENTS.md", ""), "critical"
        )
        self.assertEqual(
            self.engine.derive_importance_rating("directives/walkthrough.md", ""),
            "high",
        )
        self.assertEqual(
            self.engine.derive_importance_rating(
                "directives/wiki_concepts/voice.md", ""
            ),
            "medium",
        )

    def test_explain_search(self):
        self.engine.index_all()
        results = self.engine.explain_search("Piper TTS")
        self.assertGreater(len(results), 0)
        self.assertIn("rel_path", results[0])
        self.assertIn("final", results[0])
        self.assertIn("dense", results[0])
        self.assertIn("bm25", results[0])

    def test_restore_session_state(self):
        res = self.engine.init_project("test-restore", variant="wiki")
        self.assertEqual(res["status"], "success")

        proj_dir = self.test_projects / "test-restore"

        # Write specific goals and issues
        goals_file = proj_dir / "state" / "current-goals.md"
        with open(goals_file, "w", encoding="utf-8") as f:
            f.write(
                "# Active Goals\n- Implement Piper TTS integration\n- Build webhook pipeline\n"
            )

        issues_file = proj_dir / "state" / "open-issues.md"
        with open(issues_file, "w", encoding="utf-8") as f:
            f.write("# Open Issues\n- Duplicate Stripe webhooks\n")

        self.engine.index_all()

        restored = self.engine.restore_session_state("test-restore")
        self.assertEqual(restored["status"], "success")
        self.assertIn("Stripe webhooks", restored["blockers"][0])
        self.assertIn("Piper TTS integration", restored["active_goals"][0])

    def test_session_reflection(self):
        concept_file = self.p1_concepts / "new_test_concept.md"
        with open(concept_file, "w", encoding="utf-8") as f:
            f.write("# New Test Concept\n\nSome concept body.")

        import json

        with open(self.test_registry, "w") as f:
            json.dump({}, f)

        chat_text = """
        We think BM25 weighting should be higher in our next launch.
        We tested the new BM25 weights on retrieval quality yesterday.
        We verified retrieval improved 18% with the new formula!
        However, the automatic top-3 auto-linking produced noisy graphs.
        We decided to use concept-centric wiki architecture instead.
        The old direct file linking strategy is retired and no longer recommended.
        """

        res = self.engine.reflect_session("youtube-shorts", chat_text)
        self.assertEqual(res["status"], "success")

        events = res["knowledge_events"]
        self.assertTrue(any(ev["type"] == "hypothesis" for ev in events))
        self.assertTrue(any(ev["type"] == "experiment" for ev in events))
        self.assertTrue(any(ev["type"] == "validation" for ev in events))
        self.assertTrue(any(ev["type"] == "failure" for ev in events))
        self.assertTrue(any(ev["type"] == "decision" for ev in events))
        self.assertTrue(any(ev["type"] == "deprecation" for ev in events))

    def test_concept_registry_lifecycle(self):
        self.engine.init_project("materialize-project", variant="wiki")
        proj_dir = self.test_projects / "materialize-project"
        sessions_dir = proj_dir / "directives" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        # 1. First session: Create candidate concept (hypothesis)
        report_file = sessions_dir / "2026-06-01.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("""---
date: 2026-06-01
project: materialize-project
---
# Session Learning Report

## Knowledge Events
```yaml
knowledge_events:
  - type: hypothesis
    concept: hook-formats
    evidence: We think hook formats increase retention.
```
""")

        res = self.engine.materialize_concepts("materialize-project")
        self.assertEqual(res["status"], "success")

        # Candidate concepts should NOT write to disk
        hook_file = proj_dir / "directives" / "wiki_concepts" / "concept_001.md"
        self.assertFalse(hook_file.exists())

        # Verify candidate status in registry
        reg = self.engine._load_concept_registry("materialize-project")
        self.assertEqual(reg["concept_001"]["status"], "candidate")

        # 2. Second session: Emerging concept
        report_file2 = sessions_dir / "2026-06-02.md"
        with open(report_file2, "w", encoding="utf-8") as f:
            f.write("""---
date: 2026-06-02
project: materialize-project
---
# Session Learning Report

## Knowledge Events
```yaml
knowledge_events:
  - type: observation
    concept: hook-formats
    evidence: Observed hook formats again.
```
""")
        self.engine.materialize_concepts("materialize-project")
        reg = self.engine._load_concept_registry("materialize-project")
        self.assertEqual(reg["concept_001"]["status"], "emerging")
        self.assertFalse(hook_file.exists())

        # 3. Third session: Validations and evidence counts make it Validated
        report_file3 = sessions_dir / "2026-06-03.md"
        with open(report_file3, "w", encoding="utf-8") as f:
            f.write("""---
date: 2026-06-03
project: materialize-project
---
# Session Learning Report

## Knowledge Events
```yaml
knowledge_events:
  - type: validation
    concept: hook-formats
    evidence: Success metric 3 validated.
  - type: validation
    concept: hook-formats
    evidence: Confirmed by 5 analytics reports.
```
""")
        self.engine.materialize_concepts("materialize-project")
        reg = self.engine._load_concept_registry("materialize-project")
        self.assertEqual(reg["concept_001"]["status"], "validated")

        # Now validated node must be materialized as markdown node
        self.assertTrue(hook_file.exists())
        hook_text = hook_file.read_text()
        self.assertIn("status: validated", hook_text)

        # 4. Fourth session: Deprecation deletes node
        report_file4 = sessions_dir / "2026-06-04.md"
        with open(report_file4, "w", encoding="utf-8") as f:
            f.write("""---
date: 2026-06-04
project: materialize-project
---
# Session Learning Report

## Knowledge Events
```yaml
knowledge_events:
  - type: deprecation
    concept: hook-formats
    evidence: Old strategy is deprecated.
```
""")
        self.engine.materialize_concepts("materialize-project")
        reg = self.engine._load_concept_registry("materialize-project")
        self.assertEqual(reg["concept_001"]["status"], "deprecated")
        self.assertFalse(hook_file.exists())

    def test_bidirectional_linking_graph(self):
        self.engine.init_project("graph-project", variant="wiki")
        proj_dir = self.test_projects / "graph-project"
        concepts_dir = proj_dir / "directives" / "wiki_concepts"
        concepts_dir.mkdir(parents=True, exist_ok=True)

        # Pre-seed concept registry
        registry = {
            "concept_001": {
                "canonical_name": "concept-a",
                "aliases": ["concept a"],
                "status": "validated",
                "confidence": 3,
                "evidence_count": 3,
                "session_count": 3,
            },
            "concept_002": {
                "canonical_name": "concept-b",
                "aliases": ["concept b"],
                "status": "validated",
                "confidence": 3,
                "evidence_count": 3,
                "session_count": 3,
            },
        }
        self.engine._save_concept_registry("graph-project", registry)

        file_a = concepts_dir / "concept_001.md"
        with open(file_a, "w", encoding="utf-8") as f:
            f.write("""---
concept_id: concept_001
canonical_name: concept-a
status: validated
---
This is concept A which mentions concept-b.""")

        file_b = concepts_dir / "concept_002.md"
        with open(file_b, "w", encoding="utf-8") as f:
            f.write("""---
concept_id: concept_002
canonical_name: concept-b
status: validated
---
This is concept B which discusses general layouts.""")

        res = self.engine.update_concept_graph("graph-project")
        self.assertEqual(res["status"], "success")

        text_b = file_b.read_text()
        self.assertIn("[[concept_001|Concept A]]", text_b)

        text_a = file_a.read_text()
        self.assertIn("[[concept_002|Concept B]]", text_a)


class TestStructLaneRouting(unittest.TestCase):
    """STRUCT lane contract (formal/Symbiose/Lane.lean): total and
    disjoint term routing, backend absence = no lane, rg finds real
    identifiers in candidate files."""

    def test_router_partitions_terms_disjointly(self):
        exact, struct, pattern = memory_engine.classify_query_terms(
            "fix `hybrid_lane_weights` in src/main.py see https://x.test/a"
        )
        self.assertIn("hybrid_lane_weights", struct)
        self.assertTrue(set(exact).isdisjoint(struct))
        self.assertIsNone(pattern)
        self.assertTrue(any("main.py" in t for t in exact))

    def test_router_recognizes_structural_pattern(self):
        exact, struct, pattern = memory_engine.classify_query_terms(
            r"hybrid_lane_weights(\(ARGS*\))"
        )
        self.assertIsNotNone(pattern)
        self.assertTrue(set(exact).isdisjoint(struct))

    def test_backend_absence_returns_no_hits(self):
        with patch.object(memory_engine.shutil, "which", return_value=None):
            hits = memory_engine.structural_hits(
                ["some_identifier"], None, ["whatever.py"], backend="rg"
            )
        self.assertEqual(hits, {})

    def test_off_backend_returns_no_hits(self):
        hits = memory_engine.structural_hits(
            ["some_identifier"], None, ["whatever.py"], backend="off"
        )
        self.assertEqual(hits, {})

    @unittest.skipUnless(memory_engine.shutil.which("rg"), "rg not on PATH")
    def test_rg_backend_finds_identifier_with_line(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "sample.py"
            f.write_text(
                "def hybrid_lane_weights(x):\n    return x\n", encoding="utf-8"
            )
            hits = memory_engine.structural_hits(
                ["hybrid_lane_weights"], None, [str(f)], backend="rg"
            )
        self.assertIn(str(f), hits)
        self.assertEqual(hits[str(f)][0]["term"], "hybrid_lane_weights")
        self.assertEqual(hits[str(f)][0]["line"], 1)


class TestHybridLaneWeights(unittest.TestCase):
    """Lane decisiveness contract for the hybrid mix (measured NT-G1C shape).

    A standout lexical match (top far above the runner-up) may take the
    lead over dense; a generic field where many candidates match the same
    common terms must keep the dense lead. The pre-fix statistic
    (top - median over all candidates, on max-normalized BM25) saturated
    on both shapes, so the flat-field branch never occurred.
    """

    def weights(self, scores):
        return memory_engine.hybrid_lane_weights(scores)

    def test_generic_field_keeps_the_dense_lead(self):
        # NT-G1C measured sparse shape: top 1.0, runner-up 0.8088, most
        # positives weak (~0.099), a few zeros.
        scores = [1.0, 0.8088, 0.7817, 0.7288, 0.6432] + [0.099] * 26 + [0.0] * 5
        w_dense, w_bm25 = self.weights(scores)
        self.assertGreater(w_dense, w_bm25)
        self.assertAlmostEqual(w_dense + w_bm25, 0.75)

    def test_lone_standout_takes_the_lead(self):
        w_dense, w_bm25 = self.weights([1.0, 0.2, 0.2, 0.1] + [0.0] * 20)
        self.assertGreater(w_bm25, w_dense)
        self.assertAlmostEqual(w_dense + w_bm25, 0.75)

    def test_single_match_is_a_standout(self):
        w_dense, w_bm25 = self.weights([0.7] + [0.0] * 35)
        self.assertAlmostEqual(w_bm25, 0.60)
        self.assertAlmostEqual(w_dense, 0.15)

    def test_flat_or_empty_fields_keep_the_defaults(self):
        for scores in ([], [0.0] * 10, [0.5] * 10, [1.0] * 10):
            w_dense, w_bm25 = self.weights(scores)
            self.assertAlmostEqual(w_dense, 0.45)
            self.assertAlmostEqual(w_bm25, 0.30)


class TestRunConsensus(unittest.TestCase):
    """RRF consensus weighting contract (TODO-31).

    A run whose top-3 ranks disagree with the other runs is likely a
    confidently-wrong model (measured: arctic-m on dtd-commands votes
    confidently wrong and drags the fusion below its best member). Agreeing
    runs keep full weight; disagreeing runs are down-weighted toward 0.5.
    """

    def test_single_run_keeps_full_weight(self):
        self.assertEqual(memory_engine._compute_run_consensus([{"a": 1}]), [1.0])

    def test_agreeing_runs_keep_full_weight(self):
        ranks = [{"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 2, "c": 3}]
        out = memory_engine._compute_run_consensus(ranks)
        self.assertEqual(len(out), 2)
        self.assertAlmostEqual(out[0], 1.0)
        self.assertAlmostEqual(out[1], 1.0)

    def test_disagreeing_run_is_downweighted(self):
        ranks = [
            {"a": 1, "b": 2, "c": 3},
            {"a": 1, "b": 2, "c": 3},
            {"x": 1, "y": 2, "z": 3},
        ]
        out = memory_engine._compute_run_consensus(ranks)
        # Run 0/1 top1 'a' is corroborated by peer 0/1 -> full weight.
        # Run 2 top1 'x' appears in no peer's top-10 -> halved.
        self.assertAlmostEqual(out[0], 1.0)
        self.assertAlmostEqual(out[1], 1.0)
        self.assertAlmostEqual(out[2], 0.5)

    def test_differently_right_run_keeps_weight(self):
        # Run 1's top1 'd' is not in run 0's top-3 but is in its top-10.
        ranks = [
            {"a": 1, "b": 2, "c": 3, "d": 7, "e": 8, "f": 9},
            {"d": 1, "e": 2, "f": 3, "a": 7, "b": 8, "c": 9},
        ]
        out = memory_engine._compute_run_consensus(ranks)
        self.assertAlmostEqual(out[0], 1.0)
        self.assertAlmostEqual(out[1], 1.0)


if __name__ == "__main__":
    unittest.main()
