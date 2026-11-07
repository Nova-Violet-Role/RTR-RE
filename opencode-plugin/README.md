# rtr-re-opencode-plugin

RTR-RE:Symbiose OpenCode plugins — the **Keeper** (server) and the
**ctrl+p palette** (TUI). Technical companion to the RTR-RE product.

## What ships here

| File | Role |
|---|---|
| `rtr-re-keeper.js` | Keeper server plugin: eviction planning, DTD-shaped memory sink, recency-aware todowrite protection, `/rtr` prompt commands, status file |
| `rtr-re-tui.tsx` | TUI plugin: eleven ctrl+p palette commands (`status`, `enable`, `disable`, `preset`, `cpu`, `modality`, `threads`, `parking`, `trigger`, `target`, `max`) |
| `assets/rtr_presets.json` | Shared preset registry (keeper presets + CPU profiles + modalities) |
| `skill/rtr-skill.md` | Cross mjs-js skill body (one ruleset, two hosts) |

## Install

```bash
npm install rtr-re-opencode-plugin
# or, from the repo:
npm pack && npm install ./rtr-re-opencode-plugin-1.1.0.tgz
```

Add the plugin to your OpenCode config (`opencode.jsonc`):

```jsonc
{
  "plugin": ["./node_modules/rtr-re-opencode-plugin/rtr-re-keeper.js"]
}
```

The TUI plugin registers under the `palette` namespace (ctrl+p).

## Keeper behavior (measured contract)

- **Eviction** keeps the newest tail up to `maxKeepMessages` and
  `targetTokens`; everything evicted is written verbatim as DTD-shaped
  spans to `<project>/.opencode/memory/` and is retrievable via
  `memory_search`.
- **Protection**: `todowrite` tool messages are never evicted below 1000
  cumulative messages; past that, only recent protected messages stay
  hard-protected (recency window = `maxKeepMessages`).
- **Config** is read from `<project>/.opencode/rtr-re-keeper.json`
  (watched, no restart). The registry is reloadable
  (`OPENCODE_MEMORY_RTRRE_REGISTRY_FILE` override).
- **Status** is written atomically to
  `<project>/.opencode/rtr-re-keeper-status.json`.

## Live control

- Plain chat: `/rtr status|hold|trigger|target|max|preset|enable|disable`
- ctrl+p palette: `rtr.*` commands write the same watched config file.

## Tests

```bash
bun test rtr-re-keeper.test.mjs
bun test rtr-re-tui.test.ts
```

## License

AGPL-3.0-or-later OR EUPL-1.2.
