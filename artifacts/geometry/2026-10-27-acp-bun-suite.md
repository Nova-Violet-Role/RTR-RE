<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# ACP vendored suite: full run and keeper-only disposition (TODO-8)

Date: 2026-10-27. Instrument: `npm test` in `C:\RTR\opencode-acp`
(`node --import tsx --test tests/*.test.ts`, upstream pin 98a16d5b per
VENDORED.md), foreground, stdin closed, exit read directly.

## Result

First full run: 1390 tests · 1387 pass · 3 fail · 35 s wall · exit 1.
The 3 failing files rerun 3x in isolation: identical 31 pass / 3 fail
every time (204–246 ms) — stable failures, not flakes. The earlier
sample's preserve-recent timeouts (8.9 s / 12.5 s vs 5 s) did **not**
recur in the full run; slowest observed test was
`lastSegmentSoftBlock disabled bypasses protection` at 1234 ms. The
documented upstream baseline (134 passing, 3 known failures in
`config-validation.test.ts`) is stale relative to this pin.

Operator correction (2026-10-27): classifying those failures without
fixing them was not an acceptable closure for a pitch-perfect publish.
The three tests were therefore made platform-correct (test-only changes,
recorded in VENDORED.md), the subset rerun went 34/34, and the full
suite rerun is **1390/1390 pass · 0 fail · exit 0 · 29 s**. The table
below remains the root-cause record for why each test was wrong on
Windows; no product code was changed.

## The three failures: POSIX test assumptions on Windows

| Test | Assertion | Root cause | Keeper impact |
|---|---|---|---|
| `storage-path.test.ts:132` resolveStorageDir relative paths | expected `/some/project/data/acp`, got `\some\project\data\acp` | Test hardcodes POSIX separators; `path.resolve` is OS-correct | None. No `storagePath` key in our acp.jsonc; default resolution used. |
| `inactive-block-decompress.test.ts:206` toFile on inactive block | refuses `/tmp/test-...txt`: "must be under %TEMP% or ~/.cache/opencode/" | Test hardcodes `/tmp`; the product path guard works as designed on Windows | None. Decompress commands are outside the keeper-only posture (`permission: deny`); the guard itself is correct behaviour. |
| `image-archive.test.ts:115` spills large inline images | `mode & 0o777` expected 384 (0o600), got 438 (0o666) | POSIX mode bits do not map to Windows Node stat modes | None for windowing. Recorded divergence: on Windows, archived image files inherit the storage directory ACL instead of 0600 mode bits. |

All three were upstream test-platform defects, not product defects. The
tests now express the platform-correct contract (`join()`-built expected
paths, `tmpdir()` instead of a literal `/tmp`, POSIX mode asserted only
where POSIX modes exist), so the suite is a usable Windows gate instead
of a permanently red one. The divergence from the pin is test-only and
recorded in VENDORED.md; an upstream re-pin should drop these hunks if
upstream lands equivalents.

## Keeper-contract coverage inside the passing 1387

The behaviours the keeper-only posture depends on are covered green:
`message-priority` (prune, protected handling), `host-permissions`
(`compressDisabledByOpencode`, `resolveEffectiveCompressPermission`),
`hooks-permission` (permission enforcement in the transform pipeline),
`token-usage` / `input-budget` (context limit maths behind
max/minContextLimit), `registry`/`message-ids` (session state). Upstream
suites for compress modes also pass, unused here under `permission: deny`
(dummy T7 measured zero ACP tools in that posture).

## Disposition

Vendored suite: green on Windows (1390/1390). That closes the *test*
question, not the architecture question. The published RE:Symbiose tree
does not ship this vendored folder at all: the Keeper office is being
replaced by a first-party plugin in the standalone tree (TODO-16), and
this suite remains the lab reference for what the old external Keeper
did. Closing TODO-8 on the original classification alone would have
been the skip the operator forbade; it closes on a green suite instead.
