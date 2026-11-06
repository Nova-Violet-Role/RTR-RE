# RTR / RTR-RE two-tree catalogue (index + filesystem, no git diff)

- Generated: 2026-11-06T06:16:25+00:00 UTC
- Tool: ccc 0.2.41 (cocoindex-code), embedding Snowflake/snowflake-arctic-embed-xs, dim 384, CPU
- Method: settings.yml-mirroring walk (eligible) joined against code_chunks_vec_auxiliary (indexed); missing classified by each tree's .gitignore; git diff not used anywhere.

## RE — C:\RTR-RE

| metric | value |
|---|---|
| settings.yml bytes | 980 |
| settings.yml sha256[:16] | `fde0eb65975cb449` |
| index DB bytes | 2549227520 |
| pages / freelist | 622370 / 589541 |
| live (non-freelist) pages | 32829 |
| freelist share | 94.7% |
| eligible files (settings rules) | 193 |
| indexed distinct files | 184 |
| missing (eligible minus indexed) | 9 |
| missing gitignored | 9 |
| missing true (unexplained) | 0 |
| orphan (indexed minus eligible) | 0 |
| drift (true missing + orphan) | 0 |

Gitignored missing by top directory: [('eval', 8), ('state', 1)]

## RTR — C:\RTR

| metric | value |
|---|---|
| settings.yml bytes | 980 |
| settings.yml sha256[:16] | `fde0eb65975cb449` |
| index DB bytes | 98664448 |
| pages / freelist | 24088 / 4075 |
| live (non-freelist) pages | 20013 |
| freelist share | 16.9% |
| eligible files (settings rules) | 965 |
| indexed distinct files | 163 |
| missing (eligible minus indexed) | 802 |
| missing gitignored | 802 |
| missing true (unexplained) | 0 |
| orphan (indexed minus eligible) | 0 |
| drift (true missing + orphan) | 0 |

Gitignored missing by top directory: vendored lab predecessors 800, state 2

