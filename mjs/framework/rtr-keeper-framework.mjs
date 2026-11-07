// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// RTR-RE:Symbiose Keeper framework — the canonical implementation of the
// TODO-65 capabilities, shared by the JS Keeper and the mjs plugin.
// One framework at a time (ORG motto): this module is the reference;
// the self-contained keeper JS mirrors these contracts.
//
// Capabilities:
//   P1  prompt-level /rtr parser (Agile pattern)
//   P3  subagent brief (shared project-scoped brief file)
//   P5  ESM capabilities: Object.groupBy, Promise.withResolvers, Temporal
//   P6  cross mjs-js skill (one ruleset body, two hosts)
//   finding d  registry reload (env override + mtime reload)

import { readFileSync, statSync, writeFileSync } from "node:fs"
import { mkdirSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

export const FRAMEWORK_VERSION = "1.1.0"

// --- Registry (finding d) ------------------------------------------------

let REGISTRY_PATH = null
let REGISTRY_MTIME = 0

export function loadPresetRegistryFrom(path) {
    try {
        statSync(path)
    } catch {
        throw new Error(`rtr-keeper-framework: preset registry ${path} not found`)
    }
    const data = JSON.parse(readFileSync(path, "utf8"))
    if (
        data?.schema !== "rtr.preset-registry/v1" &&
        data?.schema !== "rtr.preset-registry/v2"
    ) {
        throw new Error(`rtr-keeper-framework: preset registry ${path} has an unsupported schema`)
    }
    REGISTRY_PATH = path
    REGISTRY_MTIME = statSync(path).mtimeMs
    return data
}

export function resolveRegistryPath(here) {
    const candidates = [
        process.env.OPENCODE_MEMORY_RTRRE_REGISTRY_FILE,
        join(here, "..", "execution", "rtr_presets.json"),
        join(here, "assets", "rtr_presets.json"),
        join(here, "..", "execution", "assets", "rtr_presets.json"),
    ].filter(Boolean)
    for (const path of candidates) {
        try {
            return loadPresetRegistryFrom(path)
        } catch {
            continue
        }
    }
    throw new Error(`rtr-keeper-framework: preset registry not found; looked in ${candidates.join(", ")}`)
}

// --- P1: prompt-level /rtr parser ---------------------------------------

export const PROMPT_RTR_RE =
    /^\s*\/(?:rtr|rtr-re)(?:\s+([a-z][a-z0-9_-]*))?(?:\s+([\s\S]*?))?\s*$/i

export function parseRtrPrompt(text) {
    const m = PROMPT_RTR_RE.exec(text ?? "")
    if (!m) return null
    return {
        verb: m[1] ?? "",
        args: (m[2] ?? "").trim().split(/\s+/).filter(Boolean),
    }
}

// --- P5: ESM capabilities -------------------------------------------------

export const SINK_TIMEOUT_MS = 30000

export function withTimeout(promise, ms = SINK_TIMEOUT_MS, label = "operation") {
    const { promise: out, resolve, reject } = Promise.withResolvers()
    const timer = setTimeout(
        () => reject(new Error(`${label} timed out after ${ms}ms`)),
        ms,
    )
    promise.then(
        (value) => {
            clearTimeout(timer)
            resolve(value)
        },
        (error) => {
            clearTimeout(timer)
            reject(error)
        },
    )
    return out
}

export function laneCensus(spans) {
    const byLane = Object.groupBy(spans, (s) => s.lane ?? "unknown")
    return Object.entries(byLane).map(([lane, group]) => ({
        lane,
        count: group.length,
        tokens: group.reduce((acc, s) => acc + (s.tokens ?? 0), 0),
    }))
}

export function nowIso() {
    if (typeof Temporal !== "undefined" && Temporal.Now?.instant) {
        return Temporal.Now.instant().toString()
    }
    return new Date().toISOString()
}

// --- P3: subagent brief ---------------------------------------------------

export const BRIEF_NAME = "rtr-re-keeper-brief.md"

export function briefPath(directory) {
    return join(directory, ".opencode", BRIEF_NAME)
}

export function writeSubagentBrief(directory, cfg, last) {
    const lines = [
        "# RTR-RE Keeper brief (shared, subagent-readable)",
        "",
        `profile: ${cfg.profileCode}`,
        `enabled: ${cfg.enabled}`,
        `trigger: ${cfg.triggerTokens} tokens`,
        `target: ${cfg.targetTokens} tokens (hold)`,
        `maxKeepMessages: ${cfg.maxKeepMessages}`,
    ]
    if (last) {
        lines.push(
            `last decision: ${last.decision} at ${last.time}`,
            `last window: total ~${last.total} tokens, kept ~${last.keepTokens}, evicted ${last.evicted}`,
        )
        if (last.sinkPath) lines.push(`last sink: ${last.sinkPath}`)
    }
    const text = lines.join("\n") + "\n"
    const path = briefPath(directory)
    mkdirSync(dirname(path), { recursive: true })
    writeFileSync(path, text, "utf8")
    return path
}

export default {
    FRAMEWORK_VERSION,
    PROMPT_RTR_RE,
    SINK_TIMEOUT_MS,
    briefPath,
    laneCensus,
    loadPresetRegistryFrom,
    nowIso,
    parseRtrPrompt,
    resolveRegistryPath,
    withTimeout,
    writeSubagentBrief,
}
