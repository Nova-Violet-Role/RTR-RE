# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Generate high-contrast captioned frames for three Tessersect collages."""

from PIL import Image, ImageDraw

W, H = 854, 480

COLLAGES = {
    "frames-a": (
        "POV-A · BINARY VERSUS (544 queries, 5 corpora)",
        [
            (
                "RTR vs RAG — binary Versus",
                [
                    "898 queries · 214 real files",
                    "frozen versus.json (1.2.0)",
                    "SUB: every number re-runnable",
                ],
            ),
            (
                "Scoreboard R@1",
                [
                    "rtr-full 0.723 · rag-hybrid 0.638",
                    "rtr-arctic 0.713 · bge 0.659",
                    "SUB: full leads, published",
                ],
            ),
            (
                "Scoreboard R@3",
                [
                    "rtr-full 0.850 BEST",
                    "rtr-arctic 0.824 · hybrid 0.736",
                    "SUB: full leads depth",
                ],
            ),
            (
                "Scoreboard MRR",
                [
                    "rtr-full 0.777 · arctic 0.760",
                    "rag-hybrid 0.681",
                    "SUB: full leads, honest",
                ],
            ),
            (
                "Per-corpus: nt-studies",
                [
                    "dense arms weak here",
                    "hybrid + fusion win",
                    "SUB: corpus shapes winner",
                ],
            ),
            (
                "Per-corpus: dita-spec",
                [
                    "rtr-full leads outright",
                    "cross-refs need fusion",
                    "SUB: structure rewards RRF",
                ],
            ),
            (
                "Per-corpus: dtd-commands",
                [
                    "arctic collapses R@1 0.160",
                    "bge arms edge R@1",
                    "SUB: weak model drag measured",
                ],
            ),
            (
                "Vote truncation top-10",
                [
                    "tail ranks are noise ballots",
                    "OPENCODE_MEMORY_RRF_VOTE_TOP=10",
                    "SUB: weak arm cannot bury best",
                ],
            ),
            (
                "Standout lane weights",
                [
                    "dense-led 0.45/0.30 defaults",
                    "lone standout may lead",
                    "SUB: mechanism, not tuning",
                ],
            ),
            (
                "STRUCT lane default-off",
                [
                    "rg --json default backend",
                    "ccc for explicit patterns",
                    "SUB: no-harm, within noise",
                ],
            ),
            (
                "Lane-on binary delta",
                [
                    "full R@1 +0.0105 MRR +0.0090",
                    "neutral-to-mild positive",
                    "SUB: archived, not claimed",
                ],
            ),
            (
                "Method: isolation",
                [
                    "fresh DB+registry+lexikon/corpus",
                    "sha256 manifest byte-identical",
                    "SUB: no live-root leakage",
                ],
            ),
            (
                "Precedent superseded",
                [
                    "old 0.679/0.763/0.715",
                    "leak-aided, replaced",
                    "SUB: we publish the freeze",
                ],
            ),
            (
                "Incident log",
                [
                    "Chroma desync fixed",
                    "single shared client per DB",
                    "SUB: bench caught itself lying",
                ],
            ),
            (
                "Janitor + overrides",
                [
                    "orphan chunks janitored",
                    "OPENCODE_MEMORY_DB_DIR",
                    "SUB: isolation is instrument",
                ],
            ),
            (
                "Golden gate 27/27",
                [
                    "isolated rtr_eval PASS",
                    "Engine Beneath 27/27",
                    "SUB: isolation, not convenience",
                ],
            ),
            (
                "Calibration 400k-200k",
                [
                    "submit ~3-6ms complete <=41ms",
                    "synthetic upper bound",
                    "SUB: planning, not model",
                ],
            ),
            (
                "Keeper 400k trigger",
                [
                    "verbatim until 400k (MUGEN)",
                    "50% cut to 200k tail",
                    "SUB: fewer, deeper cycles",
                ],
            ),
            (
                "Protected always kept",
                [
                    "todowrite + last user message",
                    "tool pairs fixpoint",
                    "SUB: core untouchable",
                ],
            ),
            (
                "Sink-first eviction",
                [
                    "DTD-shaped spans to .opencode/memory/",
                    "fail-open on sink error",
                    "SUB: never lose substance",
                ],
            ),
            (
                "Dummy3 filter-key fix",
                [
                    "root ref = no filter",
                    "0.9700 on evicted marker",
                    "SUB: fronted, not smoothed",
                ],
            ),
            (
                "Dummy4 native Keeper",
                [
                    "ACP-ABSENT, sink 110KB",
                    "search hit sink 0.9618",
                    "SUB: host-applied proof",
                ],
            ),
            (
                "Native plugin 9/9",
                [
                    "node --test green",
                    "single-export loader",
                    "SUB: contract miss fixed",
                ],
            ),
            (
                "Wheel ships keeper",
                [
                    "execution/assets keeper.js",
                    "rtr-re-install-opencode",
                    "SUB: pip installs plugin",
                ],
            ),
            (
                "What we refuse",
                [
                    "no universal RAG-eradication",
                    "no always-dual claim",
                    "SUB: scoped verdict only",
                ],
            ),
            (
                "Next: media is evidence",
                [
                    "numbers visible = frozen",
                    "nothing staged for camera",
                    "SUB: reality is judge",
                ],
            ),
        ],
    ),
    "frames-b": (
        "POV-B · GRADED GOLD-v2 (24 queries, 773 judgments)",
        [
            (
                "Gold-v2 frozen supervision",
                [
                    "24 queries · 773 judgments",
                    "histogram 0:633 1:51 2:48 3:41",
                    "SUB: v1 was 155, too sparse",
                ],
            ),
            (
                "Combined nDCG@10",
                [
                    "dense-base 0.8167 BEST",
                    "rtr-full 0.7798",
                    "SUB: dense leads, published",
                ],
            ),
            (
                "ERR@10 + MAP",
                [
                    "dense ERR 0.8369 MAP 0.724",
                    "full ERR 0.7899 MAP 0.658",
                    "SUB: same story, two metrics",
                ],
            ),
            (
                "Worst loss NT-G1C",
                [
                    "dense 0.7346 vs full 0.4192",
                    "delta -0.3154",
                    "SUB: collapse hidden in mean",
                ],
            ),
            (
                "NT-G1C mechanism",
                [
                    "jats buried rank 12 before",
                    "generic terms matched 8 losers",
                    "SUB: burial, not relevance",
                ],
            ),
            (
                "BM25 decisiveness bug",
                [
                    "gap saturated at ~0.90",
                    "flat-field branch dead code",
                    "SUB: max-norm + zeros",
                ],
            ),
            (
                "Fix: standout statistic",
                [
                    "top vs runner-up positives",
                    "hybrid_lane_weights landed",
                    "SUB: 4 red-first tests",
                ],
            ),
            (
                "After fix rank 12 to 4",
                [
                    "dense-unvoted leaders fell",
                    "head now dense-voted",
                    "SUB: mechanism removed",
                ],
            ),
            (
                "NT-G1 loss -0.2446",
                [
                    "tei-modules family",
                    "semantic intent, weak lexicon",
                    "SUB: dense wins prose",
                ],
            ),
            (
                "CMD-G1B loss -0.1977",
                [
                    "command shape intents",
                    "lexical helps here",
                    "SUB: corpus-shaped edge",
                ],
            ),
            (
                "Dita DT-G1 -0.1419",
                ["spec title match", "hybrid close behind", "SUB: within noise band"],
            ),
            (
                "CMD wins for full",
                [
                    "CMD-G3B +0.3422 measured",
                    "fusion helps term-dense",
                    "SUB: not one-sided",
                ],
            ),
            (
                "Lane-on graded neutral",
                [
                    "full 0.7798 to 0.7809",
                    "few code-shaped terms",
                    "SUB: no-harm, default-off",
                ],
            ),
            (
                "Unjudged accounting",
                [
                    "dense-base 6 · full 2",
                    "pool depth 20 blind",
                    "SUB: counted, not hidden",
                ],
            ),
            (
                "Doctor refuses forgery",
                [
                    "forged 0.9999 refused",
                    "dataset label checked",
                    "SUB: generator with teeth",
                ],
            ),
            (
                "Plates regenerate",
                [
                    "plates_graded.py one command",
                    "SVG + Lightpaper tables",
                    "SUB: decoration refused",
                ],
            ),
            (
                "Spread rejected",
                [
                    "dense spread 0.06-0.27",
                    "does not separate cases",
                    "SUB: measured, not tuned",
                ],
            ),
            (
                "No overfit promise",
                [
                    "labels frozen after v2",
                    "engine moves, gold stays",
                    "SUB: benches rerun",
                ],
            ),
            (
                "Scoped verdict",
                [
                    "graded: dense leads",
                    "binary: full R@3 leads",
                    "SUB: both tables printed",
                ],
            ),
            (
                "What full wins",
                [
                    "depth R@3 + MRR parity",
                    "dita-spec outright",
                    "SUB: where fusion earns",
                ],
            ),
            (
                "What dense wins",
                [
                    "generic-vocabulary prose",
                    "census/family corpora",
                    "SUB: semantic match",
                ],
            ),
            (
                "Calibration honesty",
                [
                    "synthetic pipeline only",
                    "ONNX excluded, labeled",
                    "SUB: upper bound only",
                ],
            ),
            (
                "Lean battery green",
                [
                    "full Mathlib, 0 sorry",
                    "axioms recorded per theorem",
                    "SUB: model, not engine",
                ],
            ),
            (
                "Lane.lean contract",
                [
                    "total + disjoint routing",
                    "bounded cap + fallback",
                    "SUB: spec before code",
                ],
            ),
            (
                "STRUCT lane verdict",
                [
                    "prose-blind, scoreless alone",
                    "rg substrate, ccc precision",
                    "SUB: absorbed as lane",
                ],
            ),
            (
                "Publish rule",
                [
                    "no decimal without artifact",
                    "no claim beyond noise",
                    "SUB: pitch perfect",
                ],
            ),
        ],
    ),
    "frames-c": (
        "POV-C · LIVE LOOP (Keeper x Compressor x Manager)",
        [
            (
                "Three offices, zero overlap",
                [
                    "Keeper selects/prunes window",
                    "Compressor evicts+indexes",
                    "SUB: Manager retrieves",
                ],
            ),
            (
                "Keeper is not Compressor",
                [
                    "ACP/native = Keeper only",
                    "Rolling lineage = Compressor",
                    "SUB: do not confound",
                ],
            ),
            (
                "MCP is the viewport",
                [
                    "status/health/WIP window",
                    "Manager + retrieval",
                    "SUB: silent work, loud glass",
                ],
            ),
            (
                "Exchange boundary",
                [
                    "evict between exchanges",
                    "never a /compact pause",
                    "SUB: live turn never blocks",
                ],
            ),
            (
                "Trigger 400k hold 200k",
                [
                    "verbatim until 400k (MUGEN)",
                    "cut 50%, keep 200k",
                    "SUB: big reads survive",
                ],
            ),
            (
                "Max 200 messages cap",
                [
                    "newest-first tail walk",
                    "tokens or count binds",
                    "SUB: whichever hits first",
                ],
            ),
            (
                "Protected tools: todowrite",
                [
                    "never evicted by tail",
                    "last user always kept",
                    "SUB: conversation stays valid",
                ],
            ),
            (
                "Tool pairs fixpoint",
                [
                    "result pulls its call",
                    "batched chains recurse",
                    "SUB: chains stay whole",
                ],
            ),
            (
                "Sink before prune",
                [
                    "write spans, then evict",
                    "fail-open on sink error",
                    "SUB: substance never lost",
                ],
            ),
            (
                "NDATA masked",
                [
                    "base64 sealed [NDATA]",
                    "never embedded, only ref",
                    "SUB: DTD-faithful",
                ],
            ),
            (
                "CDATA exact lane",
                [
                    "code/ids/hashes/paths",
                    "bounded 0.15 bonus",
                    "SUB: opaque terms vote",
                ],
            ),
            (
                "STRUCT lane rg/ccc",
                [
                    "candidate-scoped search",
                    "--json machine events",
                    "SUB: structural precision",
                ],
            ),
            (
                "Compressor planner",
                [
                    "context_budget.py bounds",
                    "env knobs refuse by name",
                    "SUB: mistune fails loud",
                ],
            ),
            (
                "Worker tickets",
                [
                    "submit returns ticket now",
                    "poll ready/failed/cached",
                    "SUB: pause never",
                ],
            ),
            (
                "Bounded retention 512",
                [
                    "oldest completed evicted",
                    "cache rides along",
                    "SUB: no leak in daemon",
                ],
            ),
            (
                "Close fails queued",
                [
                    "pending becomes failed",
                    "never wait forever",
                    "SUB: close semantics named",
                ],
            ),
            (
                "Dummy3 T1 zero-hit",
                [
                    "project=rtrre-dummy3 filtered",
                    "index keyed under project",
                    "SUB: same ref, two meanings",
                ],
            ),
            (
                "Fix: root = no filter",
                [
                    "red-first regression",
                    "search 0.9700 marker",
                    "SUB: coherence contract",
                ],
            ),
            (
                "Dummy3 T3 sink leak",
                [
                    "PROJECTS_DIR hardcoded home",
                    "sink left isolated roots",
                    "SUB: removed, root follows",
                ],
            ),
            (
                "Dummy4 ACP-ABSENT",
                [
                    "no compress/decompress tools",
                    "native keeper only",
                    "SUB: independence proof",
                ],
            ),
            (
                "Dummy4 eviction 110KB",
                [
                    "10 spans host-applied",
                    "sink file on disk",
                    "SUB: note invisible, sink counts",
                ],
            ),
            (
                "Search hits sink 0.9618",
                [
                    "evicted-only phrase found",
                    "index scanned 2 new 1",
                    "SUB: loop closed",
                ],
            ),
            (
                "Standalone C:/RTR-RE",
                [
                    "no ACP/Rolling folders",
                    "154 files manifest sha256",
                    "SUB: ship tree, not lab",
                ],
            ),
            (
                "Wheel + installer",
                [
                    "keeper inside wheel",
                    "clean-venv 25 tools",
                    "SUB: pip installs plugin",
                ],
            ),
            (
                "Live cutover next",
                [
                    "old ACP still running",
                    "swap after proof",
                    "SUB: restart proves posture",
                ],
            ),
            (
                "Pitch perfect rule",
                [
                    "fix or replace, green",
                    "never skip, never smooth",
                    "SUB: errors fronted",
                ],
            ),
        ],
    ),
}

for dirname, (header, slides) in COLLAGES.items():
    for i, (title, bullets) in enumerate(slides):
        img = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W - 1, 58], outline="black", width=4)
        d.text((18, 10), header, fill="black")
        d.text((18, 68), f"{i + 1:02d}/26  {title}", fill="black")
        y = 120
        for b in bullets:
            d.text((40, y), b, fill="black")
            y += 44
        d.rectangle([0, H - 64, W - 1, H - 1], outline="black", width=4)
        d.text(
            (18, H - 52),
            "RE:Symbiose · RTR-RE:Symbiose · Nova-Violet Role",
            fill="black",
        )
        d.text((18, H - 30), f"frame {i + 1:02d} · torch 1-bit · 480p", fill="black")
        img.save(f"C:/RTR-RE/media/{dirname}/frame-{i + 1:02d}.png")
print("frames done")
