<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Pre-Publication Closure Catalogue — RTR-RE 1.2.0

Date: 2026-11-11. Second edition of the 1.0.0 closure catalogue: every
open rung of the release ladder, its closure evidence, the operator
trigger, and the rollback plan. Nothing uploads without the operator's
explicit order; this document is preparation, not publication.

## Published state (measured 2026-11-11)

| Platform | Latest | 1.2.0 present |
|---|---|---|
| PyPI `rtr-role-type-retrieval` | 1.1.0 (2026-11-08) | no |
| npm `rtr-re-opencode-plugin` | 1.1.0 | no |
| npm `@saimonokuma/rtr-re-mjs` | 1.1.0 | no |
| GitHub tags | v1.1.0 only | no tag yet |

## This release, rebuilt fresh (dist/, gitignored scratch)

| File | Bytes | sha256 |
|---|---|---|
| rtr_role_type_retrieval-1.2.0-py3-none-any.whl | 16968617 | 9b2421e9f6b912b401a8ccdbed45f154f3d60ea1937278b97faa3648dc19e659 |
| rtr_role_type_retrieval-1.2.0.tar.gz | 19348651 | d19ca2f6fcf46045e0c80f1c0445369e361acb6a4018a2523a53e7475bbadef5 |
| rtr-re-opencode-plugin-1.2.0.tgz | 16841934 | 2a110cf8dbd4412f57f2ae449a2b6adb826d00abe9dfe0cf6018241928e93a66 |
| saimonokuma-rtr-re-mjs-1.2.0.tgz | 12775 | 89ecc5797fa2ed5e0d634f8dee83c1120d3b72a5e77948ade547dee4de4a84aa |

Stale 1.1.0 local blobs were recorded (plugin tgz cf067874…,
wheel 442572f7…, sdist 76a36042…, mjs e0b07174…) and removed; the
1.1.0 release lives on the three platforms, which is the rollback
source, not this directory.

Sdist composition note (measured, accepted): 19.3 MB vs 1.1.0's
2.1 MB — the growth is frozen evidence (seven versus snapshots,
catalogue, pool worksheet) plus the shipped installer audio. The
wheel installers actually download is unchanged in size class
(17.0 MB vs 1.1.0's 16.95 MB). Revisit if a slim sdist is wanted
(hatch exclude rules); not a blocker.

## Evidence (all measured this ladder)

| Battery | Result |
|---|---|
| pytest | 519 passed, 1 skipped, 33 subtests, exit 0 |
| node keeper / bulletproof / launcher / bin | 59 / 9 / 16 / 3, exit 0 |
| mjs suite | 38, exit 0 |
| bun TUI | 4, exit 0 |
| keeper behavior gate | PASS 8/8 |
| Lean battery | exit 0, 0 sorry, axioms standard-or-recorded |
| Engine Beneath | 27/27 VERDICT True (rmtree race fixed, retry-cleanup) |
| versus --intense | 898 queries, 0 errors, rtr-full 0.7227/0.8497/0.7769 |
| graded v2 | identical re-run (0.8094/0.7944); v3 verdict holds |
| transfer / calibrate / probes / preset-perf | re-ran fresh |
| regression gate | PASS (5 corpora, 35 systems, 11 taxons) |
| parity gate | PASS incl. license:clean |
| verify_release | PASS 40 checks, 0 failures |
| wheel preflight | paths + entry points + version 1.2.0 PASS |
| public paths | uvx help lists 21 verbs; npm names resolve at 1.1.0 |

## Operator blockers (cannot be cleared here)

1. MP3 clearance: the shipped installer audio remixes a commercial
   track (See-Saw / Kajiura, attributed in audio.js). Publish needs
   the operator's answer: confirm, replace, or drop.
2. Upstream note: the retrieval core derives in part from
   github.com/xpajonx/opencode-memory, which ships no licence file
   (NOTICE + README-PYPI carry the caveat).

## Trigger (operator runs, in order)

1. Answer the two blockers above.
2. Undraft `.github/workflows/publish.yml` (remove the Draft header;
   the workflow is otherwise preflighted).
3. `git tag v1.2.0` and push the tag (or workflow_dispatch with
   version 1.2.0). The workflow builds fresh, verifies four
   artifacts, publishes PyPI then npm (each skips if already
   published), then creates the GitHub release with assets.
4. Read back each stage: PyPI JSON shows 1.2.0, `npm view` shows
   1.2.0 on both packages, the GitHub release carries four assets.

## Rollback

- Before any upload: nothing to roll back; delete the tag.
- After PyPI: yank 1.2.0, publish 1.2.1; users reinstall 1.1.0
  (`uvx --from rtr-role-type-retrieval==1.1.0`, `uv tool install
  rtr-role-type-retrieval==1.1.0`).
- After npm: deprecate 1.2.0 on both packages, publish 1.2.1;
  users reinstall 1.1.0.
- After GitHub: delete the release and the tag, re-cut.
- Local live system: keeper file + opencode.jsonc backups restore
  the old world; the engine reinstalls from the sealed 1.1.0
  published wheel (never `uv tool upgrade` over a running server).

## Conclusion

Open items: the two blockers above plus the operator trigger.
Everything else on the ladder is closed with evidence. The gate
therefore holds at READY-BLOCKED: ready on evidence, blocked on
the operator's two answers and trigger.

## Published 2026-11-11 (post-scriptum)

One tag push (`v1.2.0`), one workflow run, all five jobs green.
Read-backs, not trust:

| Platform | Artifact | Proof |
|---|---|---|
| PyPI | wheel 16,968,617 B sha256 db19442f…9848a; sdist 19,338,291 B sha256 d3a7aa41…f0bda | version JSON 1.2.0 live, new manual on page |
| npm `rtr-re-opencode-plugin` | 1.2.0, shasum cd3ef589…, 31 files | `npm view` 1.2.0 (shasum equals local pack: reproducible) |
| npm `@saimonokuma/rtr-re-mjs` | 1.2.0, shasum 862c92a3…, 14 files | `npm view` 1.2.0 (shasum equals local pack: reproducible) |
| GitHub | release v1.2.0 + 4 assets | release read-back lists all four |

CI note: the first post-push run went 3/4 green with 11
environmental python failures (lab-data tests, frames/prepack
artifacts, one real cross-platform `family_of` bug); all fixed
red-first, CI re-ran green before the tag. No duplicates: each
stage published exactly once (a transient 404 scare was the local
npm cache, disproven with `--prefer-online`).
