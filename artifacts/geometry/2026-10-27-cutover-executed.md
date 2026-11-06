<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Cutover executed (2026-10-27, agent-executed on operator order)

Supersedes the operator-executes posture of 2026-10-27-cutover-plan.md:
the operator ordered agent execution. Measured, in order:

1. Backups: opencode.jsonc + acp.jsonc copied to *.bak.20261027-cutover,
   verified byte-identical. acp.jsonc left in place (rollback intact).
2. Wheel rebuilt from C:/RTR-RE (uv build, both artifacts green), then
   uv tool install --force from the local wheel. 6 executables installed;
   rtr-re-mcp.exe present in scoop/persist/uv/tools/shims.
3. rtr-re-install-opencode copied the Keeper into the live plugin dir:
   22580 bytes, sha256 552005ab... matches SYNC-MANIFEST.json and the
   standalone source byte-for-byte. node --check exit 0 on the live copy.
4. opencode.jsonc edited in 4 lines only (diff vs backup verified):
   memory command -> shims/rtr-re-mcp.exe; plugin opencode-acp@stable ->
   ./plugin/rtr-re-keeper.js. Environment block untouched. CR 0.
5. MCP handshake smoke (initialize + tools/list over stdio, live env):
   26 tools incl. memory_rtr_status, memory_symbiose_submit/poll,
   memory_context_plan.

Open: restart via opencode-dev (shares ~/.config/opencode), then the
post-restart live survey. Publish stays paused until that survey is
green. Version act to 1.0.0 (operator-declared) rides with publish.
