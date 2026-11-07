# Plugin architecture study — 2026-11-07 (for RTR-RE no-MCP empowerment)

Study of three plugin sources for empowering RTR-RE's no-MCP center
(rtr-core.js, keeper, TUI). Every pattern below is read from the cited file.

Sources:

- **Agile** (`C:\Users\Saimono\.cache\opencode\packages\@hubertlepicki\agile\
  node_modules\@hubertlepicki\agile`) — the operator-rated best system-binding
  plugin.
- **C:\Plugins-to-study** — `opencode-thinking-fix` (V1+V2 plugin, proxy,
  watchdog), `opal` (Python skill/agent framework), `ub-mode` (skill-only
  plugin).
- **ECMAScript docs** — `C:\Microsoft Skill OPT and Skill LENS install via
  UV\ECMAScript-features` (per-edition feature examples, es2015–es2025) and
  `complete-ECMAscript-documentation` (docs-site shell).

---

## 1. Agile — the binding patterns (measured)

`hooks/agile-core.js` + `agile-prompt.js` + `agile-subagent.js`:

1. **State file as the single source of truth**: a flag file (`.agile-off`)
   in the state dir; `isActive()` = file absent. Toggle = create/delete the
   file. No config plumbing, no TUI needed.
2. **Message-content command parsing**: `DEACTIVATE`/`REACTIVATE` regexes
   match `stop agile`, `normal mode`, `/agile off`, `/agile on` in the user
   prompt (UserPromptSubmit hook). The plugin listens to what the user types
   and flips its own state — fully autonomous, zero UI.
3. **SessionStart injection of the full ruleset** + **per-turn short
   reminder**: the full SKILL.md ruleset goes into session context once at
   start; every turn only re-sends a one-line reminder (efficient context
   use). AGENTS.md is a generated fallback.
4. **Subagent propagation**: SubagentStart injects the ruleset into subagents,
   which never see SessionStart context.
5. **Robustness**: BOM-safe JSON parse; unparseable payload falls through to
   the full ruleset (never silently drops); best-effort state writes never
   block the session; a closed stdout at hook exit is not a hook failure.
6. **Host detection**: `PLUGIN_DATA` env (Codex) vs `CLAUDE_CONFIG_DIR`
   (Claude Code) — one codebase, two hosts.

## 2. Plugins-to-study

### opencode-thinking-fix (`plugins/opencode-thinking-fix-universal.ts`)

The modern opencode hook surface, used directly:

- `experimental.chat.messages.transform` (V1 legacy hook).
- `ctx.session.hook('model.request', ...)` (V2 — comment maps legacy
  `chat.headers` → this).
- `ctx.session.hook('context', (event) => inspect(event.messages))` (V2 —
  legacy `chat.messages.transform` → this).
- `ctx.session.hook('compaction', (event) => inspect(event.messages))`.

Pattern: one plugin registers both V1 and V2 surfaces; message patching
(reasoning_content fields) runs identically in both. `"type": "module"` +
`"oc-plugin": ["server"]` in package.json.

### opal (`pyproject.toml`, `opal/`, `skills/train-with-agent/`)

A Python skill/agent framework: skills live as directories (SKILL.md +
assets), pip-installable, with tests. The skill-as-package pattern.

### ub-mode (`SKILL.md`)

The minimal skill-only plugin: YAML frontmatter (`name`, `description` with
"Use when…" trigger) + a short rule body. This is the canonical skill.md
shape — and the shape the operator wants to make "cross mjs-js strong".

## 3. ECMAScript features (es2015–es2025)

Per-edition runnable examples. The features most relevant to plugin
architecture:

- **es2022**: `array.at()`, class fields, error-cause, hasOwn, regex
  indices — plus (in the spec) top-level await and static blocks.
- **es2023**: array find-from-last, toSorted/toReversed/toSpliced/with.
- **es2024**: `Object.groupBy`/`Map.groupBy`, well-formed Unicode strings,
  `Atomics.waitAsync`, `Promise.withResolvers`.
- **es2025**: set methods, iterator helpers, Temporal API, decorator metadata.

For RTR-RE's mjs/JS layer: **top-level await** (module init can await
registry/model loads), **Promise.withResolvers** (clean async hook bridges),
**Object.groupBy** (partitioning messages by role/lane), **iterator helpers**
(streaming transforms), **Temporal** (timestamps for keeper status/recency).

## 4. Adaptation proposals for RTR-RE no-MCP

- **P1. Message-content command surface**: adopt Agile's regex-on-prompt
  pattern — the keeper already parses tool calls; add a prompt-level parser so
  `/rtr status|preset|max|off|on` works in plain chat without TUI (mirrors
  the existing palette commands, zero UI).
- **P2. SessionStart + per-turn reminder split**: move the keeper's full
  context injection to session start and keep a one-line reminder per turn
  (currently the keeper injects per exchange; split it for efficiency).
- **P3. Subagent propagation**: inject memory/keeper context into subagents
  via SubagentStart-equivalent (opencode's subagent hook), since subagents
  never see SessionStart context.
- **P4. Modern hook surface**: register both V1 (`experimental.chat.messages.
  transform`) and V2 (`ctx.session.hook('context'|'compaction'|'model.
  request')`) like thinking-fix, so the keeper observes and survives both
  plugin generations.
- **P5. ESM capabilities**: use top-level await for registry load in the
  plugin module; `Promise.withResolvers` for the async bridge; `Object.
  groupBy` for message partitioning; Temporal for status timestamps.
- **P6. Skill-as-ruleset with cross mjs-js reach**: the skill.md body should
  be loadable by both the mjs plugin (as the injected ruleset) and the JS
  keeper (as its instruction source) — one file, two hosts, like Agile's
  SKILL.md + AGENTS.md fallback.

Encoding: UTF-8, LF, no BOM, no CR.
