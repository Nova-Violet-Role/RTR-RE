<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RTR-RE .mjs edition — persistent memory without an MCP server

The full RTR-RE discipline for people who do not want to run an MCP
server: session memory, context budget rules, and **AUTO-OPTIMIZE** —
an optimize pass instigated between every file read and the next code
write, unasked, so code written by a model that never looks back still
gets a second look before it lands.

Retrieval itself runs through the `rtr-cli` command from the Python
package (`uv tool install rtr-role-type-retrieval`). The plugin starts
no server, opens no socket, and holds no index: it injects the rules,
keeps the mode on, and points the agent at the CLI. If `rtr-cli` is
missing, the rules say so out loud and the session continues on files.

## Install (OpenCode)

The npm installer route (terminal-native, no browser, no network):

```bash
npx rtr-re-installer
```

Manual: copy `mjs/.opencode/` into your project or `~/.config/opencode/`
(plugins in those directories load automatically), plus `mjs/hooks/`,
`mjs/skills/`, and `mjs/AGENTS.md` beside them at the same relative
paths the core expects — or clone this repo and add to `opencode.json`:

```json
{ "plugin": ["@nova-violet-role/rtr-re-mjs"] }
```

## Install (Claude Code / Codex)

Wire `hooks/claude-codex-hooks.json` as your hooks file (or merge its
three events): SessionStart injects the full ruleset, UserPromptSubmit
keeps a one-line reminder alive and catches the toggles, SubagentStart
covers delegated work.

## Toggles

On by default every new session. Off for the session only:
`/rtr off`, `stop rtr`, or `normal mode`. Back on: `/rtr` or `/rtr on`.
The off state is one flag file (`.rtr-off` in the host config dir);
deleting it turns the mode back on.

## AUTO-OPTIMIZE, exactly

State machine in `hooks/rtr-core.js` (`createAutoOptimizer`): the first
`read` tool result of a cycle gets one appended line — reuse what you
read, delete what earns nothing, simplify, name one concrete way the
draft beats the obvious first version. Further reads stay silent; the
next `write`/`edit` re-arms. The plugin never edits code itself; it
instigates the agent at the moment the draft forms.

## Parity with the MCP server (26 tools), honestly

| Surface | .mjs edition |
|---|---|
| search, explain, write, index, stats, init, consolidate, session-start, session-commit, reflect, materialize, update-graph, lexikon (add/show/build), janitor (16) | `rtr-cli` bridge — same engine, same index |
| context_plan | native JS arithmetic (`planContext`, same defaults) |
| keeper window discipline | rules + budget numbers in the ruleset; the native keeper plugin (`opencode-plugin/rtr-re-keeper.js`) remains the enforcement arm |
| discover, list, inbox, organize, delete, rtr_status, symbiose submit/poll | not on the CLI today: rules degrade to direct file work + `session-commit`; named as the next CLI slice, not faked |

## Architecture (one core, three shells)

`hooks/rtr-core.js` (zero dependencies) owns state, the rules cascade
(SKILL.md → AGENTS.md → inline fallback), toggles, AUTO-OPTIMIZE,
context-plan arithmetic, CLI argument building, and per-host hook
output. `.opencode/plugins/rtr.mjs` is the thin OpenCode shell over
that same core (`createRequire`), so no rule exists in two places.
`AGENTS.md` is generated from `skills/rtr/SKILL.md` by
`scripts/generate-agents.js`; the test suite fails if they drift.

Tests: `node --test tests/*.test.mjs` (also `npm test`).

## License

Dual EUPL-1.2 / AGPL-3.0-or-later, Nova-Violet Role ORG. Forms mirror
the MIT-licensed agile plugin (Hubert Lepicki) and through it ponytail
(DietrichGebert) — see `LICENSE` in this directory.
