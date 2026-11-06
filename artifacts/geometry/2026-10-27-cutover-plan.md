<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Cutover plan: ACP off, new instance on (operator executes, agent never touches live config)

Precondition (all green this cycle): keeper 19/19 (both trees), Python
117 lab + 117 standalone, Lean 8 jobs, ACP suite 1390/1390, wheel with
keeper asset, dummy5 T5 live-reload proof, frozen benches.

## Steps (operator machine, ~10 minutes)
1. Backup live config: copy `~/.config/opencode/opencode.jsonc` and
   `~/.config/opencode/acp.jsonc` to `*.bak.20261027-cutover`.
2. Install wheel (or reuse published): `uv tool install rtr-role-type-retrieval`
   (or `pip install`), then `rtr-re-install-opencode` — copies the Keeper
   plugin into `~/.config/opencode/plugin/` and prints the MCP snippet.
3. Edit `opencode.jsonc`: remove `opencode-acp@stable` from `plugin`,
   add `./plugin/rtr-re-keeper.js`; point `mcp.memory.command` at the
   standalone `rtr-re-mcp` (keep model/tool env; add
   `OPENCODE_MEMORY_RTRRE_*` only if non-default bounds wanted).
4. Optionally write `~/.config/opencode/rtr-re-keeper.json`? NO —
   keeper config is project-local (`.opencode/rtr-re-keeper.json`);
   global default is 320k/128k/40. Skip unless a project needs it.
5. Restart OpenCode. The old cached `rtr-mcp.exe` must no longer appear
   in the MCP command path.
6. Post-restart survey (TODO-14): `memory_rtr_status` with a project arg
   must read ACTIVE after one exchange; `memory_context_plan`,
   `memory_symbiose_submit/poll` answer; ACP tools absent;
   `/rtr status` prints bounds; one known retrieval hits.

## Rollback
Restore the two `.bak.20261027-cutover` files and restart. The old ACP
world is untouched until the operator deletes it. `acp.jsonc` is NOT
deleted by the installer — removal is an explicit operator act after
the survey passes.
