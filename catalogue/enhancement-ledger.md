# RTR-RE enhancement ledger + overhaul roadmap (TODO-22)

Ranked 2026-11-09 from the TODO-14–19 first-pass logs plus the rerun logs.
Bands: gain-beside (add alongside, nothing removed), implied-made-real
(habit into declaration), approach-replaced (old way removed, overhaul).

Line rule: entries marked RERUN carry file:line measured this session.
Entries marked FIRST-PASS name file + area only — the first-pass line
numbers refer to older revisions (engine 4024, server 1054, keeper 1199)
and are not re-cited here; re-pin on implementation. A line number that
cannot be re-derived is not quoted.

## Keep for the 1.1.x line (ranked)

### Do first (correctness, evidenced, low risk)

1. E-T18-3 config write races — implied-made-real — FIRST-PASS.
   Evidence: keeper/TUI share one watched config file; concurrent
   read-modify-write can lose a knob. Files: opencode-plugin/rtr-re-keeper.js
   (writeFileConfig) + opencode-plugin/rtr-re-tui.tsx (writeKeeperConfig).
2. E-T18-2 atomic writes for spans/config/brief — implied-made-real —
   FIRST-PASS, partly re-verified in rerun. Status file IS atomic since
   (keeper writeStatusFile temp+rename); spans (.dtd), keeper config and
   subagent brief still write directly. Files: opencode-plugin/rtr-re-keeper.js
   writeSink/writeFileConfig, mjs/framework/rtr-keeper-framework.mjs
   writeSubagentBrief.
3. E-T15-2 submit/poll exception-shape consistency — implied-made-real —
   FIRST-PASS. Evidence: submitters branch on ticket shapes; inconsistent
   error shapes force defensive parsing. Files: execution/memory_mcp_server.py,
   execution/memory_cli.py (symbiose verbs).
4. R2 overflow-submit cumulative drift — implied-made-real — RERUN (RRD-98).
   submit() increments cumulative_messages before the queue put, so
   queue-rejected work inflates the protection counter.
   File: execution/symbiose_worker.py:345-364 vs :378-380 (803-line rev).
5. E-T16-1 per-model effective threads order-dependence —
   implied-made-real — FIRST-PASS. Evidence: first value wins by call
   order instead of by declaration. File: execution/context_budget.py
   (profile builder).
6. E-T16-5 wait() ignores injected clock — implied-made-real —
   FIRST-PASS. Evidence: untestable timing path. File:
   execution/symbiose_worker.py wait().
7. E-T14-3 seeded terms mis-stamped source="hand" — implied-made-real —
   FIRST-PASS. Evidence: provenance lie in the lexikon seed path.
   File: execution/memory_engine.py (seed_dtd_lexikon).
8. E-T14-1 portable commit-charge guard — implied-made-real —
   FIRST-PASS. Evidence: refusals never fire on Linux CI (Windows-only
   probe). File: execution/memory_engine.py (commit-charge guard).

### Do soon (perf, robustness)

9. R1 write_wiki runs index_all twice per write — implied-made-real —
   RERUN. Correct but expensive: full index before link search and
   again after. File: execution/memory_engine.py write_wiki
   (4157-line rev).
10. E-T14-4 path-scoped indexing — implied-made-real — FIRST-PASS.
    Evidence: index_all always walks every root; no subtree scope.
    File: execution/memory_engine.py index_all.
11. E-T14-6 walk pruning in-place — implied-made-real — FIRST-PASS.
    Evidence: discovery walks more than it indexes. File:
    execution/memory_engine.py (discovery).
12. P3 brief unwired (integrate or remove) — implied-made-real —
    FIRST-PASS. Evidence: subagent brief is written but no consumer
    reads it. Files: mjs/framework/rtr-keeper-framework.mjs,
    mjs/framework/rtr-subagent-framework.mjs. Implementation must
    first decide integrate vs remove.
13. E-T15-1 unify server/CLI panel builders — gain-beside —
    FIRST-PASS. Evidence: near-verbatim duplication across surfaces.
    Files: execution/memory_mcp_server.py, execution/memory_cli.py.
14. E-T14-9 consolidate dry-run — gain-beside — FIRST-PASS. Evidence:
    consolidate has no preview mode. File: execution/memory_engine.py
    consolidate_wiki.
15. Installer uv-pip fallback for --wheel — gain-beside — FIRST-PASS.
    File: installer/launchers/python_launcher.py execute_plan.
16. Registry-validated installer names — gain-beside — FIRST-PASS.
    Evidence: preset/modality names free-typed, validated late.
    Files: installer/launchers/*.py|*.mjs.
17. E-T14-7 Windows bootstrap template — gain-beside — FIRST-PASS.
    File: execution/memory_engine.py init_project.

### Small + safe (anytime)

18. R4 egg citation hash-pin — gain-beside (test-only) — RERUN.
    No automated pin exists today (grep-verified across installer
    tests; the first-pass log's pin claim is stale). Pin the three
    copies by hash so the test never quotes spoiler text. Files:
    installer/launchers/python_launcher.py,
    installer/launchers/node_launcher.mjs,
    installer/shell/js/presets.js.
19. R3 node readScene drops camera pitch — gain-beside — RERUN.
    Harmless (pitch unused downstream in both launchers) but a
    gratuitous divergence. File:
    installer/launchers/node_launcher.mjs readScene (541-line rev).

### Hygiene (below bands; do with adjacent work)

- E-T16-2 shed_chars clamp metric (dead code) — FIRST-PASS.
- E-T16-3 render_table dead (deprecate/remove) — FIRST-PASS.
- R6 pre-existing LSP str=None annotations — RERUN.
  File: execution/memory_cli.py:18/249 (879-line rev).

## Parked (not for 1.1.x, with reasons)

- E-T18-1 thinking offload (HEADLINE overhaul) — approach-replaced.
  Sink + strip reasoning from the kept tail; replaces message-granular
  eviction for thinking content. Parked: architectural, needs design;
  the 1.1.1 line is repair-only. This is the durable fix for
  thinking-heavy windows (keepTokens over target while message count
  binds first).
- E-T19 demo server half — approach-replaced. Parked: conditional —
  only if the browser shell ever graduates from demo (RRD-54b says
  demo today).
- Full cross-host optimizer — approach-replaced. Parked: product
  decision first (RRD-47a scope).
- E-T16-4 unlocked counter/closed reads — parked: benign by evidence;
  adding locks risks more than it buys.
- E-T14-5 concept-id max+1 (latent) — parked pending design: latent,
  unpinned, cannot be ranked precisely.
- H4/H7/H10/H11 (TODO-16, marked ledgered) — parked title-only
  (RRD-102): detail lost with the study spans; re-derive from code
  if pursued.

## Routed elsewhere (not ledger)

- E-T14-2 graded loader strictness → TODO-25 (eval power).
- J10/J11 → TODO-23; J15/J17/J22/J29 → TODO-24; J1/J3/J4/J8/J16/J23 →
  TODO-25; J27/J28 → TODO-26; extractor mirror-hazard → TODO-30.
- R5 docs drift (CLI 16→19 verbs, tools 27→29) → TODO-33.
- N4 WMP handoff assumption → stays noted, unverifiable by
  construction (first-pass verdict stands).
- Audio clearance flag → TODO-35 (blocks publish, not repair).

## Ranked done-work (shipped, by impact)

1. Cycle-2 counter-move (RRD-104-120) — approach hardened
   toward approach-replaced (incremental eviction). 17 RRDs,
   ~30 tests, reinstall plus live proof (992k to 136k served,
   debt 0, phantom gone). Highest: live cost plus correctness.
2. TODO-14 retrieval core — implied-made-real. 16 fixes
   (index holes F12, lexikon, RRF, lanes) plus gate-found-RED.
   Highest: silent-corruption class.
3. TODO-18 keeper/JS — implied-made-real. 13 fixes plus thinking
   probe (COUNTED) plus gate. Highest: live window truth.
4. TODO-15 MCP/CLI — implied-made-real. 13 fixes plus G14
   (lock-region race, traversal, refusal crashes). High:
   surface safety.
5. TODO-16 compressor/worker — implied-made-real. 6 fixes plus
   thinking probe (reasoning counted, think lane). High:
   thinking counted.
6. TODO-19 installer/egg — gain-beside plus implied. 14 fixes
   plus reopen (50/50 wired, coda, backlog) plus hardcore
   payload. Medium-high: install reliability plus egg coherence.
7. TODO-17 eval study — study (no band). 24 findings routed;
   J10/J11 landed via TODO-23. Foundational: methodology plus
   routes (rest land via TODO-24/25/26/30).

## Overhaul roadmap (post-1.1.1)

Near-term (1.1.x Keep queue, tier order): do-first (1-8 plus
E-T14-9 new) → do-soon (9-17 plus E-T14-5/E-T16-5 new-tier) →
small+safe (18-19) → hygiene (with adjacent work). E-T38C rides
the first trigger (relay miss/backlog), not the queue.
Overhaul phases (gated): P0 design docs (E-T18-1 strip protocol
plus adversarial review; E-T38B calibration plan) → P1 E-T18-1
implement (correctness before accuracy) → P2 E-T38B implement.
Gated (not sequenced): E-T19 demo half (on shell graduation),
optimizer (on product decision). Never (parked indefinite):
E-T16-4 (benign), H-pack (detail absent).

## Redo evidence (2026-11-09) — per-entry tree verification

E-T18-3 config write races — VERIFIED, still present. Keeper
writeFileConfig (opencode-plugin/rtr-re-keeper.js:1013-1024) reads
(L1016), merges (L1020), validates via probe (L1021, throws before
write — good ordering, no clamp divergence), writes directly
(L1024): no lock, no atomic rename, no mtime guard. TUI
writeKeeperConfig (opencode-plugin/rtr-re-tui.tsx:82-95) is the same
read-merge-write shape. Two /rtr verbs, two palette clicks, or two
clients on one project interleave at the awaits → silent lost knob
update. Fix risk LOW (single-writer queue or lock + atomic write;
pattern already in-repo at writeStatusFile). Band implied-made-real
(the mtime-reload design already assumes coherent files). Verdict:
KEEP, do-first. Pairs with E-T18-2 (same files, one hardening pass).

E-T18-2 atomic writes — VERIFIED, partly done. Direct writes remain:
spans .dtd (rtr-re-keeper.js:722,725), sidecar JSON (:728),
keeper config (:1024), subagent brief
(mjs/framework/rtr-keeper-framework.mjs:141-144, writeFileSync).
Status file already tmp+rename (:759). Nuance: corrupt sidecars
are CONTAINED (worker quarantines unparseable sidecars), but
truncated spans/config/brief are not. Fix risk LOW (extend the
proven tmp+rename pattern). Band implied-made-real. Verdict:
KEEP, do-first, same pass as E-T18-3.

E-T18-1 thinking offload — VERIFIED, still present, HEADLINE.
Keeper applyKeeper (opencode-plugin/rtr-re-keeper.js:689) keeps
whole messages — `messages.filter((_, i) => plan.keep.has(i))`,
parts untouched; the only kept-side mutation is the appended
eviction note. Worker plan() (execution/context_budget.py) likewise
evicts whole spans. No strip-thinking-from-kept path exists on
either side (whole-file reads this session). Harm is measured, not
theorized: thinking-heavy windows bind maxKeep first (live:
keepTokens 419204 vs 200000 target) and message granularity cannot
recover. Fix shape: sink reasoning parts to spans, strip them from
kept messages, mark every strip, keep the offload retrievable via
memory_search. Fix risk HIGH: mutates model-visible content —
deliberation loss mid-task if the strip misfires; markers must be
unambiguous; needs a design doc + adversarial review before code.
Band approach-replaced (replaces keep-verbatim-tail for thinking
content). Verdict: PARK as the overhaul headline. Reason:
architectural with blast radius; the 1.1.1 line is repair-only.

E-T38B density-aware estimator — PARKED per RRD-119 (follow-up to
cycle 2, not part of it). Problem: the keeper estimates chars/4
while real tokenizers run ~1.45x hotter on dense sessions
(measured: 543k live vs 373k kept-estimate), so trigger-400k
fires at ~580k-real. Fix shape: keep /4 for prose, add a cheap
dense-content rate (code/JSON/tool-call markers) calibrated
OFFLINE against a real tokenizer in tests (gpt-tokenizer fixtures:
prose/code/JSON/tool-call), no host API at runtime. Both surfaces
(keeper.js estimateTokens + budget.py estimate_tokens, parity).
Why parked: overflow contained without it (worst-case served
~250k-est ~= 360k-real, safe); cost significant; reinstall-first
per operator order. Promotes if live data shows density blindness
causing bad decisions.

E-T38C relay-verify rework — GAP (measured live 2026-11-10):
drain relayed 0/115 sidecars (sidecar-to-spans count-match
assumption false; windows drift). Fix per RRD-125:
normalize-then-compare (recompute spans digest over
sink-normalized message texts, compare to sidecar digest) with
ticket fallback preserved; failing-first (drifted-count fixture
RED). Band gain-beside (drain-internal). Verdict: CARRIED per
RRD-126 (implement at 22-sweep or on trigger: relay miss or new
backlog). Note: ticket fallback cleared 115/115 safely; 115
dup-sinks cleaned pre-index (spans restored 570). 39-refine (2026-11-10): fresh-pair autopsy (1cb8575a): loose count 202 vs strict 195 (7 content lines match the loose tag); collision, not drift. Fix: strict-pattern count minimum, digest-set compare preferred; ticket fallback stays.

E-T15-1 unify server/CLI panel builders — VERIFIED, diverging.
Server memory_search (memory_mcp_server.py:93, render_panel
:98/:103/:120) and CLI format_search (memory_cli.py:18-51) build
near-verbatim panels (same titles, statuses, line formats, shared
TUIRenderer): duplication real. Divergence already present: server
prints a Title: line the CLI lacks; failure text differs ("Error:"
vs "Error during search:"). No format_* exists server-side (tools
call TUIRenderer inline); CLI owns 19 format_*. Fix shape: extract
shared line-builders both import (delivery differs: CLI exits,
server returns; content unifies); panels byte-comparable in tests.
Fix risk LOW (pure extraction). Band gain-beside. Verdict: KEEP,
do-soon (#13 holds).

E-T15-2 submit/poll exception-shape consistency — VERIFIED, two
live divergences. (a) Same cause, different labels: corrupt
cumulative counter raises ValueError; server submit
(memory_mcp_server.py:909, single ValueError catch) reports it as
"Symbiose Submit Refused" while CLI submit wraps worker-build
separately (memory_cli.py:539, worker Exception) as "Symbiose
Submit Failure". (b) CLI drain (memory_cli.py:578) has no catch
around the drain call (traceback on failure) while the server
drain tool and every CLI sibling (G14 convention) render failure
panels with exit 1. Poll/drain granular catches server-side hold;
CLI's sync submit versus server async tickets is by design (verb
topology, out of scope). Fix shape: server submit wraps
_symbiose_for (Failure) separately from submit_json ValueError
(Refused); CLI drain gains the sibling Failure catch; optional
shared refused()/failure() builders ride E-T15-1's
unification (pair both entries, one panel-consistency pass). Fix
risk LOW. Band implied-made-real. Verdict: KEEP, do-first (#3 holds).

E-T14-1 portable commit-charge guard — VERIFIED, Windows-only.
_commit_charge_bytes (memory_engine.py:211) reads
GlobalMemoryStatusEx via ctypes.windll (AttributeError off-Windows
-> None); _full_reindex_refusal (:240) returns None when unknown,
so Linux never refuses (fail-open = unprotected). OOM-crash guard
absent on Linux CI. Fix shape: stdlib portable probe (/proc
meminfo+swap, fallback None) with identical refusal semantics;
no new dependency. Fix risk LOW-MED (per-OS probe validation;
misread degrades to status quo, never worse). Band
implied-made-real. Verdict: KEEP, do-first (#8 holds).

E-T14-3 seeded terms mis-stamped source="hand" — VERIFIED, stored
lie with shadowing. seed_dtd_lexikon
(memory_engine.py:3367-3467) stores seeds via add_lexikon_term
(:3466), which hardcodes "source": "hand" (:3358, no source
parameter): machine guesses persisted as hand-curated. Merge
(:3526) then protects them from registry-derived updates (stale
shadows fresh); export (:3580) defaults sourceless to "hand",
propagating the claim. Fix shape: optional source param on
add_lexikon_term (default "hand", hand-path unchanged), seed
passes "seed", precedence hand > registry > seed, export default
"derived". Fix risk LOW (lexikon content; seeded terms yield to
registry as intended). Band implied-made-real. Verdict: KEEP,
do-first (#7 holds).

E-T14-4 path-scoped indexing — VERIFIED, stronger than filed.
index_all (memory_engine.py:1721) takes projects but uses it
only to register out-of-roots for discovery, then indexes ALL
discovered (no project filter, no subtree scope). Fix shape:
optional scope filter threading into discover_wikis; DESIGN TRAP:
purge uses active_paths over full discovery — a naive filter
makes out-of-scope files look deleted; scope purge consistently
or disable purge when scoped (with warning). Fix risk LOW-MED
(purge interaction). Band implied-made-real (projects param
implies scoping). Verdict: KEEP, do-soon (#10 holds).

E-T14-6 walk pruning in-place — VERIFIED. discover_wikis
(memory_engine.py:1379) descends into noise dirs (os.walk
:1395) and skips at file level (:1406 parts-check) instead of
pruning dirs in place: walks more than it indexes (second site:
directives scan :3046, same shape). Subtree
scoping (fixed_key walk_root) and deterministic sorts hold.
Fix shape: dirs[:] in-place prune on _NOISE_DIRS names at both
sites (equivalent file set, sorts retained, order stable). Fix risk
LOW (pure perf, behavior-identical). Band implied-made-real.
Verdict: KEEP, do-soon (#11 holds).

E-T14-9 consolidate dry-run — VERIFIED, UPGRADED to do-first
(#9 new). Merge execution (memory_engine.py:2700-2749) is
destructive: winner overwritten, loser unlinked (:2737), on an
aggressive filename word-subset heuristic (common words >= min
length: "concept_one" swallows "concept_one_v2"). No preview, no
backup, no undo; then a force full reindex (:2749, same
sledgehammer smell as R1). Fix shape: dry_run flag returning
would-merge pairs with reasons, no writes; heuristic threshold
tuning needs false-positive measurement first (follow-up, not
bundled). Fix risk LOW (additive). Band implied-made-real
(destructive ops preview as declared habit). Verdict: KEEP,
do-first (do-first new; first-pass numbers frozen).

E-T14-7 Windows bootstrap template — VERIFIED. init_project
(memory_engine.py:2757) writes dirs, docs (AGENTS/CLAUDE/inbox/
progress/handoff all created, referenced files present), state
JSONs, and a POSIX-only init.sh (:2860-2870: bash, source,
python3, pip): no Windows bootstrap script on a Windows-first
box. Stale product name in template (:2818, absent from
README/pyproject): rename token to RTR-RE. Fix shape:
add init.cmd minimal mirror alongside (zero-dep, runs everywhere);
.ps1 as follow-up note. Fix risk LOW (new file, behavior
unchanged). Band gain-beside. Verdict: KEEP, do-soon (#17 holds).

E-T14-5 concept-id allocation — VERIFIED, worse than filed,
PROMOTED to do-soon (new). Allocator _resolve_concept
(memory_engine.py:3632) uses len(registry)+1 (step 3), not
max+1: any id gap (deletion) collides and overwrites a live
concept. Load-compute-save unlocked (multi-process callers:
MCP plus CLI shells) → same-id race. Secondary: step-2 fuzzy
match mutates (appends alias plus saves on a resolve path);
aggressive word-subset like consolidate — needs a
false-positive case before ranking. No deletion path exists
today (gaps ungappable) and races need concurrency: latent in
practice, now pinned (first-pass "unpinned" retired). Fix
shape: max+1 (gap-safe) plus cross-process file lock (G13
pattern); resolver mutation split read-vs-add. Fix risk MED
(locking). Band implied-made-real (ids declared unique).
Verdict: KEEP, do-soon (new; first-pass numbers frozen).

E-T16-4 unlocked counter/closed reads — PARK CONFIRMED, benign
verified. submit checks _closed under lock
(symbiose_worker.py:307 within :305); _run loop checks (:422,
:429) and cumulative read (:451) are unlocked but GIL-atomic
bools/ints with harmless staleness (extra loop iteration,
slightly old recency input); close fail-path takes the lock.
No torn read possible at these sites. Verdict: PARK STANDS
(locks would risk more than they buy).

R1 write_wiki double index — VERIFIED, plus an MCP third.
write_wiki (memory_engine.py:2513) indexes at Step 2 (:2547,
freshness for OTHER files before link search, new file
excluded) and Step 4 (:2591, persist file+links); MCP
memory_write then indexes a THIRD time (server write path).
Step-2's own comment offers the cheaper alternative
("...OR search before indexing it"). Fix shape: drop Step-2
index (link search tolerates staleness: advisory cross-refs,
misses self-heal), keep Step-4, caller skip-flag for the MCP
third. Fix risk LOW-MED (bounded link-recall dip on
concurrent-change windows). Band implied-made-real. Verdict:
KEEP, do-soon (#9 holds).

R2 overflow-submit cumulative drift — VERIFIED, re-pinned.
submit() increments+persist the protection counter
(symbiose_worker.py:348-359) BEFORE the queue put; overflow
returns after (~:381-388) without compensating: rejected work
inflates the counter, engaging recency-gating early (weaker
protection). Per-incident impact tiny (drain stops at first
overflow, queue caps at 8) but the counter feeds a safety
threshold. Fix shape: move increment+persist after successful
put (inside the held lock; put_nowait cannot deadlock).
Decrement-on-overflow rejected (transient lie, double I/O).
Fix risk LOW. Band implied-made-real. Verdict: KEEP, do-first
(#4 holds).

E-T16-5 wait() ignores injected clock — VERIFIED, DOWNGRADED
to do-soon (new tier; was do-first #6). wait()
(symbiose_worker.py:411) hardcodes time.monotonic() (:412
deadline, :413 loop-check) while _clock is used at 14 other
sites (:222/:277/:298/:303/:306/:335/:385/:391/:405/:447/
:449/:458/:466/:520): injected fake clocks cannot control
waits. Zero clock-injecting tests exist today
(test_symbiose_worker.py grep: none), so harm is potential
(untestable timeouts), not active (waits behave). Fix shape:
use self._clock() in wait plus documented fake-advance
contract for tests. Fix risk LOW (2 lines, no test updates
needed). Band implied-made-real (clock seam honored).
Verdict: KEEP, do-soon (new tier).

E-T16-1 per-model effective threads order-dependence —
WITHDRAWN, mechanism absent. resolve_threads_for
(memory_engine.py:443, no decorator, pure) resolves per model
from env map, legacy profile, then registry; sole caller
models (L1281) passes each model its own name; memo keyed by
slug (correct, not first-wins). No shared state, no cache,
no order path: "first value wins by call order" cannot occur
in the current tree. Verdict: WITHDRAWN (first redo
withdrawal). Revisit only as a NEW entry with live
per-model contention measurements.

E-T16-3 render_table dead — VERIFIED (file corrected).
render_table lives in execution/tui_renderer.py:65, not
context_budget.py (first-pass misattribution); tree-wide
git-grep shows the def plus only this ledger's own citation:
zero prod callers, zero test callers. Fix shape: delete the
one function; suite green confirms nothing breaks (nothing
can). Fix risk NIL. Below bands (hygiene). Verdict: KEEP
hygiene (delete when adjacent).

E-T16-2 summary-budget shed metric — VERIFIED, widened: whole
function dead in prod. enforce_summary_budget
(context_budget.py:755) computes (summary, shed_chars) but has
zero production callers tree-wide (tests only:
test_context_budget.py:286/290, test_rtrre_matrix.py:148/154/
160); SHED_MARKER (:55) used only by its body (:767/:783).
Fix shape: delete fn plus marker, retire the 4 test calls;
suite green confirms. Fix risk NIL. Below bands (hygiene).
Verdict: KEEP hygiene (delete when adjacent).

R4 egg citation hash-pin — VERIFIED OPEN. test_citation_
identical_across_all_three_copies
(execution/test_installer.py:141) pins by equality against
EASTER_CITATION (:136), a constant quoting the spoiler text:
the pin works but leaks the egg into the test file (spoiler
doctrine RRD-66: test files are not the egg). Fix shape:
compare hashes (pinned digest constant; text never quoted).
Fix risk NIL (test-only). Band gain-beside (test-only).
Verdict: KEEP, small+safe (#18 holds).

Installer uv-pip fallback for --wheel — VERIFIED. execute_plan
(installer/launchers/python_launcher.py:321) installs via bare
sys.executable -m pip (:341-346, check=False, False on
failure): uv-managed interpreters lack pip, so --wheel installs
fail there. Fix shape: fall back to uv pip on pip failure
(runtime probe, self-proving); if uv also absent, error panel
naming both. Fix risk LOW. Band gain-beside. Verdict: KEEP,
do-soon (#15 holds). Revisit if uv absent too (then error
panel naming both).

Registry-validated installer names — VERIFIED, guidance shape.
presetName entered free-typed (installer/launchers/
python_launcher.py:551, no check) and written into live
keeper.json unvalidated (:311/:326, default only on missing):
typos fail late and confusingly at keeper refusal. validated_int
(:348-350) declares registry membership keeper-owned (single
validator): installer must not duplicate enforcement. Fix
shape: installer reads the registry for prompt completion
(guide, not enforce); keeper keeps refusal; probe registry
readability from the installer at implementation. Fix risk
LOW. Band gain-beside. Verdict: KEEP, do-soon (#16 holds).
Revisit if registry unreadable (then snapshot or preflight).

E-T19 demo server half — PARK STANDS, conditional false.
installer/shell/ holds assets/css/dtd/index.html/js/tools:
no server half exists, browser stays demo-only (RRD-54b
holds). Verdict: PARK STANDS (unpark iff the shell
graduates; then this becomes the feature entry).

R3 node readScene drops camera pitch — VERIFIED, node-reads.
Scene DTD (rtrre-scene.mod:34) declares camera pitch
(default -0.16); python reads it
(python_launcher.py:112, sole hit: parsed-never-used in
terminal); node readScene (node_launcher.mjs:42) parses
drift but not pitch. Fix shape: node reads pitch mirroring
py (1 line, schema completeness); parsed-never-used is fine
(data preserved). Fix risk NIL. Below bands? No — small+safe:
nobody's hygiene covers installer parity. Verdict: KEEP,
small+safe (#19 holds).

E-T17 eval internals — NO OPEN ENTRIES. All J-findings routed
(J10/J11 to TODO-23 done, J15/J17/J22/J29 to TODO-24,
J1/J3/J4/J8/J16/J23 to TODO-25, J27/J28 to TODO-26,
mirror-hazard to TODO-30). Nothing to redo-verify; routes
tracked by their owners. Verdict: NOTHING OPEN (by routing).

H4/H7/H10/H11 title-only pack — PARK STANDS, no new info.
RRD-102's record holds: detail lost with the study spans;
re-derivation means re-doing TODO-16 wholesale (out of redo
scope). Titles preserved; pursued only by explicit order with
fresh study. Verdict: PARK STANDS (no code read — nothing new
to read against).
