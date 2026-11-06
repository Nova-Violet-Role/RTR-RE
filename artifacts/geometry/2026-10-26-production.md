<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# Production: RTR-RE:Rolling figure

- survey: artifacts/geometry/2026-10-26-survey.md (2026-10-26)
- plan: artifacts/geometry/2026-10-26-plan.md (2026-10-26)
- renovation: artifacts/geometry/2026-10-26-renovation.md (2026-10-26)
- target: C:\RTR

## Produced (bytes read back after write)

- produced 73 cabinet cells artifacts/geometry/2026-10-26-production.cells.txt 415 bytes
- produced 73 cabinet svg artifacts/geometry/2026-10-26-production.svg 1041 bytes
- produced 105 vectorisation png artifacts/geometry/2026-10-26-production.png 7234 bytes (via resvg)

## Rungs used

- 53 chord (surveyor lens): straight keep/evict cut between two measured points, TRIGGER and TARGET.
- 70 foreshortening (architect lens): verbatim length shortened 200k -> 100k by the 50% factor.
- 73 cabinet (architect lens): front face true (verbatim tail), depth halved (evicted to index).
- 81-83 hue/value/chroma (surveyor lens): layers distinguished without hex values in cells.
- 95 consolidation, 105 vectorisation, 106 restructure, 107 specification, 108 documentation (renovator lens): caps, png raster, wiring, records.

## Domains unused

- trigonometry remainder (54-66 except 53): no angle was measured; the cut is linear, naming more would be decoration.
- projection remainder (67-72, 74-80 except 70/73): one plate, no multiview or exploded view was produced.
- chromatics remainder (84-94): cells carry no colour; tint/shade/glaze would claim paint the poorest renderer cannot honour.
- restoration remainder (96-104 except 95): no loss was inpainted; substance is preserved, not reconstructed.

Figure: see cells file; plate svg + png beside this record. Mark: measured.
Next band: 1 planimetry — run /codebase-surveyor-dtd on what was produced (after OpenCode restart, with live ACP).
