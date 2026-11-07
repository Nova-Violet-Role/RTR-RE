import { describe, expect, test } from "bun:test"
import { fileURLToPath } from "node:url"
import plugin from "./rtr-re-tui.tsx"

describe("rtr-re-tui", () => {
  test("module shape: id + tui function", () => {
    expect(plugin.id).toBe("rtr-re-tui")
    expect(typeof plugin.tui).toBe("function")
  })

  test("preset registry loads and exposes keeper knobs", () => {
    // Importing the module already ran loadPresetRegistry(); the registry
    // must be the 1.0.0 one with the three AH presets.
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
