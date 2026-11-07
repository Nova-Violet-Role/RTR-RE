// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// RTR-RE:Symbiose native Keeper for OpenCode — first-party, self-contained.
// No dependencies.
//
// Office: Keeper only. On every request it estimates the visible window;
// above TRIGGER it keeps a bounded verbatim tail (TARGET), sinks the
// evicted spans verbatim (NDATA masked) to directives/sessions/ for the
// RTR memory MCP index, and only then rewrites the outgoing message
// list. If the sink fails, nothing is evicted (fail-open): substance is
// never lost to a failed write. The Compressor planner
// (execution/context_budget.py) owns the same bounds in Python; this
// plugin mirrors its keep rules for the host window: newest-first tail,
// tool-pair fixpoint, protected tools and last user message always kept.
//
// Live control (no restart): bounds/enabled/maxKeep come from plugin
// options > project config file (.opencode/rtr-re-keeper.json, reloaded
// when its mtime changes) > env > defaults. The `/rtr` command family
// (status, hold, trigger, target, max, preset, enable, disable) writes
// that file, so the next exchange already runs the new bounds. Every
// transform writes a status file the MCP viewport reads.

import { createHash } from "node:crypto"
import { mkdir, writeFile, stat, readFile, rename } from "node:fs/promises"
import { availableParallelism } from "node:os"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"
import { readFileSync, statSync } from "node:fs"

const KEEPER_VERSION = "1.1.0"

function loadPresetRegistryFrom(path) {
    try {
        statSync(path)
    } catch {
        throw new Error(`rtr-re-keeper: preset registry ${path} not found`)
    }
    const data = JSON.parse(readFileSync(path, "utf8"))
    if (
        data?.schema !== "rtr.preset-registry/v1" &&
        data?.schema !== "rtr.preset-registry/v2"
    ) {
        throw new Error(`rtr-re-keeper: preset registry ${path} has an unsupported schema`)
    }
    REGISTRY_PATH = path
    REGISTRY_MTIME = statSync(path).mtimeMs
    return data
}

function loadPresetRegistry() {
    const here = dirname(fileURLToPath(import.meta.url))
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
    throw new Error(`rtr-re-keeper: preset registry not found; looked in ${candidates.join(", ")}`)
}

let REGISTRY_PATH = null
let REGISTRY_MTIME = 0

let PRESET_REGISTRY = loadPresetRegistry()
let DEFAULT_PRESET = PRESET_REGISTRY.defaultKeeperPreset
let DEFAULT_PRESET_VALUES = PRESET_REGISTRY.keeperPresets[DEFAULT_PRESET]
let DEFAULT_CPU_PROFILE_NAME = PRESET_REGISTRY.defaultCpuProfile
let DEFAULT_CPU_PROFILE = PRESET_REGISTRY.cpuProfiles[DEFAULT_CPU_PROFILE_NAME]
let DEFAULT_TRIGGER_TOKENS = DEFAULT_PRESET_VALUES.triggerTokens
let DEFAULT_TARGET_TOKENS = DEFAULT_PRESET_VALUES.targetTokens
let DEFAULT_MAX_KEEP_MESSAGES = DEFAULT_PRESET_VALUES.maxKeepMessages
const PROTECTED_TOOLS = new Set(["todowrite"])
const NDATA_RE = /[A-Za-z0-9+/]{64,}={0,2}/
const NDATA_RE_G = /[A-Za-z0-9+/]{64,}={0,2}/g
const CDATA_RE =
    /```|`[^`\n]+`|https?:\/\/[^\s)>\]]+|\b[0-9a-fA-F]{8,}\b|\b[\w.~\-]+(?:[\\/][\w.~\-]+)+\b/

const KEEPER_CONFIG_NAME = "rtr-re-keeper.json"
const KEEPER_STATUS_NAME = "rtr-re-keeper-status.json"

let KEEPER_PRESETS = PRESET_REGISTRY.keeperPresets
let KEEPER_PRESET_ALIASES = PRESET_REGISTRY.keeperAliases ?? {}
let RETRIEVAL_MODALITIES = PRESET_REGISTRY.modalities
let CPU_PROFILES = PRESET_REGISTRY.cpuProfiles
let CPU_PROFILE_ALIASES = PRESET_REGISTRY.cpuProfileAliases ?? {}
let THREAD_MODES = PRESET_REGISTRY.threadModes.map(Number)
let PARKING_PERCENTS = PRESET_REGISTRY.parkingPercents.map(Number)

function reloadRegistry(path) {
    const next = path ? loadPresetRegistryFrom(path) : loadPresetRegistry()
    PRESET_REGISTRY = next
    DEFAULT_PRESET = next.defaultKeeperPreset
    DEFAULT_PRESET_VALUES = next.keeperPresets[DEFAULT_PRESET]
    DEFAULT_CPU_PROFILE_NAME = next.defaultCpuProfile
    DEFAULT_CPU_PROFILE = next.cpuProfiles[DEFAULT_CPU_PROFILE_NAME]
    DEFAULT_TRIGGER_TOKENS = DEFAULT_PRESET_VALUES.triggerTokens
    DEFAULT_TARGET_TOKENS = DEFAULT_PRESET_VALUES.targetTokens
    DEFAULT_MAX_KEEP_MESSAGES = DEFAULT_PRESET_VALUES.maxKeepMessages
    KEEPER_PRESETS = next.keeperPresets
    KEEPER_PRESET_ALIASES = next.keeperAliases ?? {}
    RETRIEVAL_MODALITIES = next.modalities
    CPU_PROFILES = next.cpuProfiles
    CPU_PROFILE_ALIASES = next.cpuProfileAliases ?? {}
    THREAD_MODES = next.threadModes.map(Number)
    PARKING_PERCENTS = next.parkingPercents.map(Number)
    return next
}

function normalizePresetName(raw) {
    const value = String(raw ?? "")
        .trim()
        .toLowerCase()
        .replaceAll("_", "-")
        .replace(/[\s-]+/g, "-")
        .replace(/^-+|-+$/g, "")
    return value.endsWith("!") ? value.slice(0, -1) : value
}

function resolvePresetName(raw, field = "preset") {
    const normalized = normalizePresetName(raw) || DEFAULT_PRESET
    const name = KEEPER_PRESET_ALIASES[normalized] ?? normalized
    if (!KEEPER_PRESETS[name]) {
        throw new Error(
            `rtr-re-keeper: ${field} unknown preset ${raw}; known: ${Object.keys(KEEPER_PRESETS).join(", ")}`,
        )
    }
    return name
}

function resolveCpuProfileName(options = {}, env = process.env) {
    const raw =
        options.cpuProfile ??
        env.OPENCODE_MEMORY_RTR_PRESET_PROFILE ??
        env.OPENCODE_MEMORY_RTR_PROFILE ??
        DEFAULT_CPU_PROFILE_NAME
    const normalized = normalizePresetName(raw)
    const name = CPU_PROFILE_ALIASES[normalized] ?? normalized
    if (!CPU_PROFILES[name]) {
        throw new Error(
            `rtr-re-keeper: OPENCODE_MEMORY_RTR_PRESET_PROFILE unknown CPU preset profile ${raw}; known: ${Object.keys(CPU_PROFILES).join(", ")}`,
        )
    }
    return name
}

function resolveModalityName(raw, cpuProfile) {
    const name = normalizePresetName(raw) || cpuProfile.modality
    if (!RETRIEVAL_MODALITIES[name]) {
        throw new Error(
            `rtr-re-keeper: OPENCODE_MEMORY_RETRIEVAL_MODALITY unknown modality ${raw}; known: ${Object.keys(RETRIEVAL_MODALITIES).join(", ")}`,
        )
    }
    return name
}

function allowedInt(raw, allowed, name, allowPerModelThreads = false) {
    const value = String(raw).trim()
    if (allowPerModelThreads && value.includes(":")) {
        const parsed = []
        for (const part of value.split(",")) {
            if (!part.includes(":")) {
                throw new Error(`rtr-re-keeper: ${name} per-model mapping requires model:threads entries, got ${part}`)
            }
            const number = Number(part.split(":", 2)[1].trim())
            if (!Number.isInteger(number) || !allowed.includes(number)) {
                throw new Error(`rtr-re-keeper: ${name} must be one of ${allowed.join(", ")}, got ${number}`)
            }
            parsed.push(number)
        }
        return parsed[0]
    }
    const number = Number(value)
    if (!Number.isInteger(number) || !allowed.includes(number)) {
        throw new Error(`rtr-re-keeper: ${name} must be one of ${allowed.join(", ")}, got ${raw}`)
    }
    return number
}

function effectiveThreadsForModel(selectedThreads, parkingPercent, modelCount, logicalProcessors) {
    const processors = logicalProcessors || availableParallelism()
    const budget = Math.floor((processors * parkingPercent) / 100)
    return Math.max(1, Math.min(selectedThreads, Math.max(1, Math.floor(budget / Math.max(1, modelCount)))))
}

function profileFields(cfg) {
    const preset = KEEPER_PRESETS[cfg.preset]
    const modality = RETRIEVAL_MODALITIES[cfg.modality]
    const cpuProfile = CPU_PROFILES[cfg.cpuProfile]
    const models = cfg.models?.length ? cfg.models : [...(modality.models ?? [])]
    const effectiveThreads = effectiveThreadsForModel(
        cfg.threadsPerModel,
        cfg.parkingPercent,
        models.length,
        cfg.logicalProcessors,
    )
    return {
        presetDisplay: preset.displayName,
        cpuProfileDisplay: cpuProfile.displayName,
        computePreset: `${cfg.modality}/t${cfg.threadsPerModel}/p${cfg.parkingPercent}`,
        modalityDisplay: modality.displayName,
        models,
        hybrid: Boolean(modality.hybrid),
        expansion: Boolean(modality.expansion),
        effectiveThreadsPerModel: effectiveThreads,
        logicalProcessors: cfg.logicalProcessors || availableParallelism(),
        parkingBudgetThreads: Math.floor(
            ((cfg.logicalProcessors || availableParallelism()) * cfg.parkingPercent) / 100,
        ),
        plannedThreadsPerEngine: effectiveThreads * models.length,
        profileCode: `${cfg.preset}/${cfg.modality}/t${cfg.threadsPerModel}/p${cfg.parkingPercent}`,
        profileLabel: `${preset.displayName} · ${modality.displayName} · T${cfg.threadsPerModel} · P${cfg.parkingPercent}`,
    }
}

function positiveInt(raw, name) {
    const value = Number(raw)
    if (!Number.isInteger(value) || value <= 0) {
        throw new Error(`rtr-re-keeper: ${name} must be a positive integer, got ${raw}`)
    }
    return value
}

function enabledFlag(raw) {
    if (raw === undefined || raw === "") return true
    const s = String(raw).toLowerCase()
    if (["1", "true", "yes", "on"].includes(s)) return true
    if (["0", "false", "no", "off"].includes(s)) return false
    throw new Error(`rtr-re-keeper: enabled must be boolean-like, got ${raw}`)
}

function keeperConfigPath(directory, env = process.env) {
    if (env.RTR_RE_KEEPER_CONFIG) return env.RTR_RE_KEEPER_CONFIG
    return join(directory, ".opencode", KEEPER_CONFIG_NAME)
}

function keeperStatusPath(directory, env = process.env) {
    if (env.RTR_RE_KEEPER_STATUS) return env.RTR_RE_KEEPER_STATUS
    return join(directory, ".opencode", KEEPER_STATUS_NAME)
}

function resolveKeeperConfig(options = {}, env = process.env) {
    const pick = (opt, envName, fallback) => {
        const raw = options[opt] ?? env[envName]
        return raw === undefined || raw === "" ? fallback : positiveInt(raw, envName)
    }
    const preset = resolvePresetName(
        options.preset ?? env.OPENCODE_MEMORY_RTRRE_PRESET,
        "OPENCODE_MEMORY_RTRRE_PRESET",
    )
    const presetValues = KEEPER_PRESETS[preset]
    const cpuProfileName = resolveCpuProfileName(options, env)
    const cpuProfile = CPU_PROFILES[cpuProfileName]
    const modality = resolveModalityName(
        options.modality ?? env.OPENCODE_MEMORY_RETRIEVAL_MODALITY,
        cpuProfile,
    )
    const modelsRaw = options.models ?? env.OPENCODE_MEMORY_EMBED_MODELS
    const models = Array.isArray(modelsRaw)
        ? modelsRaw.map(String).filter(Boolean)
        : String(modelsRaw ?? "")
              .split(",")
              .map((model) => model.trim())
              .filter(Boolean)
    const threadsRaw = options.threadsPerModel ?? env.OPENCODE_MEMORY_EMBED_THREADS
    const parkingRaw = options.parkingPercent ?? env.OPENCODE_MEMORY_CPU_PARKING_PERCENT
    const logicalProcessors =
        positiveInt(options.logicalProcessors ?? availableParallelism(), "logicalProcessors")
    const cfg = {
        preset,
        cpuProfile: cpuProfileName,
        modality,
        models: models.length ? models : [...(RETRIEVAL_MODALITIES[modality].models ?? [])],
        threadsPerModel:
            threadsRaw === undefined || threadsRaw === ""
                ? cpuProfile.threadsPerModel
                : allowedInt(threadsRaw, THREAD_MODES, "OPENCODE_MEMORY_EMBED_THREADS", true),
        parkingPercent:
            parkingRaw === undefined || parkingRaw === ""
                ? cpuProfile.parkingPercent
                : allowedInt(parkingRaw, PARKING_PERCENTS, "OPENCODE_MEMORY_CPU_PARKING_PERCENT"),
        logicalProcessors,
        triggerTokens: pick(
            "triggerTokens",
            "OPENCODE_MEMORY_RTRRE_TRIGGER",
            presetValues.triggerTokens,
        ),
        targetTokens: pick(
            "targetTokens",
            "OPENCODE_MEMORY_RTRRE_TARGET",
            presetValues.targetTokens,
        ),
        maxKeepMessages: pick(
            "maxKeepMessages",
            "OPENCODE_MEMORY_RTRRE_MAX_KEEP",
            presetValues.maxKeepMessages,
        ),
        enabled: options.enabled ?? enabledFlag(env.RTR_RE_KEEPER_ENABLED),
        cumulativeMessages: Number(
            options.cumulativeMessages ?? env.OPENCODE_MEMORY_RTRRE_CUMULATIVE ?? 0,
        ),
        protectedTools: new Set([
            ...PROTECTED_TOOLS,
            ...(Array.isArray(options.protectedTools) ? options.protectedTools : []),
        ]),
    }
    Object.assign(cfg, profileFields(cfg))
    if (cfg.targetTokens >= cfg.triggerTokens) {
        throw new Error(
            `rtr-re-keeper: OPENCODE_MEMORY_RTRRE_TARGET must be below TRIGGER (${cfg.targetTokens} >= ${cfg.triggerTokens})`,
        )
    }
    return cfg
}

/** Read + validate a keeper JSON file. Returns { values, mtimeMs }. */
async function loadKeeperFileConfig(path) {
    const st = await stat(path)
    const raw = await readFile(path, "utf8")
    let data
    try {
        data = JSON.parse(raw)
    } catch (e) {
        throw new Error(`rtr-re-keeper: config file ${path} is not valid JSON: ${e.message}`)
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) {
        throw new Error(`rtr-re-keeper: config file ${path} must be a JSON object`)
    }
    const values = {}
    if (data.preset !== undefined) values.preset = resolvePresetName(data.preset, "config file preset")
    if (data.cpuProfile !== undefined) {
        const normalized = normalizePresetName(data.cpuProfile)
        const name = CPU_PROFILE_ALIASES[normalized] ?? normalized
        if (!CPU_PROFILES[name]) {
            throw new Error(`rtr-re-keeper: config file cpuProfile unknown profile ${data.cpuProfile}`)
        }
        values.cpuProfile = name
    }
    if (data.modality !== undefined) {
        const name = normalizePresetName(data.modality)
        if (!RETRIEVAL_MODALITIES[name]) {
            throw new Error(`rtr-re-keeper: config file modality unknown modality ${data.modality}`)
        }
        values.modality = name
    }
    if (data.threadsPerModel !== undefined) {
        values.threadsPerModel = allowedInt(
            data.threadsPerModel,
            THREAD_MODES,
            "config file threadsPerModel",
            true,
        )
    }
    if (data.parkingPercent !== undefined) {
        values.parkingPercent = allowedInt(
            data.parkingPercent,
            PARKING_PERCENTS,
            "config file parkingPercent",
        )
    }
    for (const [key, envName] of [
        ["triggerTokens", "triggerTokens"],
        ["targetTokens", "targetTokens"],
        ["maxKeepMessages", "maxKeepMessages"],
    ]) {
        if (data[key] !== undefined) values[key] = positiveInt(data[key], `config file ${envName}`)
    }
    if (data.enabled !== undefined) values.enabled = enabledFlag(data.enabled)
    if (values.targetTokens !== undefined || values.triggerTokens !== undefined) {
        // Full-pair check happens at merge time; record intent only.
    }
    return { values, mtimeMs: st.mtimeMs }
}

function mergeFileConfig(cfg, values, source) {
    const next = { ...cfg, protectedTools: new Set(cfg.protectedTools) }
    if (values.preset !== undefined) {
        next.preset = values.preset
        const preset = KEEPER_PRESETS[values.preset]
        next.triggerTokens = preset.triggerTokens
        next.targetTokens = preset.targetTokens
        next.maxKeepMessages = preset.maxKeepMessages
    }
    if (values.cpuProfile !== undefined) {
        next.cpuProfile = values.cpuProfile
        const profile = CPU_PROFILES[values.cpuProfile]
        next.modality = profile.modality
        next.threadsPerModel = profile.threadsPerModel
        next.parkingPercent = profile.parkingPercent
        next.models = [...(RETRIEVAL_MODALITIES[profile.modality].models ?? [])]
    }
    for (const k of [
        "triggerTokens",
        "targetTokens",
        "maxKeepMessages",
        "enabled",
        "modality",
        "threadsPerModel",
        "parkingPercent",
    ]) {
        if (values[k] !== undefined) next[k] = values[k]
    }
    if (values.modality !== undefined && values.models === undefined) {
        next.models = [...(RETRIEVAL_MODALITIES[values.modality].models ?? [])]
    }
    Object.assign(next, profileFields(next))
    if (next.targetTokens >= next.triggerTokens) {
        throw new Error(
            `rtr-re-keeper: ${source} would set TARGET >= TRIGGER (${next.targetTokens} >= ${next.triggerTokens})`,
        )
    }
    return next
}

function estimateTokens(text) {
    if (!text) return 0
    return Math.max(1, Math.floor((text.length + 3) / 4))
}

function partText(part) {
    if (!part || typeof part !== "object") return ""
    if (part.type === "text" || part.type === "reasoning") return part.text ?? ""
    if (part.type === "tool") {
        const state = part.state ?? {}
        let input = ""
        try {
            input = JSON.stringify(state.input ?? "")
        } catch {
            input = String(state.input ?? "")
        }
        return `${part.tool ?? ""} ${input} ${state.output ?? ""}`
    }
    if (part.type === "file") return `${part.filename ?? ""} ${part.url ?? ""}`
    return part.text ?? ""
}

function messageText(message) {
    const parts = Array.isArray(message?.parts) ? message.parts : []
    return parts.map(partText).join("\n")
}

function messageTokens(message) {
    return estimateTokens(messageText(message))
}

function roleOf(message) {
    return message?.info?.role ?? "unknown"
}

function hasToolPart(message) {
    return (message?.parts ?? []).some((p) => p?.type === "tool")
}

function isProtected(message, protectedTools) {
    return (message?.parts ?? []).some(
        (p) => p?.type === "tool" && protectedTools.has(p.tool),
    )
}

function spanLane(message) {
    return roleOf(message) === "assistant" && !hasToolPart(message)
        ? "written"
        : "read"
}

function spanDtype(text) {
    if (NDATA_RE.test(text || "")) return "NDATA"
    if (CDATA_RE.test(text || "")) return "CDATA"
    return "PCDATA"
}

function maskNdata(text) {
    return (text || "").replace(NDATA_RE_G, "[NDATA]")
}

/** Mirror of context_budget.plan_compression over host messages. */
function planKeepIndices(messages, cfg) {
    const tokens = messages.map(messageTokens)
    const total = tokens.reduce((a, b) => a + b, 0)
    const keep = new Set()
    if (!cfg.enabled || total <= cfg.triggerTokens || messages.length === 0) {
        messages.forEach((_, i) => keep.add(i))
        return { compress: false, keep, evict: [], total, keepTokens: total }
    }
    let keptTokens = 0
    for (let i = messages.length - 1; i >= 0; i--) {
        if (keep.size >= cfg.maxKeepMessages) break
        if (keep.size > 0 && keptTokens + tokens[i] > cfg.targetTokens) break
        keep.add(i)
        keptTokens += tokens[i]
    }
    // Tool-pair safety, fixpoint: a kept tool-result message pulls its
    // preceding call in, however long the batched chain is.
    let changed = true
    while (changed) {
        changed = false
        for (const i of [...keep].sort((a, b) => a - b)) {
            if (roleOf(messages[i]) === "tool" && i > 0 && !keep.has(i - 1)) {
                keep.add(i - 1)
                keptTokens += tokens[i - 1]
                changed = true
            }
        }
    }
    let lastUser = -1
    const cumulative = Number(cfg.cumulativeMessages) || 0
    const protectAll = cumulative < 1000
    const recencyStart = Math.max(0, messages.length - cfg.maxKeepMessages)
    messages.forEach((m, i) => {
        if (isProtected(m, cfg.protectedTools) && !keep.has(i) &&
            (protectAll || i >= recencyStart)) {
            keep.add(i)
            keptTokens += tokens[i]
        }
        if (roleOf(m) === "user") lastUser = i
    })
    if (lastUser >= 0 && !keep.has(lastUser)) {
        keep.add(lastUser)
        keptTokens += tokens[lastUser]
    }
    const evict = messages.map((_, i) => i).filter((i) => !keep.has(i))
    return { compress: evict.length > 0, keep, evict, total, keepTokens: keptTokens }
}

function evictedSpans(messages, evict) {
    return evict.map((i) => {
        const text = messageText(messages[i])
        return {
            index: i,
            role: roleOf(messages[i]),
            lane: spanLane(messages[i]),
            dtype: spanDtype(text),
            text: maskNdata(text),
        }
    })
}

function serializeSpans(spans, digest) {
    const lines = [
        `# RE:Symbiose evicted spans ${digest}`.trimEnd(),
        "",
        "Verbatim substance evicted from the live window. " +
            "PCDATA/CDATA byte-exact; NDATA masked, never embedded.",
        "",
    ]
    const census = laneCensus(spans)
    if (census.length) {
        lines.push("## lane census")
        for (const row of census) {
            lines.push(`- ${row.lane}: ${row.count} spans, ~${row.tokens} tokens`)
        }
        lines.push("")
    }
    for (const s of spans) {
        lines.push(
            `## span ${s.index}`,
            `role: ${s.role}`,
            `lane: ${s.lane}`,
            `dtype: ${s.dtype}`,
            "",
            s.text,
            "",
        )
    }
    return lines.join("\n")
}

function spansDigest(spans) {
    return createHash("sha256")
        .update(JSON.stringify(spans), "utf8")
        .digest("hex")
        .slice(0, 16)
}

// P5 (TODO-65): Object.groupBy — group evicted spans by lane for the sink
// payload summary, so the sink file carries a lane census without a second
// pass. (ES2024; verified present in the supported Node runtime.)
function laneCensus(spans) {
    const byLane = Object.groupBy(spans, (s) => s.lane ?? "unknown")
    return Object.entries(byLane).map(([lane, group]) => ({
        lane,
        count: group.length,
        tokens: group.reduce((acc, s) => acc + (s.tokens ?? 0), 0),
    }))
}

// P5 (TODO-65): Promise.withResolvers — a bounded sink wait. A hung sink
// must fail open (window untouched) instead of blocking the exchange
// forever; the timer is cleared on settle. (ES2024; verified present.)
const SINK_TIMEOUT_MS = 30000

function withTimeout(promise, ms, label) {
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

// P5 (TODO-65): Temporal for status timestamps (ES2025; falls back to
// Date when the runtime lacks Temporal).
function nowIso() {
    if (typeof Temporal !== "undefined" && Temporal.Now?.instant) {
        return Temporal.Now.instant().toString()
    }
    return new Date().toISOString()
}

/**
 * Apply the keeper plan. `sink(spans, digest)` must persist the evicted
 * spans and return a path (or a Promise of one); if it throws/rejects,
 * the exception propagates and the caller leaves the window untouched
 * (fail-open in the hook).
 */
async function applyKeeper(messages, cfg, sink) {
    const plan = planKeepIndices(messages, cfg)
    if (!plan.compress) {
        return { changed: false, messages, plan, sinkPath: null }
    }
    const spans = evictedSpans(messages, plan.evict)
    const digest = spansDigest(spans)
    const sinkPath = await withTimeout(sink(spans, digest), SINK_TIMEOUT_MS, "sink")
    const kept = messages.filter((_, i) => plan.keep.has(i))
    const evictedTokens = plan.total - plan.keepTokens
    const note =
        `[RTR-RE:Symbiose] ${plan.evict.length} earlier spans ` +
        `(~${evictedTokens} est. tokens) were evicted verbatim to ` +
        `directives/sessions/rtrre-${digest}.md and are retrievable via ` +
        `memory_search. Kept tail: ~${plan.keepTokens} tokens ` +
        `(target ${cfg.targetTokens}).`
    const host = kept.find((m) => roleOf(m) === "user") ?? kept[0]
    if (host) {
        const parts = Array.isArray(host.parts) ? host.parts : []
        const firstText = parts.find((p) => p?.type === "text")
        if (firstText) {
            host.parts = [
                {
                    ...firstText,
                    id: `${firstText.id ?? "rtrre"}-rtrre-note`,
                    text: note,
                },
                ...parts,
            ]
        }
    }
    return { changed: true, messages: kept, plan, sinkPath }
}

function writeSink(directory) {
    return async (spans, digest) => {
        const dir = join(directory, "directives", "sessions")
        await mkdir(dir, { recursive: true })
        const path = join(dir, `rtrre-${digest || "spans"}.md`)
        // LF via explicit join("\n") in serializeSpans; no translation.
        await writeFile(path, serializeSpans(spans, digest), "utf8")
        return path
    }
}

/** Read the Python worker's cumulative counter file; 0 when absent. */
async function readCumulativeFile(path) {
    let raw
    try {
        raw = await readFile(path, "utf8")
    } catch {
        return 0
    }
    const state = JSON.parse(raw)
    const value = Number(state?.cumulative_messages ?? 0)
    if (!Number.isFinite(value) || value < 0) {
        throw new Error("cumulative_messages must be >= 0")
    }
    return value
}

async function writeStatusFile(path, status) {
    const payload = { keeper: "rtr-re-keeper", version: KEEPER_VERSION, ...status }
    await mkdir(dirname(path), { recursive: true })
    // Atomic write: temp + rename, mirroring the Python worker's
    // cumulative-counter persistence. A reader never sees a torn status.
    const tmp = `${path}.tmp`
    await writeFile(tmp, JSON.stringify(payload, null, 2) + "\n", "utf8")
    await rename(tmp, path)
    return path
}

const INTERNAL_AGENTS = new Set(["title", "summary", "compaction"])

function isInternalRequest(messages) {
    for (let i = messages.length - 1; i >= 0; i--) {
        const info = messages[i]?.info
        if (info?.role === "user") {
            return INTERNAL_AGENTS.has(info.agent ?? "")
        }
    }
    return false
}

function formatStatus(cfg, last) {
    const lines = [
        "RTR-RE Keeper status (native, live):",
        `profile: ${cfg.profileLabel} (${cfg.profileCode})`,
        `preset: ${cfg.preset} (${cfg.presetDisplay})`,
        `enabled: ${cfg.enabled}`,
        `trigger: ${cfg.triggerTokens} tokens`,
        `target: ${cfg.targetTokens} tokens (hold)`,
        `maxKeepMessages: ${cfg.maxKeepMessages}`,
        `modality: ${cfg.modality} (${cfg.modalityDisplay})`,
        `threads: T${cfg.threadsPerModel} selected, ${cfg.effectiveThreadsPerModel} effective per model`,
        `parking: P${cfg.parkingPercent} (${cfg.plannedThreadsPerEngine} planned threads of ${cfg.parkingBudgetThreads} budgeted)`,
    ]
    if (last) {
        lines.push(
            `last decision: ${last.decision} at ${last.time}`,
            `last window: total ~${last.total} tokens, kept ~${last.keepTokens}, evicted ${last.evicted}`,
        )
        if (last.sinkPath) lines.push(`last sink: ${last.sinkPath}`)
        if (last.error) lines.push(`last error: ${last.error}`)
    } else {
        lines.push("no eviction yet this process (window below trigger so far)")
    }
    return lines.join("\n")
}

const RTR_USAGE =
    "rtr usage: /rtr status | hold <tokens> | trigger <tokens> | target <tokens> | max <n> | preset <standard|calibrated|wide|fusion-ah|symbiose-ah|re-symbiose|re-symbiose-mugen> | cpu <public-default|local-system> | modality <rtr-full|rtr-arctic|rtr-bge|rag-hybrid-base|rag-dense-base|rag-hybrid|rag-dense|custom> | threads <2|4|6|8|12|16> | parking <20|30|40|50|60|70|80> | enable | disable"

/**
 * Shared `/rtr` verb executor (P1, TODO-65): used by both the command
 * hook (`command.execute.before`) and the prompt-level parser
 * (PROMPT_RTR_RE in the transform). `say` receives the reply text.
 */
async function runRtrVerb(verb, rest, ctx, say) {
    try {
        if (!verb || verb === "status") {
            say(formatStatus(ctx.getConfig(), ctx.last))
            return
        }
        if (verb === "help") {
            say(RTR_USAGE)
            return
        }
        if (verb === "enable" || verb === "disable") {
            const values = { enabled: verb === "enable" }
            await ctx.writeFileConfig(values)
            say(`keeper ${verb}d; applies on the next exchange (no restart)`)
            return
        }
        if (verb === "preset") {
            const name = resolvePresetName(rest[0] ?? "", "preset")
            const preset = KEEPER_PRESETS[name]
            await ctx.writeFileConfig({ preset: name, ...preset })
            say(
                `keeper preset ${name} applied (trigger ${preset.triggerTokens}, target ${preset.targetTokens}, max ${preset.maxKeepMessages}); next exchange uses it`,
            )
            return
        }
        if (verb === "cpu") {
            const name = resolveCpuProfileName({ cpuProfile: rest[0] ?? "" }, {})
            const profile = CPU_PROFILES[name]
            await ctx.writeFileConfig({
                cpuProfile: name,
                modality: profile.modality,
                threadsPerModel: profile.threadsPerModel,
                parkingPercent: profile.parkingPercent,
            })
            say(
                `keeper CPU profile ${name} applied (${profile.modality}, T${profile.threadsPerModel}, P${profile.parkingPercent}); next exchange uses it`,
            )
            return
        }
        if (verb === "modality") {
            const name = resolveModalityName(rest[0] ?? "", CPU_PROFILES[ctx.getConfig().cpuProfile])
            await ctx.writeFileConfig({ modality: name })
            say(`keeper modality ${name} set; applies on the next exchange (no restart)`)
            return
        }
        if (verb === "threads") {
            const value = allowedInt(rest[0] ?? "", THREAD_MODES, "threads", true)
            await ctx.writeFileConfig({ threadsPerModel: value })
            say(`keeper threads T${value} set; applies on the next exchange (no restart)`)
            return
        }
        if (verb === "parking") {
            const value = allowedInt(rest[0] ?? "", PARKING_PERCENTS, "parking")
            await ctx.writeFileConfig({ parkingPercent: value })
            say(`keeper parking P${value} set; applies on the next exchange (no restart)`)
            return
        }
        const numeric = { hold: "targetTokens", target: "targetTokens", trigger: "triggerTokens", max: "maxKeepMessages" }[
            verb
        ]
        if (!numeric) {
            say(RTR_USAGE)
            return
        }
        const value = positiveInt(rest[0], verb)
        await ctx.writeFileConfig({ [numeric]: value })
        say(`keeper ${verb} set to ${value}; applies on the next exchange (no restart)`)
    } catch (error) {
        say(`keeper command refused: ${error?.message ?? error} (live window untouched)`)
    }
}

/**
 * `/rtr` command handler. Mutates output.parts in place with the result
 * text and returns normally (the command result rides to the model as
 * the user message; no abort-error hack, no ERROR log line).
 */
async function handleRtrCommand(input, output, ctx) {
    const args = (input.arguments ?? "").trim().split(/\s+/).filter(Boolean)
    const [verb, ...rest] = args.map((a) => String(a))
    const parts = Array.isArray(output.parts) ? output.parts : (output.parts = [])
    const say = (text) => {
        parts.length = 0
        parts.push({ type: "text", text })
    }
    await runRtrVerb(verb, rest, ctx, say)
}

// P1 (TODO-65): prompt-level `/rtr` parser (Agile pattern — regex on the
// prompt). Matches "/rtr status", "/rtr preset mugen", "/rtr max 200",
// etc. inside the last user message, so the command family works in plain
// chat without the command palette.
const PROMPT_RTR_RE = /^\s*\/(?:rtr|rtr-re)(?:\s+([a-z][a-z0-9_-]*))?(?:\s+([\s\S]*?))?\s*$/i

// P4 (TODO-65): processed-array dedup so V1 and V2 surfaces never
// double-process the same exchange.
const processedMessageArrays = new WeakSet()

// P2 (TODO-65): reminder cadence for the one-line status note.
const REMINDER_EVERY = 10

const server = async (ctx, options = {}) => {
    let cfg = resolveKeeperConfig(options)
    const configPath = options.configFile ?? keeperConfigPath(ctx.directory, process.env)
    const statusPath = options.statusFile ?? keeperStatusPath(ctx.directory, process.env)
    const cumulativePath =
        options.cumulativeFile ??
        join(ctx.directory, ".opencode", "rtr-re-cumulative.json")
    let fileMtime = 0
    let cumulativeMtime = 0
    let last = null
    let exchangeCount = 0

    const sink = writeSink(ctx.directory)

    // The cumulative counter is owned by the Python worker (atomic
    // temp+rename). This host-side mirror reads it so the recency-aware
    // protection (TODO-45) behaves identically in both engines: past
    // PROTECTION_CUMULATIVE_THRESHOLD only recent protected messages stay
    // hard-protected. A missing/corrupt file reads as 0 (all-protect),
    // never as a refusal — the worker is the authority.
    async function refreshCumulative() {
        let st = null
        try {
            st = await stat(cumulativePath)
        } catch {
            if (cumulativeMtime !== 0) {
                cumulativeMtime = 0
                cfg = { ...cfg, cumulativeMessages: 0 }
            }
            return
        }
        if (st.mtimeMs === cumulativeMtime) return
        try {
            const value = await readCumulativeFile(cumulativePath)
            cfg = { ...cfg, cumulativeMessages: value }
            cumulativeMtime = st.mtimeMs
        } catch (error) {
            console.error(
                `[rtr-re-keeper] cumulative counter read refused: ${error?.message ?? error}`,
            )
        }
    }

    async function refreshConfig() {
        // Registry reload (finding d, TODO-65): the registry is loaded once
        // at module load; if it changed on disk (e.g. a new preset shipped
        // mid-session), reload it so newly-added preset names resolve without
        // a restart. This fixes the measured stale-registry refusal.
        if (REGISTRY_PATH) {
            try {
                const st = await stat(REGISTRY_PATH)
                if (st.mtimeMs !== REGISTRY_MTIME) {
                    reloadRegistry()
                }
            } catch {
                // Registry missing is not a config failure; keep the loaded one.
            }
        }
        let st = null
        try {
            st = await stat(configPath)
        } catch {
            return false
        }
        if (st.mtimeMs === fileMtime) return false
        const { values } = await loadKeeperFileConfig(configPath)
        cfg = mergeFileConfig(cfg, values, `config file ${configPath}`)
        fileMtime = st.mtimeMs
        return true
    }

    async function recordStatus(decision) {
        last = { time: nowIso(), ...decision }
        const status = {
            preset: cfg.preset,
            presetDisplay: cfg.presetDisplay,
            cpuProfile: cfg.cpuProfile,
            computePreset: cfg.computePreset,
            modality: cfg.modality,
            threadsPerModel: cfg.threadsPerModel,
            effectiveThreadsPerModel: cfg.effectiveThreadsPerModel,
            parkingPercent: cfg.parkingPercent,
            profileCode: cfg.profileCode,
            profileLabel: cfg.profileLabel,
            enabled: cfg.enabled,
            triggerTokens: cfg.triggerTokens,
            targetTokens: cfg.targetTokens,
            maxKeepMessages: cfg.maxKeepMessages,
            configFile: configPath,
            ...last,
        }
        try {
            await writeStatusFile(statusPath, status)
        } catch (error) {
            console.error(`[rtr-re-keeper] status write failed: ${error?.message ?? error}`)
        }
    }

    async function commandCtx() {
        return {
            getConfig: () => cfg,
            last,
            writeFileConfig: async (values) => {
                let current = {}
                try {
                    current = JSON.parse(await readFile(configPath, "utf8"))
                    if (!current || typeof current !== "object") current = {}
                } catch {
                    current = {}
                }
                const merged = { ...current, ...values }
                const probe = mergeFileConfig(cfg, merged, "command update")
                await mkdir(join(ctx.directory, ".opencode"), { recursive: true })
                await writeFile(configPath, JSON.stringify(merged, null, 2) + "\n", "utf8")
                cfg = probe
                try {
                    fileMtime = (await stat(configPath)).mtimeMs
                } catch {
                    fileMtime = 0
                }
            },
        }
    }

    // Shared processing core for both the V1 transform and the V2
    // `context` hook. The WeakSet dedup guarantees a given messages array
    // is processed exactly once even when both surfaces fire for the same
    // exchange (P4, TODO-65).
    async function processMessages(messages) {
        if (processedMessageArrays.has(messages)) return
        processedMessageArrays.add(messages)
        try {
            try {
                await refreshConfig()
                await refreshCumulative()
            } catch (error) {
                console.error(`[rtr-re-keeper] config reload refused: ${error?.message ?? error}`)
            }
            if (!Array.isArray(messages) || messages.length === 0) return
            if (isInternalRequest(messages)) return
            // P1 (TODO-65): prompt-level /rtr commands in plain chat.
            let lastUser = null
            for (let i = messages.length - 1; i >= 0; i--) {
                if (messages[i]?.info?.role === "user") {
                    lastUser = messages[i]
                    break
                }
            }
            if (lastUser) {
                const pm = PROMPT_RTR_RE.exec(messageText(lastUser))
                if (pm) {
                    const reply = []
                    await runRtrVerb(
                        pm[1] ?? "",
                        (pm[2] ?? "").trim().split(/\s+/).filter(Boolean),
                        await commandCtx(),
                        (t) => reply.push(t),
                    )
                    if (reply.length) {
                        const parts = Array.isArray(lastUser.parts)
                            ? lastUser.parts
                            : (lastUser.parts = [])
                        parts.push({ type: "text", text: reply.join("\n"), synthetic: true })
                    }
                    return
                }
            }
            if (!cfg.enabled) {
                await recordStatus({ decision: "disabled-identity", total: 0, keepTokens: 0, evicted: 0, sinkPath: null })
                return
            }
            // P2 (TODO-65): status injection split — full status on the first
            // processed exchange, one-line reminder every REMINDER_EVERY
            // exchanges, so the keeper's presence is visible without cost.
            exchangeCount += 1
            if (exchangeCount === 1 || exchangeCount % REMINDER_EVERY === 0) {
                const last = messages[messages.length - 1]
                if (last) {
                    const parts = Array.isArray(last.parts) ? last.parts : (last.parts = [])
                    const note =
                        exchangeCount === 1
                            ? formatStatus(cfg, last)
                            : `RTR-RE Keeper active — ${cfg.profileCode}`
                    parts.push({ type: "text", text: note, synthetic: true })
                }
            }
            const result = await applyKeeper(messages, cfg, sink)
            if (result.changed) {
                messages.length = 0
                messages.push(...result.messages)
                await recordStatus({
                    decision: "evicted",
                    total: result.plan.total,
                    keepTokens: result.plan.keepTokens,
                    evicted: result.plan.evict.length,
                    sinkPath: result.sinkPath,
                })
            } else {
                await recordStatus({
                    decision: "kept-verbatim",
                    total: result.plan.total,
                    keepTokens: result.plan.keepTokens,
                    evicted: 0,
                    sinkPath: null,
                })
            }
        } catch (error) {
            // Fail-open: a keeper fault must never lose context or
            // break the request. The sink runs before any eviction,
            // so an error here leaves the window exactly as it was.
            console.error(`[rtr-re-keeper] ${error?.message ?? error}`)
            try {
                await recordStatus({
                    decision: "error-fail-open",
                    total: 0,
                    keepTokens: 0,
                    evicted: 0,
                    sinkPath: null,
                    error: String(error?.message ?? error),
                })
            } catch {
                // Status itself must never break the request either.
            }
        }
    }

    // P4 (TODO-65): modern V2 hook surface alongside the V1 transform
    // (opencode-thinking-fix pattern). The `context` hook observes the
    // same messages; the WeakSet dedup keeps processing single.
    if (typeof ctx?.session?.hook === "function") {
        try {
            await ctx.session.hook("context", async (event) => {
                await processMessages(event?.messages)
            })
            await ctx.session.hook("compaction", async (event) => {
                const messages = event?.messages
                if (Array.isArray(messages) && messages.length) {
                    await recordStatus({
                        decision: "compaction-observer",
                        total: 0,
                        keepTokens: 0,
                        evicted: 0,
                        sinkPath: null,
                    })
                }
            })
        } catch (error) {
            console.error(`[rtr-re-keeper] V2 hook registration failed: ${error?.message ?? error}`)
        }
    }

    return {
        "experimental.chat.messages.transform": async (_input, output) => {
            await processMessages(output?.messages)
        },
        "command.execute.before": async (input, output) => {
            if (input.command !== "rtr" && input.command !== "rtr-re") return
            await handleRtrCommand(input, output, await commandCtx())
        },
        config: async (opencodeConfig) => {
            opencodeConfig.command ??= {}
            if (!opencodeConfig.command["rtr"]) {
                opencodeConfig.command["rtr"] = {
                    template: "",
                    description: "RTR-RE Keeper: status | hold | trigger | target | max | preset | cpu | modality | threads | parking | enable | disable",
                }
            }
        },
    }
}

export default server

// Single-export module: the OpenCode legacy loader iterates every export
// and requires each to be a function, so helpers ride on _test.
server._test = {
    KEEPER_CONFIG_NAME,
    KEEPER_PRESETS,
    KEEPER_STATUS_NAME,
    KEEPER_VERSION,
    allowedInt,
    applyKeeper,
    effectiveThreadsForModel,
    estimateTokens,
    evictedSpans,
    handleRtrCommand,
    keeperConfigPath,
    keeperStatusPath,
    loadKeeperFileConfig,
    readCumulativeFile,
    messageTokens,
    normalizePresetName,
    planKeepIndices,
    profileFields,
    reloadRegistry,
    resolveCpuProfileName,
    resolveKeeperConfig,
    resolveModalityName,
    resolvePresetName,
    serializeSpans,
    spansDigest,
}
