<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# Study: ccc grep vs rg as a structural lane backend for RE:Symbiose

Date: 2026-10-27. Instruments: ccc 0.2.41 (`ccc grep`, no index) and
ripgrep 15.2.0, run foreground on identical targets in `C:\RTR`, exit codes
and wall times read directly from completed process records. Question
(TODO-15): can structural grep be absorbed into the RTR architecture as a
typed lane, and which backend should carry it? Complete replacement of
`_fused_multi` was already measured not makable (prose-blind, scoreless);
this study decides the lane backend.

## Measured comparisons

| # | Target | rg | ccc grep |
|---|---|---|---|
| A | Exact symbol `hybrid_lane_weights` in `execution/` | exit 0, 37 ms, 4 lines incl. comment `memory_engine.py:1367` | exit 0, 225 ms, 3 code occurrences (comment excluded) |
| B | All definitions in `execution/` | regex `def [A-Za-z_]+[(]`: exit 0, 38 ms, 272 lines | pattern `def \NAME(\(ARGS*\)):`: exit 0, 231 ms, 290 output lines (includes multi-line signatures a line regex must approximate) |
| C | Comment/docstring word `standout` in `execution/` | 7 lines: docstrings, comments, and test names containing the substring | `No matches found` — bare word is not a code shape; no substring matching |
| D | Prose: `Symbiose` in `directives/` (markdown) | finds `context-management.md:2`, `rtr-re-symbiose.md:2,4` | `No matches found` — markdown is not a supported source file |
| E | Machine output | `--json` event stream (`{"type":"begin",...}` verified) | no JSON flag (`ccc grep --help`: only `--lang`, `--path`, `--no-color`); human text with `---` separators |
| F | No-match contract | exit 1, empty stdout | exit 0, stdout `No matches found.` — caller must parse text to detect emptiness |
| G | Whole repo `MemoryEngine` | exit 0, 51 ms, 33 lines (gitignore-aware) | exit 0, 280 ms, 72 output lines |
| H | Call with any args | regex finds definition + both call sites, incl. attribute call `memory_engine.hybrid_lane_weights(scores)` | `hybrid_lane_weights(\(ARGS*\))` finds definition line and bare call, **misses the attribute-qualified call** unless the pattern names the qualifier |

## What each instrument is, in lane terms

- **rg** is a text instrument: line regex over every file type, comments
  and strings included (rows A, C), substring by default, JSON events and
  a scriptable exit-code contract (E, F), 5–6× faster on these trees
  (A, B, G). Its false positives are exactly the comment/string hits.
- **ccc grep** is a code-shape instrument: the pattern is compiled per
  language and matched structurally — comments excluded (A), metavariables
  span argument lists and multi-line shapes (B, H). Its costs: the pattern
  must be a valid code shape (C), qualification must be spelled out (H),
  prose corpora are invisible (D), and the CLI offers no machine contract
  (E, F). Per-call filesystem scan measured 225–280 ms here.

Neither ranks. Both return locations; any lane built on them must convert
locations into bounded fusion evidence itself.

## Design consequences for the STRUCT lane (TODO-15)

1. **Backend interface, two optional backends.** Define one internal
   interface `structural_hits(terms, roots) -> [{source, line}]`.
   The rg backend (`--json`, word-boundary identifier search) is the
   integratable default: machine output, exit codes, every file type.
   The ccc backend is used only when the query itself already carries a
   structural shape (metavariables or an explicit call pattern), where its
   precision is the point. Choosing per query shape is the custom routing;
   neither backend is a hard dependency — absence means the lane is off.
2. **Scope the scan to candidates, not the tree.** `_fused_multi` already
   holds the dense-retrieved candidate sources; the lane should search
   those source paths (rg accepts many paths in one call) instead of
   rescanning a whole project per query. This bounds the cost and keeps
   the lane an exactness check over retrieved evidence, in the same
   position as the current substring CDATA lane it would replace for
   code-shaped terms.
3. **Lean contract stays backend-agnostic.** `formal/Symbiose/Lane.lean`
   (to be written under TODO-15) pins what the study cannot: term
   classification total and disjoint across lanes (no double voting — the
   collision constraint), bounded influence
   (`final <= dense_final + EXACT_LANE_WEIGHT`), and fallback identity when
   no backend is available. The Python lane is then one realization of a
   proved contract, whichever backend answers.
4. **Comment/string false positives are the rg lane's known tax** (row A:
   1 of 4 hits). Mitigation without ccc: restrict the rg lane to
   word-boundary identifier patterns and let the bounded bonus cap the
   damage; a comment mention can add at most the exact-lane weight, never
   bury a dense winner — the same bound the Lean contract states.

## Verdict

Absorb as a typed optional lane: **yes, makable**, with rg --json as the
default backend and ccc as the precision backend for explicitly structural
queries. Replace `_fused_multi`: **no** — rows C and D are the graded
bench's home ground (natural-language intents over prose), where both
instruments are silent and only dense/BM25 evidence exists. The lane lands
default-off behind an env flag, so every frozen number stays reproducible;
TODO-15 carries the Lean-first implementation steps and their red tests.
