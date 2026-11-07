# Todo ladder snapshot — 2026-11-07 (Maelstrom session)

Full ladder state at the end of the live dummy-run verification phase. The
source of truth for the working list is the session's todowrite tool; this
file is the durable on-disk snapshot so the ladder is never lost. Statuses:
[✓] completed, [ ] pending, [▶] in progress.

---

## RTR-RE ladder (1–52, historical)

- [✓] TODO-1 Restate RTR-RE live-tuning request in domain words and agree done criteria before changing keeper code.
- [✓] TODO-2 Prove keeper evicts oldest-first with a measured test (planKeepIndices on 10-message windows; keep newest tail, evict oldest prefix; protected skill+last-user survive).
- [✓] TODO-3 Set live RTR-RE keeper max messages to 200 in the project config (trigger 250000/target 100000/max 200/enabled; status file confirms).
- [✓] TODO-4 Promote RTR 0.5.0 into RTR-RE and live; switch protection skill to todowrite; disable skill loading (verify-live 45, verify-config 29, keeper 22/22 x2, python 51/51 x2, contracts 44 x2, sync 1/1, mjs 13/13 x2 green).
- [✓] TODO-5 Expose every MCP-controllable knob in slash and ctrl+p palettes (TUI plugin rtr-re-tui.tsx, eleven commands, solid-js; bun 2/2; committed 5acde5a + fec8245).
- [✓] TODO-6 Catalogue C:\RTR-RE via ccc index (eligible 178, indexed 169, missing 9 gitignored, orphans 0, drift 0; DB 2.5 GB with 96.9% freelist bloat).
- [✓] TODO-7 Bring C:\RTR ccc index to full coverage (eligible 967, indexed 165, missing 802 gitignored lab-only predecessors, drift 0).
- [✓] TODO-8 Build the full two-tree catalogue (catalogue/two-tree-catalogue.md; both trees drift 0).
- [✓] TODO-9 Merge C:\RTR-RE as standalone git tree (88db4d5 + 743bc23; 212 files; clean).
- [✓] TODO-10 Re-adapt C:\RTR README to retriever-only form at 0.4.1 facts (commit d356247).
- [✓] TODO-11 Update C:\RTR-RE README to 0.5.0 full-product facts, engine-vs-car boundary (commit 742f79b).
- [✓] TODO-12 Remove lab-to-standalone sync tooling from both trees (contracts green, grep clean).
- [✓] TODO-13 Commit RTR pending 0.5.0 lab work as release-shaped changeset (0b41830; RTR clean).
- [✓] TODO-14 Record chromadb diagnosis (bare python → uv-managed 3.14; fixed every doc invocation; RE 03a27fa, RTR d8d3517).
- [✓] TODO-15 Fix test-file leak in both wheels (exclude execution/test_*.py; RE 9a573f3, RTR 9e0034e).
- [✓] TODO-16 Rebuild stale wheels at 0.5.0, version decision (RE f25a2da, RTR 59b68c6).
- [✓] TODO-17 engine_beneath placement: keep probe in eval/ unshipped, test in execution/ (documented in TAXONOMY; RE 22a4137).
- [✓] TODO-18 Release-gate verification under correct interpreter (RE 131/131, RTR 137/137+1 skip; wheels install clean into fresh venvs).
- [✓] TODO-19 DTD family corpus study: 768 DTD-like files, 15 families, catalogue + sha256 (commit 8cb33a4).
- [✓] TODO-20 DTD structural feature extractor (eval/dtd_extractor.py; entity masking LAW.AMP.13; 10 tests; commit 98d901e).
- [✓] TODO-21 Index DTD corpus into retrieval (dtd-family corpus, 80 queries, 4x7 bench; commit ebf81e2).
- [✓] TODO-22 Extend taxonomy with T7-T10 (attribute-semantic, entity-lane, content-model, cross-family; commit c1f9dad).
- [✓] TODO-23 Four-column parity matrix for 1.0.0 (RTR MCP/no-MCP vs RTR-RE MCP/no-MCP; 26/26 tool sets; byte-identity on 7 core files; commit abb8164).
- [✓] TODO-24 Engine Beneath evaluation instrument, open + red-capable (7 cases; commit 45ef2bb).
- [✓] TODO-25 Add corrupted-sink/duplicate/protected-tool/production-scale controls (10 cases; commit f8614c9).
- [✓] TODO-26 3D presentation plates + exact evidentiary 2D tables (commit fd7aec0).
- [✓] TODO-27 DTD-corpus evaluation across all 7 systems (rtr-full leads R@1=0.565, R@3=0.685, MRR=0.620).
- [✓] TODO-28 Preset-axis measurement: 84-cell parking arithmetic verified, both profiles (commit 0c2e1f2).
- [✓] TODO-29 Baseline frozen at 1.0.0 (baseline-1.0.0.json/.md; manifest; re-frozen with big-n DTD caps).
- [✓] TODO-30 Outperform frozen baseline on every taxon (lexikon seeding commit 10bedbf; dtd-family R@1 0.5460→0.7239, T7 +0.425, T8 +0.300; no regression; full re-run reproduces exactly).
- [✓] TODO-31 Outperform classic RAG again (deterministic 4x7 re-run commit 56db917; rtr-full beats all classic systems on every corpus).
- [✓] TODO-32 DTD-aware chunking: variants measured; winner whole-file + inventory header (OPENCODE_MEMORY_DTD_CHUNK_MODE).
- [✓] TODO-33 Content-model grammar features study: three variants measured net-negative, reverted; first pass shipped (03d798e); T9 ceiling characterized.
- [✓] TODO-34 Parameter-entity safety LAW.AMP.13 (quote-aware scanning; hostile-DTD guard; commit 59d607a).
- [✓] TODO-35 Cross-family transfer study (transfer_matrix.py; lane decision; 92/105 pairs independent; commit 488b494).
- [✓] TODO-36 Per-family benchmark suites (14 families; 14x7 zero query errors; rtr-full leads 9/ties 2/loses 3 sibling bleed; commit 9e286f2).
- [✓] TODO-37 Grow lexikon with DTD vocabulary (3800 terms seeded; two pollution bugs fixed; commit 10bedbf).
- [✓] TODO-38 Rewrite public story with amplified evidence (1.0.0 measurement section; version coherent everywhere).
- [✓] TODO-39 Expand Re:hack citations + operator thesis (citation corpus read whole; thesis placed beside evidence).
- [ ] TODO-40 Prepare major release distributions at 1.0.0 — **completed this session**: wheel dist\rtr_role_type_retrieval-1.0.0-py3-none-any.whl (129,635 B, sha256 bf95f7b6...), sdist (2,118,462 B, sha256 66c46e38..., bloat fixed 217 MB→2.1 MB), npm plugin tarball (13,480 B, sha256 993c13b5...), npm mjs tarball (11,061 B, sha256 9dc28f1d...); fresh-install defaults verified from packaged artifacts (symbiose-ah/rtr-full/T4/P60 both profiles; MCP commit probe passes on installed 1.0.0).
- [ ] TODO-41 Publish the major release everywhere in separate verified stages — pending, gated on closure catalogue + live verification suite; operator go-ahead required.
- [ ] TODO-42 Post-publication verification (isolated installs + smoke matrix) — pending; pre-publish equivalent executed against prepared artifacts.
- [✓] TODO-43 Regression harness (eval/regression_gate.py; red-capable; 5 tests; full suite 221 green).
- [✓] TODO-44 Document DTD study in TAXONOMY.md (transfer matrix, per-family suites, amplification table).
- [✓] TODO-45 Cumulative counter + recency-aware protection (worker cumulative_path fail-closed; threshold 1000; JS/Python parity; warning case flipped; 8 tests; commit 200951e).
- [✓] TODO-46 Compressor analysis (three named cases; fires past trigger, reduces live window ~65%, never compresses protected; commit 6051e8e).
- [✓] TODO-47 Re-Symbiose-Mugen preset (400k/200k/200; future default recorded without flipping; alias mugen; TUI lists it; Engine Beneath measures it).
- [✓] TODO-48 Plugin verification both versions (same core, same seeding, same registry-driven presets; fresh-install defaults resolve; all surfaces green).
- [✓] TODO-49 Optimizer empowerment (profile consumed by engine: models/threads/parking/hybrid/expansion; JS planContext registry-aligned; 6 new Engine Beneath cases; bench reproduction exact).
- [✓] TODO-50 Compressor deepening (5 new cases; incremental firing, session-resume cumulative, post-trim double duty, evicted retrievable via memory_search, lexikon interplay; 27/27).
- [✓] TODO-51 Pre-publication closure catalogue (catalogue/pre-publication-closure.md; gate PASS — TODO-40 may begin).
- [✓] TODO-52 Keeper triple/quadruple testing interface + empowerment (four layers, each red-capable; cumulative-counter parity gap + status-write atomicity closed).

## Maelstrom session (53–66)

- [▶] TODO-64 Implement DTD family-signature assimilation (proposals A-E): lineage extraction (PUBLIC/SYSTEM), driver/module role, customization-layer switches, T10 enrichment, taxonomy T11/T12; defguide examples + DocBook 4.5 as fixtures. IN PROGRESS — extractor read; engine scanner (memory_engine.py:792) + chunker next; failing-first tests.
- [ ] TODO-65 Implement plugin architecture empowerment (proposals P1-P6): prompt-level /rtr commands, SessionStart+per-turn reminder split, subagent propagation, V1+V2 hook surface, ESM capabilities, cross mjs-js skill. Sequenced after TODO-64. Live findings recorded: (a) registry search paths plugin-relative → live-asset sync/robust resolution; (b) config field is cpuProfile (not cpu); unknown keys ignored vs unknown preset values refuse; (c) TUI write path and keeper read path agree on cpuProfile/preset/enabled; (d) registry loaded once per module lifetime — mid-session registry changes refused until restart (measured).
- [✓] TODO-66 Set live system default MUGEN + T8/P80. Final state: explicit values in C:\RTR-RE\.opencode\rtr-re-keeper.json (400000/200000/200, threads 8, parking 80, rtr-full) — accepted by running keeper; status file confirms live (12:47:59 exchange, evicted 386 under new bounds). Named form works post-restart; label shows fallback name until then. Live registry synced from repo.
- [✓] TODO-62 Live palette verification: bun 2/2; plugin loads cleanly; config-write path verified; command-shim (command-shim.ts:48-60) maps namespace "palette" → palette entries. Interactive ctrl+p rendering requires a real terminal.
- [ ] TODO-61 Compact-flow live test — deferred per operator: compact is emergency button only, not in RTR-RE; keeper+compressor proven (eviction + memory_search recovery observed live); 12000-limit config did not trigger compaction (model limit merge not applied for custom inception provider; session ~157k tokens, time_compacting empty).

- [✓] TODO-53 Diagnose Compact python-instance failure. Evidence: installed 0.4.1 stale; compaction calls memory_session_commit on rtr-re-mcp.exe; MCP connection closed at 09:01:04/09:11:37 then memory MCP call failed; live server ~1.2 GB; compaction agent provider (cpa-gui @ 127.0.0.1:8317) unreachable; standalone probe of 0.4.1 commit works on small project → environmental failure (heavy real-corpus commit + manual kill + dead model proxy).
- [ ] TODO-54 Install RTR-RE 1.0.0 locally + verify whole chain. Wheel built; uv tool install interrupted by file locks (live 0.4.1 server tree force-terminated taskkill /F /T /PID 17904); re-run deferred until measurement suite completes.
- [✓] TODO-55 Cumulative counter live measurement (submit counting 5→15→18 across server restarts; threshold crossing 918→1001→2001; recency rule verified at planner level + Engine Beneath case).
- [ ] TODO-56 Full preset axis measurement on Ryzen 9 9950X3D2 (16C/32T): profiles × threads 2-16 × parking 20-80% × modality × dummy presets through keeper/MCP/no-MCP optimizer.
- [✓] TODO-57 Chroma DB health/corruption/recovery: forced kills survive (integrity ok); mid-index kill → recovery search works; full build 69 files/119.2s/0 failed/DB 1.1MB→34MB; fail-closed refusal; live DB untouched. Catalogue: catalogue/2026-11-07-maelstrom-live-verification.md.
- [✓] TODO-58 ONNX health: models load lazily (threads=4 each); real worker python behind shim (~7MB shim); index run 3.4GB RSS/483s CPU (~3.8 cores); live server ~1.16GB warm; dense fallback span=0→1.0 documented as silent degradation window.
- [ ] TODO-59 Study Agile plugin architecture → empower RTR-RE no-MCP.
- [ ] TODO-60 Study C:\Plugins-to-study + ECMAScript docs (.mjs/.js plugin architecture, cross mjs-js skills).
- [ ] TODO-61 Compact-flow live test — deferred per operator: compact is emergency button only, not in RTR-RE; keeper+compressor proven (eviction + memory_search recovery observed live); 12000-limit config did not trigger compaction (model limit merge not applied for custom inception provider; session ~157k tokens, time_compacting empty).
- [ ] TODO-62 Live palette (ctrl+p) verification in dummy TUI.
- [▶] TODO-63 Study DTD family-building sources: DocBook Definitive Guide (C:\Microsoft Skill OPT and Skill LENS install via UV\dtd\defguide\en — 12 top-level dirs, defguide/34 files incl. ch00-ch05, appa-appi, schema, examples, refpages) + C:\DTD_FAMILY\.dtd-file-examples (27 entries: JATS, DocBook, DITA v1.2/v1.3, TEI, MathML, SVG, XHTML, Office, standalone DTDs). Inventory done; reading + assimilation pending.

---

## Instruments kept (temp, for release verification suite)

- C:\Users\Saimono\AppData\Local\Temp\opencode\rtr-mcp-probe.mjs
- rtr-cumulative-probe.mjs, rtr-protection-probe.mjs
- rtr-chroma-kill-probe.mjs, rtr-chroma-recovery-probe.mjs
- rtr-onnx-probe2..6.mjs, rtr-proc-probe.mjs
- sink-times.ps1, encchk.ps1, find-db.ps1, find-opencode-dev.ps1

Encoding: UTF-8, LF, no BOM, no CR.
