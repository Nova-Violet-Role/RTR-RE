// RTR-RE:Symbiose — TUI plugin: live keeper knobs in the ctrl+p palette.
// Registers commands under namespace "palette" (category "RTR Keeper") that
// write <project>/.opencode/rtr-re-keeper.json — the same watched file the
// keeper plugin reloads on mtime change, so every change applies on the next
// exchange with no restart.
// Requires solid-js resolvable from this file (JSX import source).
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// SPDX-FileCopyrightText: Nova-Violet Role ORG
// @jsxImportSource solid-js/h

import { readFile, writeFile, mkdir } from "node:fs/promises"
import { readFileSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const KEEPER_CONFIG_NAME = "rtr-re-keeper.json"
const KEEPER_STATUS_NAME = "rtr-re-keeper-status.json"
const CATEGORY = "RTR Keeper"

function loadPresetRegistry() {
  const here = dirname(fileURLToPath(import.meta.url))
  const candidates = [
    join(here, "..", "execution", "assets", "rtr_presets.json"),
    join(here, "assets", "rtr_presets.json"),
    join(here, "..", "execution", "rtr_presets.json"),
  ]
  for (const path of candidates) {
    try {
      const data = JSON.parse(readFileSync(path, "utf8"))
      const schema = data?.schema
      if (schema !== "rtr.preset-registry/v1" && schema !== "rtr.preset-registry/v2") {
        throw new Error("unsupported schema")
      }
      return data
    } catch {
      // try next candidate
    }
  }
  throw new Error("rtr-re-tui: preset registry not found")
}

const REGISTRY = loadPresetRegistry()
const PRESETS = REGISTRY.keeperPresets
const CPU_PROFILES = REGISTRY.cpuProfiles
const MODALITIES = REGISTRY.modalities
const THREAD_MODES = REGISTRY.threadModes.map(Number)
const PARKING_PERCENTS = REGISTRY.parkingPercents.map(Number)

function optionList(map) {
  return Object.entries(map).map(([value, p]) => ({
    value,
    title: p.displayName ?? value,
    description: p.description ?? undefined,
  }))
}

function positiveInt(raw, name) {
  const n = Number(String(raw).trim())
  if (!Number.isInteger(n) || n <= 0) {
    throw new Error(`${name} must be a positive integer, got ${raw}`)
  }
  return n
}

function allowedInt(raw, allowed, name) {
  const n = Number(String(raw).trim())
  if (!Number.isInteger(n) || !allowed.includes(n)) {
    throw new Error(`${name} must be one of ${allowed.join(", ")}, got ${raw}`)
  }
  return n
}

async function readKeeperConfig(directory) {
  const path = join(directory, ".opencode", KEEPER_CONFIG_NAME)
  try {
    return JSON.parse(await readFile(path, "utf8"))
  } catch {
    return {}
  }
}

async function writeKeeperConfig(directory, values, label) {
  const dir = join(directory, ".opencode")
  await mkdir(dir, { recursive: true })
  const path = join(dir, KEEPER_CONFIG_NAME)
  const current = await readKeeperConfig(directory)
  const merged = { ...current, ...values }
  if (
    typeof merged.targetTokens === "number" &&
    typeof merged.triggerTokens === "number" &&
    merged.targetTokens >= merged.triggerTokens
  ) {
    throw new Error("target must stay below trigger")
  }
  await writeFile(path, JSON.stringify(merged, null, 2) + "\n", "utf8")
}

async function readKeeperStatus(directory) {
  const path = join(directory, ".opencode", KEEPER_STATUS_NAME)
  try {
    return JSON.parse(await readFile(path, "utf8"))
  } catch {
    return null
  }
}

function formatStatus(cfg, status) {
  const lines = [
    "RTR-RE Keeper status (native, live):",
    `enabled: ${cfg.enabled}`,
    `preset: ${cfg.preset ?? "?"} (${cfg.presetDisplay ?? ""})`,
    `trigger: ${cfg.triggerTokens} tokens`,
    `target: ${cfg.targetTokens} tokens (hold)`,
    `maxKeepMessages: ${cfg.maxKeepMessages}`,
    `cpu profile: ${cfg.cpuProfile ?? "?"} (${cfg.cpuProfileDisplay ?? ""})`,
    `modality: ${cfg.modality ?? "?"} (${cfg.modalityDisplay ?? ""})`,
    `threads: T${cfg.threadsPerModel} selected, ${cfg.effectiveThreadsPerModel} effective per model`,
    `parking: P${cfg.parkingPercent} (${cfg.plannedThreadsPerEngine ?? "?"} planned of ${cfg.parkingBudgetThreads ?? "?"} budgeted)`,
  ]
  if (status) {
    lines.push(`last decision: ${status.decision} at ${status.time}`)
    if (status.total) lines.push(`last window: total ~${status.total} tokens, kept ~${status.keepTokens}, evicted ${status.evicted}`)
    if (status.error) lines.push(`last error: ${status.error}`)
  } else {
    lines.push("no status file yet this project")
  }
  return lines.join("\n")
}

const plugin = {
  id: "rtr-re-tui",
  tui: async (api) => {
    const directory = () => api.state.path.directory || process.cwd()

    const apply = async (values, label) => {
      try {
        await writeKeeperConfig(directory(), values, label)
        api.ui.toast({
          variant: "success",
          title: "RTR Keeper",
          message: `${label} set; applies on the next exchange (no restart)`,
        })
      } catch (error) {
        api.ui.toast({
          variant: "error",
          title: "RTR Keeper",
          message: String(error?.message ?? error),
        })
      }
    }

    const confirmNumber = (title, placeholder, current, onValue) => {
      api.ui.dialog.replace(() => (
        <api.ui.DialogPrompt
          title={title}
          placeholder={placeholder}
          value={current ? String(current) : ""}
          onConfirm={(raw) => {
            api.ui.dialog.clear()
            try {
              onValue(positiveInt(raw, title))
            } catch (error) {
              api.ui.toast({ variant: "error", title, message: String(error?.message ?? error) })
            }
          }}
          onCancel={() => api.ui.dialog.clear()}
        />
      ))
    }

    const selectOption = (title, options, current, onPick) => {
      api.ui.dialog.replace(() => (
        <api.ui.DialogSelect
          title={title}
          options={options}
          current={current}
          onSelect={(item) => {
            api.ui.dialog.clear()
            onPick(item.value)
          }}
          onCancel={() => api.ui.dialog.clear()}
        />
      ))
    }

    api.keymap.registerLayer({
      commands: [
        {
          name: "rtr.status",
          title: "RTR Keeper: status",
          category: CATEGORY,
          desc: "Show live bounds, preset and last decision",
          namespace: "palette",
          run: async () => {
            const cfg = await readKeeperConfig(directory())
            const status = await readKeeperStatus(directory())
            const message = formatStatus(cfg, status)
            api.ui.dialog.replace(() => (
              <api.ui.DialogAlert
                title="RTR Keeper status"
                message={message}
                onConfirm={() => api.ui.dialog.clear()}
              />
            ))
          },
        },
        {
          name: "rtr.enable",
          title: "RTR Keeper: enable",
          category: CATEGORY,
          desc: "Turn pruning on",
          namespace: "palette",
          run: () => apply({ enabled: true }, "keeper enabled"),
        },
        {
          name: "rtr.disable",
          title: "RTR Keeper: disable",
          category: CATEGORY,
          desc: "Turn pruning off (identity transform)",
          namespace: "palette",
          run: () => apply({ enabled: false }, "keeper disabled"),
        },
        {
          name: "rtr.preset",
          title: "RTR Keeper: preset…",
          category: CATEGORY,
          desc: "Pick a preset (bounds + profile)",
          namespace: "palette",
          run: async () => {
            const cfg = await readKeeperConfig(directory())
            selectOption("RTR Keeper preset", optionList(PRESETS), cfg.preset, (value) => {
              const preset = PRESETS[value]
              apply({ preset: value, ...preset }, `preset ${value}`)
            })
          },
        },
        {
          name: "rtr.cpu",
          title: "RTR Keeper: CPU profile…",
          category: CATEGORY,
          desc: "Pick a CPU profile (modality, threads, parking)",
          namespace: "palette",
          run: async () => {
            const cfg = await readKeeperConfig(directory())
            selectOption("RTR Keeper CPU profile", optionList(CPU_PROFILES), cfg.cpuProfile, (value) => {
              const profile = CPU_PROFILES[value]
              apply(
                { cpuProfile: value, modality: profile.modality, threadsPerModel: profile.threadsPerModel, parkingPercent: profile.parkingPercent },
                `CPU profile ${value}`,
              )
            })
          },
        },
        {
          name: "rtr.modality",
          title: "RTR Keeper: modality…",
          category: CATEGORY,
          desc: "Pick the retrieval modality",
          namespace: "palette",
          run: async () => {
            const cfg = await readKeeperConfig(directory())
            selectOption("RTR Keeper modality", optionList(MODALITIES), cfg.modality, (value) => {
              apply({ modality: value }, `modality ${value}`)
            })
          },
        },
        {
          name: "rtr.threads",
          title: "RTR Keeper: threads…",
          category: CATEGORY,
          desc: "Pick threads per model",
          namespace: "palette",
          run: async () => {
            const cfg = await readKeeperConfig(directory())
            const options = THREAD_MODES.map((n) => ({ value: String(n), title: `T${n}` }))
            selectOption("RTR Keeper threads per model", options, cfg.threadsPerModel != null ? String(cfg.threadsPerModel) : undefined, (value) => {
              try {
                apply({ threadsPerModel: allowedInt(value, THREAD_MODES, "threads") }, `threads T${value}`)
              } catch (error) {
                api.ui.toast({ variant: "error", title: "RTR Keeper", message: String(error?.message ?? error) })
              }
            })
          },
        },
        {
          name: "rtr.parking",
          title: "RTR Keeper: parking…",
          category: CATEGORY,
          desc: "Pick the CPU parking percent",
          namespace: "palette",
          run: async () => {
            const cfg = await readKeeperConfig(directory())
            const options = PARKING_PERCENTS.map((n) => ({ value: String(n), title: `P${n}` }))
            selectOption("RTR Keeper parking percent", options, cfg.parkingPercent != null ? String(cfg.parkingPercent) : undefined, (value) => {
              try {
                apply({ parkingPercent: allowedInt(value, PARKING_PERCENTS, "parking") }, `parking P${value}`)
              } catch (error) {
                api.ui.toast({ variant: "error", title: "RTR Keeper", message: String(error?.message ?? error) })
              }
            })
          },
        },
        {
          name: "rtr.trigger",
          title: "RTR Keeper: trigger…",
          category: CATEGORY,
          desc: "Set the trigger tokens (eviction starts here)",
          namespace: "palette",
          run: async () => {
            const cfg = await readKeeperConfig(directory())
            confirmNumber("RTR Keeper trigger tokens", "e.g. 250000", cfg.triggerTokens, (n) => apply({ triggerTokens: n }, `trigger ${n}`))
          },
        },
        {
          name: "rtr.target",
          title: "RTR Keeper: target…",
          category: CATEGORY,
          desc: "Set the target tokens (preserved tail)",
          namespace: "palette",
          run: async () => {
            const cfg = await readKeeperConfig(directory())
            confirmNumber("RTR Keeper target tokens", "e.g. 100000", cfg.targetTokens, (n) => apply({ targetTokens: n }, `target ${n}`))
          },
        },
        {
          name: "rtr.max",
          title: "RTR Keeper: max messages…",
          category: CATEGORY,
          desc: "Set the max verbatim messages kept",
          namespace: "palette",
          run: async () => {
            const cfg = await readKeeperConfig(directory())
            confirmNumber("RTR Keeper max messages", "e.g. 200", cfg.maxKeepMessages, (n) => apply({ maxKeepMessages: n }, `max ${n}`))
          },
        },
      ],
      bindings: [],
    })
  },
}

export default plugin
