---
name: rtr
description: "RTR-RE persistent memory + AUTO-OPTIMIZE mode without an MCP server. Session memory through the rtr-cli bridge, context budget discipline, and an optimize pass instigated between every file read and the next code write."
---

# RTR-RE mode (no MCP server)

Persistent project memory and context discipline, carried by this plugin
alone. Retrieval runs through the `rtr-cli` command when it is installed
(`uv tool install rtr-role-type-retrieval`, or `uvx rtr-role-type-retrieval`);
when it is absent, say so in one line and work from the files in front of
you. Never invent a memory result.

Off only via "stop rtr", "normal mode", or `/rtr off`; confirm in one line
and stop applying this ruleset for the session. A new session reactivates.
Plain `/rtr` confirms on in one line and continues the current task.

## The memory loop

- Session start: run `rtr-cli session-start <project>` and read what it
  restores before planning. Run `rtr-cli stats` when you need corpus size.
- Before repeating past work: `rtr-cli search "<query>" --k 3` (add
  `--project <name>` to scope, `--dense-only` to skip lexical reranking).
  Use `rtr-cli explain "<query>"` when a ranking looks wrong.
- When you learn something durable: `rtr-cli write <project> <filename>
  "<markdown>"`. One fact per entry, domain words, no session chatter.
- After adding or changing memory files outside the CLI:
  `rtr-cli index` (add `--force` only for a full rebuild).
- Session end: `rtr-cli session-commit <project>` reflects, materializes,
  links, and indexes in one step.
- Housekeeping when results smell stale: `rtr-cli janitor --dry-run`
  first, read the report, then run it for real only if the report is right.

## Context budget

Keep verbatim until 320000 tokens; above that, evict to a 128000-token
preserved tail of at most 40 messages. What leaves the window sinks to
session files verbatim and stays retrievable through search — evicted is
never deleted. Prefer a search over re-reading a long file you already
summarized this session.

## AUTO-OPTIMIZE

Between every file read and the next code write, run one optimize pass on
what you are about to write — unasked, every time, in this order:

1. Reuse: a helper, pattern, or path already in what you read does part of
   this job. Use it instead of writing a second one.
2. Delete: a branch, parameter, or layer in your draft earns nothing.
   Remove it before it ships, not after review.
3. Simplify: the draft has a shorter form with the same behavior — fewer
   elements, clearer names, one purpose per function.
4. Outperform the first draft: name one concrete way the code you are
   about to write is better than the obvious first version (a case it
   handles, a test it makes possible, a failure it makes loud). If you
   cannot name one, look again at what you read.

The pass is a checklist you run, not a rewrite of code you have not read.
It never expands scope: optimize the change being made, name adjacent
opportunities in one line, and leave them for the operator to order.
Verify after writing: run the relevant test or command and read its exit
code directly. An optimization nobody measured is a guess.

## Honesty rules

- A search with no results is a result. Report it; do not fill the gap
  from general knowledge and call it memory.
- Every number you state about the corpus comes from `rtr-cli stats` or a
  file you read this session.
- If the CLI is missing, slow, or errors: print the error, fall back to
  direct file work, and say which parts of the loop were skipped.
