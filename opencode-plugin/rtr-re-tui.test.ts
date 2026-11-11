import { describe, expect, test } from "bun:test"
import { fileURLToPath } from "node:url"
import plugin from "./rtr-re-tui.tsx"

describe("rtr-re-tui", () => {
  test("module shape: id + tui function", () => {
    expect(plugin.id).toBe("rtr-re-tui")
    expect(typeof plugin.tui).toBe("function")
  })

  test("palette registers all fourteen keeper commands", async () => {
    let layer: any = null
    const api: any = {
      state: { path: { directory: "/tmp/rtrre-tui-reg" } },
      ui: { toast: () => {}, dialog: { replace: () => {}, clear: () => {} } },
      keymap: { registerLayer: (l: any) => { layer = l } },
    }
    await plugin.tui(api)
    const names = layer.commands.map((c: any) => c.name).sort()
    expect(names).toEqual(
      [
        "rtr.cpu",
        "rtr.disable",
        "rtr.enable",
        "rtr.evict-messages",
        "rtr.evict-tokens",
        "rtr.max",
        "rtr.modality",
        "rtr.parking",
        "rtr.preset",
        "rtr.repair",
        "rtr.status",
        "rtr.target",
        "rtr.threads",
        "rtr.trigger",
      ].sort(),
    )
    for (const c of layer.commands) {
      expect(c.namespace).toBe("palette")
      expect(c.category).toBe("RTR Keeper")
    }
  })

  test("enable and disable write the watched config file", async () => {
    const os = require("node:os")
    const fs = require("node:fs")
    const path = require("node:path")
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "rtrre-tui-"))
    const toasts: any[] = []
    let layer: any = null
    const api: any = {
      state: { path: { directory: dir } },
      ui: {
        toast: (t: any) => toasts.push(t),
        dialog: { replace: () => {}, clear: () => {} },
      },
      keymap: { registerLayer: (l: any) => { layer = l } },
    }
    await plugin.tui(api)
    const byName = Object.fromEntries(layer.commands.map((c: any) => [c.name, c]))
    await byName["rtr.disable"].run()
    let cfg = JSON.parse(
      fs.readFileSync(path.join(dir, ".opencode", "rtr-re-keeper.json"), "utf8"),
    )
    expect(cfg.enabled).toBe(false)
    await byName["rtr.enable"].run()
    cfg = JSON.parse(
      fs.readFileSync(path.join(dir, ".opencode", "rtr-re-keeper.json"), "utf8"),
    )
    expect(cfg.enabled).toBe(true)
    expect(toasts.length).toBe(2)
    fs.rmSync(dir, { recursive: true, force: true })
  })

  test("preset registry loads and exposes keeper knobs", () => {
    // Importing the module already ran loadPresetRegistry(); it must
    // expose the keeper presets asserted below.
    const fs = require("node:fs")
    const path = require("node:path")
    const here = path.dirname(fileURLToPath(import.meta.url))
    const candidates = [
      path.join(here, "..", "execution", "assets", "rtr_presets.json"),
      path.join(here, "assets", "rtr_presets.json"),
      path.join(here, "..", "execution", "rtr_presets.json"),
    ]
    const found = candidates.find((p) => fs.existsSync(p))
    expect(found).toBeDefined()
    const data = JSON.parse(fs.readFileSync(found, "utf8"))
    expect(data.defaultKeeperPreset).toBe("re-symbiose-mugen")
    expect(data.futureDefaultKeeperPreset).toBe("re-symbiose-mugen")
    expect(data.keeperPresets["fusion-ah"].maxKeepMessages).toBe(30)
    expect(data.keeperPresets["symbiose-ah"].maxKeepMessages).toBe(40)
    expect(data.keeperPresets["re-symbiose"].maxKeepMessages).toBe(50)
    expect(data.keeperPresets["re-symbiose-mugen"].triggerTokens).toBe(400000)
    expect(data.keeperPresets["re-symbiose-mugen"].targetTokens).toBe(200000)
    expect(data.keeperPresets["re-symbiose-mugen"].maxKeepMessages).toBe(200)
  })
})
