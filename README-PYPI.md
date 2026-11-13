<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RTR-RE:Symbiose (rtr-role-type-retrieval) — dense usage manual

RTR-RE:Symbiose (Role-Type-Retrieval-RE:Symbiotized) 1.2.2: RRF-heuristic,
DTD-semantic-capable persistent memory + symbiotized context engine for
coding agents. Dual ONNX ensemble on CPU, zero API cost, local only.
Three offices: native Keeper plugin (window), background Compressor
(verbatim until trigger, drain to target), RTR Manager
(retrieval of what left the window).

**Engine vs car:** RTR (the `rtr-role-type-retrieval` repo) is the retriever
alone. RTR-RE is the full system: RTR retrieval + Keeper + Compressor + Manager
+ engine-beneath + installer + live-tuning palette. The preset registry is
shared; the keeper presets are RTR-RE's section.

The **.mjs edition** (`mjs/` in the repo) provides the same memory
discipline with **no MCP server**: an OpenCode plugin + Claude Code /
Codex hooks over one zero-dependency core, retrieval through `rtr-cli`,
and **AUTO-OPTIMIZE**, an optimize pass instigated between every file
read and the next code write. Two measured defects stay fixed since the 0.4.x line: engine close/reopen returning a dead Chroma client, and
wikilink expansion crashing search on chromadb 1.5 (`$contains in get`);
dependencies are now bounded to tested majors.

RTR-RE ships as its own standalone git repository: no lab sync tooling is
included, and the shipped tree is the git history itself.
By [Nova-Violet Role](https://github.com/Nova-Violet-Role) — non-profit.
**AGPL-3.0-or-later OR EUPL-1.2.** Support: [ko-fi.com/saimonokuma](https://ko-fi.com/saimonokuma).

## 1. Run it — the installer (terminal-native, no browser, no network)

```bash
uvx --from rtr-role-type-retrieval rtr-re-install
```

Session details (presets, themes, flags, easter egg): [§8a](#8a-the-installer-session-terminal-native).

Manual paths (no clone, no venv, no sync in any of them):

```bash
# A. Zero-install, every session: uvx caches + isolates automatically
uvx --from rtr-role-type-retrieval rtr-mcp            # MCP server over stdio
uvx --from rtr-role-type-retrieval rtr-cli stats      # CLI
uvx --from rtr-role-type-retrieval rtr-re-install-opencode   # native Keeper plugin + config snippet

# B. Persistent tool install
uv tool install rtr-role-type-retrieval
rtr-mcp
rtr-cli index

# C. Classic pip (you manage the venv)
pip install rtr-role-type-retrieval
rtr-mcp
```

First run downloads embedding models once (~650 MB: Arctic-m 768 + bge-base 768)
into `FASTEMBED_CACHE_PATH` — **pin it to persistent storage** (default is the
system temp dir and can be wiped). Models then load warm every session.

## 2. Wire it into your agent CLI (model-agnostic: works with any LLM, local or API)

The server is plain MCP-over-stdio. It never calls an LLM itself — embeddings
are local ONNX — so it works with Claude, GPT, GLM, Kimi, Ollama-driven harnesses,
anything with an MCP client.

```jsonc
// opencode.jsonc  — global config, automatic every session
"mcp": {
  "memory": {
    "type": "local",
    "command": ["uvx", "--from", "rtr-role-type-retrieval", "rtr-mcp"],
    "enabled": true,
    "timeout": 180000,   // cold model load on very first start
    "environment": {
      "OPENCODE_MEMORY_RTR_PROFILE": "performance",  // balanced 4+4 | performance 8+8
      "OPENCODE_MEMORY_PROJECTS_DIR": "C:/Users/you/projects",  // ;-separated multi-root
      "FASTEMBED_CACHE_PATH": "C:/Users/you/.config/opencode/memory/.fastembed_cache"
    }
  }
}
```

```json
// Claude Code / any MCP-stdIO client: same command, same env
{ "mcpServers": { "rtr-memory": {
  "command": "uvx",
  "args": ["--from", "rtr-role-type-retrieval", "rtr-mcp"],
  "env": { "OPENCODE_MEMORY_RTR_PROFILE": "balanced" }
} } }
```

```bash
# Local-LLM harnesses without MCP: use the CLI as tools
rtr-cli session-start /path/to/project     # restore goals/blockers/prefetch
rtr-cli search "buffer API quirks" --project myproj --k 5
rtr-cli session-commit /path/to/project --chat "...session log..."
```

## 3. Project bootstrap (works anywhere — absolute paths auto-register)

```bash
rtr-cli init /any/where/myproj              # harness tree; dir joins discovery roots
rtr-cli init myproj --variant design        # design_wiki flavour
rtr-cli index                               # delta index (hash-guarded, per-model collections)
rtr-cli index --project /any/where/myproj   # force-register then index
```

Indexed suffixes: `.md`, `.nt`, `.yaml`, `.yml`, `.dtd`, `.mod`, `.ent` (`OPENCODE_MEMORY_FILE_SUFFIXES`
overrides). Sources of truth stay in each project's `directives/`; the vector
store (`~/.config/opencode/memory/.local_vector_db`) is a derived global cache,
partitioned per project. Reopen the same project name → memory restored.

## 4. Every environment knob (one global local config)

| Variable | Default | Meaning |
|---|---|---|
| `OPENCODE_MEMORY_EMBED_MODELS` | `Snowflake/snowflake-arctic-embed-m,BAAI/bge-base-en-v1.5` | comma-separated fastembed models; one ChromaDB collection each |
| `OPENCODE_MEMORY_RTR_PROFILE` | `balanced` | `balanced` = 4+4 threads, `performance` = 8+8 |
| `OPENCODE_MEMORY_EMBED_THREADS` | profile default | int for all models, or per-model `arctic:4,bge:8` |
| `OPENCODE_MEMORY_PROJECTS_DIR` | `~/projects` | `os.pathsep`-separated discovery roots |
| `OPENCODE_MEMORY_FILE_SUFFIXES` | `.md,.nt,.yaml,.yml,.dtd,.mod,.ent` | indexed file types (DtD polyglot) |
| `OPENCODE_MEMORY_RRF_K` | `60` | RRF dampening; fuses rankings, never raw scores |
| `OPENCODE_MEMORY_RRF_VOTE_TOP` | `10` | per-run rank vote truncation (0 disables) |
| `OPENCODE_MEMORY_STRUCT_LANE` | off | `rg`/`ccc`/`auto` = structural grep lane for code-shaped terms |
| `OPENCODE_MEMORY_RTRRE_TRIGGER` | `400000` | Compressor trigger tokens (scale below your model input cap) |
| `OPENCODE_MEMORY_RTRRE_TARGET` | `200000` | verbatim tail kept after the drain (target) |
| `OPENCODE_MEMORY_RTRRE_PRESET` | `re-symbiose-mugen` | keeper preset: `re-symbiose-mugen` 400k/200k/200 (default) · `symbiose-ah` 250k/100k/40 · `fusion-ah` 200k/100k/30 · `re-symbiose` 320k/128k/50 · legacy `standard`/`calibrated`/`wide` |
| `OPENCODE_MEMORY_RTR_PRESET_PROFILE` | `public-default` | CPU profile: `public-default` (T4/P60) or `local-system` (T8/P80) |
| `OPENCODE_MEMORY_RETRIEVAL_MODALITY` | `rtr-full` | retrieval modality: `rtr-full` (dual), `rtr-arctic`, `rtr-bge`, `rag-hybrid-base`, `rag-dense-base`, `rag-hybrid`, `rag-dense`, `custom` |
| `OPENCODE_MEMORY_CPU_PARKING_PERCENT` | profile default | CPU parking percent (20–80) — cores kept awake for embedding |
| `OPENCODE_MEMORY_RTRRE_MAX_KEEP` | `200` | max verbatim messages kept |
| `RTR_RE_KEEPER_CONFIG` | `<project>/.opencode/rtr-re-keeper.json` | live Keeper bounds file (watched, no restart) |
| `RTR_RE_KEEPER_STATUS` | `<project>/.opencode/rtr-re-keeper-status.json` | Keeper status file read by `memory_rtr_status` |
| `RTR_RE_KEEPER_ENABLED` | unset (enabled) | `0`/`false`/`no`/`off` disables pruning (identity transform); other values refuse |
| `OPENCODE_MEMORY_PRF` | `0` | `1` = pseudo-relevance-feedback second pass |
| `OPENCODE_MEMORY_DB_DIR` | `<memory>/.local_vector_db` | override vector DB home (bench isolation) |
| `FASTEMBED_CACHE_PATH` | system temp | **override this** — model home, persistent |
| `PYTHONIOENCODING` | — | set `utf-8` on Windows for the TUI panels |

**Advanced knobs** (defaults read from code; most operators never touch these):

| Variable | Default | Meaning |
|---|---|---|
| `OPENCODE_MEMORY_DIR` | `~/.config/opencode/memory` | memory root; registry, extra roots, lexikon live here |
| `OPENCODE_MEMORY_REGISTRY_FILE` | `<memory>/wiki_registry.json` | concept registry path |
| `OPENCODE_MEMORY_EXTRA_ROOTS_FILE` | `<memory>/extra_roots.json` | extra discovery roots file |
| `OPENCODE_MEMORY_LEXIKON_GLOBAL_FILE` | `<memory>/lexikon_global.json` | hand-curated `_global` lexikon path |
| `OPENCODE_MEMORY_DTD_CHUNK_MODE` | `inventory` | DTD chunking strategy |
| `OPENCODE_MEMORY_DTD_CHUNK_TOKENS` | `512` | DTD chunk token bound |
| `OPENCODE_MEMORY_DTD_MAX_CHUNKS` | `2000` | DTD chunk hard ceiling |
| `OPENCODE_MEMORY_DTD_PER_DECLARATION_MAX` | `300` | per-declaration cap |
| `OPENCODE_MEMORY_DTD_LEXIKON_SEED` | `1` | `0` disables DTD vocabulary lexikon seeding |
| `OPENCODE_MEMORY_HNSW_NUM_THREADS` | unset (Chroma default) | HNSW index build threads |
| `OPENCODE_MEMORY_HNSW_SEARCH_EF` | unset (Chroma default) | HNSW search ef |
| `OPENCODE_MEMORY_QUERY_PROMPT_OVERRIDE` | empty (off) | override the query prompt template |
| `OPENCODE_MEMORY_RRF_CONSENSUS` | `0` | `1` down-weights confidently-wrong runs in fusion |
| `OPENCODE_MEMORY_WARM_MODELS` | unset (warm) | models warm at server start unless `0`/`false`/`no`/`off` |
| `OPENCODE_MEMORY_RTRRE_MAX_SUMMARY` | `20000` | max summary chars |
| `OPENCODE_MEMORY_RTRRE_MAX_RESTORE` | `4000` | max restore chars |
| `OPENCODE_MEMORY_RTRRE_CUMULATIVE` | `0` | cumulative message seed for cross-restart accounting |
| `OPENCODE_MEMORY_RTRRE_REGISTRY_FILE` | first existing (repo, bundled asset) | preset registry override |

## 5. Tools exposed (MCP) and CLI map

`memory_session_start` · `memory_session_commit` · `memory_reference_add` · `memory_reflect_session` ·
`memory_materialize_concepts` · `memory_update_graph` · `memory_search` ·
`memory_explain_search` · `memory_discover` · `memory_list` · `memory_delete` ·
`memory_inbox_write` · `memory_inbox_read` · `memory_write` · `memory_organize` ·
`memory_init_project` · `memory_consolidate` · `memory_stats` · `memory_index` ·
`memory_lexikon_add` · `memory_lexikon_show` · `memory_lexikon_build` ·
`memory_janitor` · `memory_context_plan` · `memory_symbiose_submit` ·
`memory_symbiose_poll` · `memory_symbiose_drain` · `memory_symbiose_compress` ·
`memory_keeper_evict_now` · `memory_doctor` · `memory_repair` ·
`memory_rtr_status` (32 tools; the symbiose/keeper/doctor/repair/status set is the
live loop surface — background tickets that never pause the turn, plus the
truthful status/health viewport reporting Keeper, Compressor and Manager).
Supervision beyond v2: gold v3 (785 judgments, additive only, labels frozen)
reruns the same verdict; the Lean battery builds against full Mathlib
(pinned v4.33.0, green, 0 sorry).
CLI mirrors the core verbs (`rtr-cli <verb> --help` each): consolidate, context-plan, explain, index, init, janitor, keeper-evict-now, lexikon-add, lexikon-build, lexikon-show, materialize, reflect, search, session-commit, session-start, stats, symbiose-compress, symbiose-drain, symbiose-submit, update-graph, write.

Lexikon: per-project glossary auto-derived from registry + sessions, plus a
hand-curated `_global` user lexikon (`rtr-cli lexikon-add _global "term"
--definition "..." --alias ...`) — lookup-first expansion, no inference.
Maintenance: `rtr-cli janitor [--dry-run]` deletes orphan chunks whose files
are gone (also `memory_janitor`).

## 6. How retrieval works (the 30-second version)

Per query: original + lexikon/alias + workspace-delta sub-queries (+ optional
PRF) × per-model collections → decisiveness-weighted RRF (top-10 vote
truncation) → min-max normalized dense mixed with BM25 under standout lane
weights (dense-led 0.45/0.30 defaults; a lone lexical standout may take the
lead, weights always sum to 0.75) + `0.15·recency + 0.10·importance`, plus
one shared 0.15-capped bonus lane split disjointly between CDATA exact
terms and optional structural-grep hits (`OPENCODE_MEMORY_STRUCT_LANE`).
Spans are DTD-typed at index
(`PCDATA`/`CDATA`/`NDATA` + NOTATION recorded, NDATA masked pre-embedding).
Same-name projects across roots resolve first-match; absolute paths always exact.
Query prompts are per-model from each model's own card: Arctic-m gets its
instruction prefix, bge-base declares none so it embeds raw queries — the
asymmetry is correct by design (an instruction prefix would push a
non-instruction model off-distribution, not prepare it).

## 6b. Overseeding — bigger turbos welcome (bi-turbo philosophy)

RTR runs twin powerplants — Arctic precision plus bge recall — fused by RRF,
the way rally engineers ran bi-turbo: not because one turbo wasn't enough,
but out of love for solving the paradigm. Discoveries live there.

Any fastembed model slots in via one variable, and because every model owns
its collection, **overseeding is zero-migration**: point, re-index, the old
collections janitor away. Measured guidance from our own bench:

| Your hardware | Suggestion | Why |
|---|---|---|
| 8 cores | default dual (arctic-m + bge-base), `balanced` 4+4 | the efficiency crown |
| 12–16 cores | same dual, `performance` 8+8 | headroom well spent |
| Strong CPU + RAM | `BAAI/bge-large-en-v1.5` and/or `Snowflake/snowflake-arctic-embed-l` (1024d) | precision ceiling rises with dim |
| Keyword-heavy corpus | try single `BAAI/bge-base-en-v1.5` | our bench: BM25-adjacent turf favors focus |

```bash
OPENCODE_MEMORY_EMBED_MODELS="BAAI/bge-large-en-v1.5,Snowflake/snowflake-arctic-embed-l"
rtr-cli index          # new collections fill; old ones: rtr-cli janitor
uv run python eval/bench_versus.py   # prove it on your own corpus before you believe us
```

Honest note: bigger is not always better — on keyword-dense corpora our bench
favors focus over size. Measure, don't assume. If your turbo wins, tell us;
falsification is a contribution here.

## 6c. Live Keeper control (no restart)

The Keeper watches `<project>/.opencode/rtr-re-keeper.json` and reloads it
when it changes, so the next exchange already runs the new bounds. From any
session, slash commands do the same (confirmation rides back as the command
result; the window itself is untouched):

```
/rtr status              bounds, last decision, sink, errors
/rtr hold 100000         preserved tail (target)
/rtr trigger 250000      eviction starts here
/rtr max 200             message cap
/rtr preset fusion-ah|symbiose-ah|re-symbiose|re-symbiose-mugen|standard|calibrated|wide
/rtr disable | /rtr enable
```

The ctrl+p palette (TUI plugin `rtr-re-tui.tsx`) exposes the same knobs as
commands under **RTR Keeper**: status, enable, disable, preset, cpu, modality,
threads, parking, trigger, target, max — each writes the same watched file, so
every change applies on the next exchange with no restart. Presets (shared
registry, 1.2.0): `re-symbiose-mugen` 400k/200k/200 (default) · `symbiose-ah`
250k/100k/40 · `fusion-ah` 200k/100k/30 · `re-symbiose` 320k/128k/50 ·
legacy `standard`/`calibrated`/`wide`.
The Keeper protects `todowrite` messages and the last user message; eviction is
oldest-first, sink-first, fail-open.

Every transform also writes `.opencode/rtr-re-keeper-status.json`; the
`memory_rtr_status` MCP tool reports it alongside Compressor bounds, worker
ticket health and Manager index state — absent evidence reads absent, never
invented.

## 7. Verify it (falsifiable or it didn't happen)

```bash
uvx --from rtr-role-type-retrieval python -m execution.rtr_eval  # release gate
uv run python -m unittest execution.test_memory                  # unit suite
node --test opencode-plugin/rtr-re-keeper.test.mjs                # Keeper suite (repo)
bun test opencode-plugin/rtr-re-tui.test.ts                       # ctrl+p palette suite (repo)
uv run python eval/bench_versus.py --intense                     # RTR-vs-RAG bench, real docs
uv run python eval/bench_graded.py --queries eval/graded/queries-v2.json --qrels eval/graded/qrels-v2.json
```

`eval/results/` ships the scoreboard JSON, the Mermaid source, and the SVG.

## 8. Troubleshooting

- **Slow first start** — model download (~650 MB); later starts are warm. Raise MCP `timeout` once.
- **HF rate limits** — set `HF_TOKEN`; downloads resume.
- **Windows paths** — forward slashes work everywhere in this config.
- **Empty results** — project must live under a discovery root or be touched once by absolute path (auto-registers); check `rtr-cli stats`.
- **ChromaDB lock errors** — one writer at a time; close stale sessions.

## 8a. The installer session (terminal-native)

The installer runs entirely in the terminal — no browser, no HTTP, no
network. Same experience on every platform, three personalities:

```bash
# pip / uvx — The Instrument (cool cyan, oscilloscope progress)
uvx --from rtr-role-type-retrieval rtr-re-install --theme instrument

# npm — The Network (magenta/violet, node-graph progress)
npx --package rtr-re-opencode-plugin rtr-re-installer --theme network

# GitHub — The Forge (charcoal/emerald, raw build-log stream)
python installer/launchers/python_launcher.py --theme forge
```

Flags (Python `installer/launchers/python_launcher.py`): `--theme instrument|network|forge` (default instrument), `--project DIR` (default cwd, or `RTRRE_INSTALL_PROJECT`), `--wheel PATH` (installs the wheel, or `RTRRE_INSTALL_WHEEL`). Flags (Node `installer/launchers/node_launcher.mjs`): `--theme` (default network, or `RTRRE_INSTALL_THEME`), `--project DIR` (or `RTRRE_INSTALL_PROJECT`), `--tarball PATH` (or `RTRRE_INSTALL_TARBALL`). `--wheel` needs pip on the running interpreter (uv-managed Pythons ship without it — install the wheel with `uv pip` separately in that case). `RTRRE_INSTALL_NO_AUDIO=1` silences the remixes on both launchers (headless installs). The session offers four presets — Quick (MUGEN one-click),
Custom (component selection), Hardcore (full cockpit with
Recommended-from-Saimonokuma badges), Manual (palette guide, no automation) — plus adaptive arcade remixes of
*Obsession* and the MiDi-MoE-Symbiogen-000 easter egg. The scene is a
DTD family member (`installer/shell/dtd/rtrre-scene.mod`); the shell
markup is validated against the declared vocabulary by
`installer/shell/tools/conformance.py`. The same shell doubles as a browser demo: open `installer/shell/index.html` over `file://` (instrument theme; plan and execute fall back to demo responses — no launcher serves the bridge API, so installation itself always runs in the terminal launchers).

## 9. Licence

Dual-licensed, copyleft, binding: **AGPL-3.0-or-later OR EUPL-1.2**
(`LICENSE-AGPL-3.0.txt`, `LICENSE-EUPL-1.2.txt`, `NOTICE`). Upstream note: the
retrieval core derives in part from `github.com/xpajonx/opencode-memory`, which
ships no licence file — public redistribution of the combined work awaits
upstream clarification.
