// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// RTR-RE:Symbiose native Keeper for OpenCode — first-party, self-contained.
// No dependencies.
//
// Office: Keeper only. On every request it estimates the visible window;
// above TRIGGER it keeps a bounded verbatim tail (TARGET), sinks the
// evicted spans verbatim (NDATA masked) to <project>/.opencode/memory/ for
// the RTR memory MCP index, and only then rewrites the outgoing message
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

const KEEPER_VERSION = "1.2.0"

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
const PROTECTION_BUDGET_FRACTION = 0.25
const DEBT_DIVISOR = 10
const DEBT_DECAY = 0.8
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
        manual: options.manual === undefined ? false : enabledFlag(options.manual),
        cumulativeMessages: Number(
            options.cumulativeMessages ?? env.OPENCODE_MEMORY_RTRRE_CUMULATIVE ?? 0,
        ),
        protectedTools: new Set([
            ...PROTECTED_TOOLS,
            ...(Array.isArray(options.protectedTools) ? options.protectedTools : []),
        ]),
        evictTokensNow: 0,
        evictMessagesNow: 0,
    }
    if (options.evictTokensNow !== undefined) cfg.evictTokensNow = positiveInt(options.evictTokensNow, "evictTokensNow")
    if (options.evictMessagesNow !== undefined) cfg.evictMessagesNow = positiveInt(options.evictMessagesNow, "evictMessagesNow")
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
        ["evictTokensNow", "evictTokensNow"],
        ["evictMessagesNow", "evictMessagesNow"],
    ]) {
        if (data[key] !== undefined) values[key] = positiveInt(data[key], `config file ${envName}`)
    }
    if (data.enabled !== undefined) values.enabled = enabledFlag(data.enabled)
    if (data.manual !== undefined) values.manual = enabledFlag(data.manual)
    if (data.repairNow !== undefined) values.repairNow = enabledFlag(data.repairNow)
    // Full target/trigger pair check happens at merge time.
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
        "manual",
        "modality",
        "threadsPerModel",
        "parkingPercent",
        "repairNow",
        "evictTokensNow",
        "evictMessagesNow",
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
    if (part.type === "text" || part.type === "reasoning") return part.text ?? part.reasoning ?? ""
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
    if (part.type === "patch") return (part.files ?? []).join(" ")
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
    if (roleOf(message) === "assistant" && !hasToolPart(message)) {
        const parts = Array.isArray(message?.parts) ? message.parts : []
        const hasVisibleText = parts.some(
            (p) => p?.type === "text" && String(p.text ?? "").trim() !== "",
        )
        const hasThinking = parts.some(
            (p) =>
                p?.type === "reasoning" &&
                String(p.text ?? p.reasoning ?? "").trim() !== "",
        )
        if (!hasVisibleText && hasThinking) return "think"
        return "written"
    }
    return "read"
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
function planKeepIndices(messages, cfg, sunkDigests = new Map(), targetOverride = null, force = false) {
    const tokens = messages.map(messageTokens)
    const total = tokens.reduce((a, b) => a + b, 0)
    const keep = new Set()
    if (!cfg.enabled || messages.length === 0) {
        messages.forEach((_, i) => keep.add(i))
        return { compress: false, keep, evict: [], total, keepTokens: total, loopBound: "none", overrunTokens: 0, overrunBy: "none", reEvicted: [], newlySunk: 0, effectiveTotal: total }
    }
    // Incremental eviction (RRD-110): pre-partition sunk spans out. They
    // leave the served window without re-sink; only fresh plans and sinks.
    const sunkFilter = sunkDigests instanceof Map || sunkDigests instanceof Set ? sunkDigests : new Map()
    const sunkSet = new Set()
    const fresh = []
    const freshTokens = []
    messages.forEach((m, i) => {
        if (sunkFilter.has(spanDigest(messageText(m)))) sunkSet.add(i)
        else { fresh.push(i); freshTokens.push(tokens[i]) }
    })
    const effectiveTotal = freshTokens.reduce((a, b) => a + b, 0)
    const reEvicted = [...sunkSet].sort((a, b) => a - b)
    // Debt-tightened budget (RRD-109/117): the hook passes an effective
    // target; default keeps today's behavior exactly.
    const effTarget = targetOverride ?? cfg.targetTokens
    if (!force && effectiveTotal <= cfg.triggerTokens) {
        fresh.forEach((i) => keep.add(i))
        return {
            compress: reEvicted.length > 0, keep, evict: [...reEvicted], total,
            keepTokens: effectiveTotal, loopBound: "none", overrunTokens: 0, overrunBy: "none",
            reEvicted, newlySunk: 0, effectiveTotal,
        }
    }
    let keptTokens = 0
    let loopBound = "exhausted"
    for (let i = messages.length - 1; i >= 0; i--) {
        if (sunkSet.has(i)) continue
        if (keep.size >= cfg.maxKeepMessages) { loopBound = "maxKeep"; break }
        if (keep.size > 0 && keptTokens + tokens[i] > effTarget) { loopBound = "target"; break }
        keep.add(i)
        keptTokens += tokens[i]
    }
    // Tool-pair safety, fixpoint: a kept tool-result message pulls its
    // preceding call in, however long the batched chain is.
    let changed = true
    let fixToks = 0
    while (changed) {
        changed = false
        for (const i of [...keep].sort((a, b) => a - b)) {
            if (roleOf(messages[i]) === "tool" && i > 0 && !keep.has(i - 1) && !sunkSet.has(i - 1)) {
                keep.add(i - 1)
                keptTokens += tokens[i - 1]
                fixToks += tokens[i - 1]
                changed = true
            }
        }
    }
    let lastUser = -1
    const cumulative = Number(cfg.cumulativeMessages) || 0
    const protectAll = cumulative < 1000
    const recencyStart = Math.max(0, messages.length - cfg.maxKeepMessages)
    let protToks = 0
    // Protection budget backstop (RRD-105/115): in recency-gated mode the
    // gap-span pulls are newest-first within 25% of target (oldest shed
    // first); the newest protected is always kept as the working-set
    // floor. protectAll (young session, nothing archived) stays unbounded.
    const protCandidates = []
    messages.forEach((m, i) => {
        if (isProtected(m, cfg.protectedTools) && !keep.has(i) && !sunkSet.has(i) &&
            (protectAll || i >= recencyStart)) {
            protCandidates.push(i)
        }
        if (roleOf(m) === "user" && !sunkSet.has(i)) lastUser = i
    })
    protCandidates.sort((a, b) => b - a)
    const protBudget = protectAll ? Infinity : Math.floor(effTarget * PROTECTION_BUDGET_FRACTION)
    for (const i of protCandidates) {
        if (protToks > 0 && protToks + tokens[i] > protBudget) break
        keep.add(i)
        keptTokens += tokens[i]
        protToks += tokens[i]
    }
    let lastToks = 0
    if (lastUser >= 0 && !keep.has(lastUser)) {
        keep.add(lastUser)
        keptTokens += tokens[lastUser]
        lastToks += tokens[lastUser]
    }
    const evict = messages.map((_, i) => i).filter((i) => !keep.has(i))
    const overrunTokens = fixToks + protToks + lastToks
    const contributors = [
        fixToks > 0 ? "fixpoint" : null,
        protToks > 0 ? "protection" : null,
        lastToks > 0 ? "lastUser" : null,
    ].filter(Boolean)
    const newlySunk = evict.length - reEvicted.length
    return {
        compress: evict.length > 0, keep, evict, total, keepTokens: keptTokens,
        loopBound, overrunTokens,
        overrunBy: contributors.length ? contributors.join("+") : "none",
        reEvicted, newlySunk, effectiveTotal,
    }
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

const SPAN_SCHEMA = [
    "<!-- RTR-RE:Symbiose keeper memory span v2.1 (DTD-shaped) -->",
    '<!ENTITY % rtrre.span.module "INCLUDE">',
    "<![%rtrre.span.module;[",
    "<!ELEMENT span EMPTY>",
    "<!ATTLIST span",
    "    id ID #REQUIRED",
    "    role (user|assistant|tool|system|unknown) #REQUIRED",
    "    lane (read|written|think|plan|unknown) #IMPLIED",
    "    dtype (PCDATA|CDATA|NDATA) #IMPLIED",
    "    ts CDATA #IMPLIED",
    "    source CDATA #IMPLIED",
    "    session CDATA #IMPLIED>",
    "]]>",
    "<!-- verbatim span content follows -->",
    "",
].join("\n")

const SUMMARY_SCHEMA = [
    "<!-- RTR-RE:Symbiose keeper paraphrase v2 (DTD-shaped) -->",
    '<!ENTITY % rtrre.summary.module "INCLUDE">',
    "<![%rtrre.summary.module;[",
    "<!ELEMENT paraphrase EMPTY>",
    "<!ATTLIST paraphrase",
    "    spanref IDREF #REQUIRED",
    "    text CDATA #REQUIRED",
    "    ts CDATA #IMPLIED>",
    "]]>",
    "<!-- common-line anchors follow -->",
    "",
].join("\n")

const ANCHOR_MAX = 160

function anchorLine(text) {
    for (const line of String(text ?? "").split("\n")) {
        const stripped = line.trim()
        if (stripped) {
            return stripped.length > ANCHOR_MAX ? stripped.slice(0, ANCHOR_MAX) + "…" : stripped
        }
    }
    return ""
}

function escapeAttr(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
}

function serializeSpans(spans, digest) {
    const lines = [SPAN_SCHEMA]
    const summaries = [SUMMARY_SCHEMA]
    for (const s of spans) {
        const role = escapeAttr(s.role ?? "unknown")
        const lane = escapeAttr(s.lane ?? "read")
        const dtype = escapeAttr(s.dtype ?? "PCDATA")
        const ts = escapeAttr(s.ts ?? "")
        const source = escapeAttr(s.source ?? "")
        const session = escapeAttr(s.session ?? "")
        const idx = escapeAttr(s.index ?? "?")
        lines.push(
            `<span id="span-${idx}" role="${role}" lane="${lane}" ` +
                `dtype="${dtype}" ts="${ts}" source="${source}" session="${session}">`,
        )
        let text = String(s.text ?? "")
        if (dtype === "NDATA") {
            text = "[NDATA]"
        }
        lines.push(text, "</span>", "")
        const anchor = anchorLine(text)
        if (anchor) {
            summaries.push(`<paraphrase spanref="span-${escapeAttr(idx)}" text="${escapeAttr(anchor)}" ts="${ts}"/>`)
        }
    }
    return { spans: lines.join("\n"), summaries: summaries.join("\n") }
}

function spansDigest(spans) {
    return createHash("sha256")
        .update(JSON.stringify(spans), "utf8")
        .digest("hex")
        .slice(0, 16)
}

// P5 (TODO-65): Promise.withResolvers — a bounded sink wait. A hung sink
// must fail open (window untouched) instead of blocking the exchange
// forever; the timer is cleared on settle. (ES2024; verified present.)
function spanDigest(text) {
    return createHash("sha256").update(String(text ?? ""), "utf8").digest("hex").slice(0, 16)
}

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
 * Apply the keeper plan. `sink(spans, digest, evictMessages)` must persist
 * the evicted spans plus a .submit.json sidecar for the worker drain,
 * and return a path (or a Promise of one); if it throws/rejects,
 * the exception propagates and the caller leaves the window untouched
 * (fail-open in the hook).
 */
async function applyKeeper(messages, cfg, sink, sunkDigests = new Map(), targetOverride = null, force = false) {
    const plan = planKeepIndices(messages, cfg, sunkDigests, targetOverride, force)
    if (!plan.compress) {
        return { changed: false, messages, plan, sinkPath: null }
    }
    const kept = messages.filter((_, i) => plan.keep.has(i))
    if (plan.newlySunk === 0) {
        // Pure re-eviction (RRD-110): served window trimmed, nothing new
        // sunk — no sink I/O, no sidecar, no repeat note.
        return { changed: true, messages: kept, plan, sinkPath: null, sunkAdded: [] }
    }
    const reEvicted = new Set(plan.reEvicted)
    const freshEvict = plan.evict.filter((i) => !reEvicted.has(i))
    const spans = evictedSpans(messages, freshEvict)
    const digest = spansDigest(spans)
    const sinkPath = await withTimeout(sink(spans, digest, freshEvict.map((i) => messages[i])), SINK_TIMEOUT_MS, "sink")
    const freshEvictTokens = freshEvict.reduce((a, i) => a + messageTokens(messages[i]), 0)
    const note =
        `[RTR-RE:Symbiose] ${freshEvict.length} earlier spans ` +
        `(~${freshEvictTokens} est. tokens) were evicted verbatim to ` +
        `.opencode/memory/rtrre-${digest}.dtd and are retrievable via ` +
        `memory_search. Kept tail: ~${plan.keepTokens} tokens ` +
        `(target ${cfg.targetTokens}).` +
        (plan.reEvicted.length ? ` ${plan.reEvicted.length} older spans already sunk.` : "")
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
    const sunkAdded = freshEvict.map((i) => spanDigest(messageText(messages[i])))
    return { changed: true, messages: kept, plan, sinkPath, sunkAdded }
}

function writeSink(directory) {
    return async (spans, digest, evictMessages = []) => {
        const dir = join(directory, ".opencode", "memory")
        await mkdir(dir, { recursive: true })
        const path = join(dir, `rtrre-${digest || "spans"}.dtd`)
        const serialized = serializeSpans(spans, digest)
        // LF via explicit join("\n"); no translation.
        await writeFile(path, serialized.spans, "utf8")
        if (serialized.summaries !== SUMMARY_SCHEMA) {
            const summaryPath = join(dir, `rtrre-summary-${digest || "spans"}.dtd`)
            await writeFile(summaryPath, serialized.summaries, "utf8")
        }
        const sidecarPath = join(dir, `rtrre-${digest || "spans"}.submit.json`)
        await writeFile(
            sidecarPath,
            JSON.stringify({ digest: digest || "spans", ts: nowIso(), messages: evictMessages ?? [] }),
            "utf8",
        )
        return path
    }
}

/** Read the Python worker's cumulative counter file; 0 when absent. */
const KEEPER_SUNK_NAME = "rtr-re-sunk.json"

async function loadSunkDigests(directory) {
    // Absent -> empty. Corrupt -> heal-empty with loud error (RRD-113):
    // relief must never depend on aux-file integrity.
    const sunk = new Map()
    let debt = 0
    const path = join(directory, ".opencode", KEEPER_SUNK_NAME)
    let raw = null
    try {
        raw = await readFile(path, "utf8")
    } catch {
        return { sunk, debt }
    }
    try {
        const parsed = JSON.parse(raw)
        const list = Array.isArray(parsed?.digests) ? parsed.digests : []
        for (const d of list) if (typeof d === "string" && d) sunk.set(d, 1)
        if (typeof parsed?.debt === "number" && parsed.debt >= 0) debt = Math.floor(parsed.debt)
    } catch (error) {
        console.error(`[rtr-re-keeper] sunk store corrupt, healing empty: ${error?.message ?? error}`)
        try {
            await saveSunkDigests(directory, new Map(), 0)
        } catch (rewriteError) {
            console.error(`[rtr-re-keeper] sunk store rewrite failed: ${rewriteError?.message ?? rewriteError}`)
        }
        return { sunk: new Map(), debt: 0 }
    }
    return { sunk, debt }
}

async function saveSunkDigests(directory, sunk, debt = 0) {
    const path = join(directory, ".opencode", KEEPER_SUNK_NAME)
    const tmp = `${path}.tmp`
    await mkdir(join(directory, ".opencode"), { recursive: true })
    await writeFile(tmp, JSON.stringify({ v: 1, digests: [...sunk.keys()], debt }), "utf8")
    await rename(tmp, path)
}

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
        `manual: ${cfg.manual ?? false}`,
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
    "rtr usage: /rtr status | hold <tokens> | trigger <tokens> | target <tokens> | max <n> | preset <standard|calibrated|wide|fusion-ah|symbiose-ah|re-symbiose|re-symbiose-mugen> | cpu <public-default|local-system> | modality <rtr-full|rtr-arctic|rtr-bge|rag-hybrid-base|rag-dense-base|rag-hybrid|rag-dense|custom> | threads <2|4|6|8|12|16> | parking <20|30|40|50|60|70|80> | evict-tokens <n> | evict-messages <n> | repair | enable | disable"

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
            await ctx.writeFileConfig({ preset: name, manual: false, ...preset })
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
                manual: false,
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
        if (verb === "evict-tokens" || verb === "evict-messages") {
            const value = positiveInt(rest[0], verb)
            const key = verb === "evict-tokens" ? "evictTokensNow" : "evictMessagesNow"
            await ctx.writeFileConfig({ [key]: value })
            say(`keeper ${verb} ${value} armed; fires on the next exchange (no restart)`)
            return
        }
        if (verb === "repair") {
            await ctx.writeFileConfig({ repairNow: true })
            say("repair requested; the engine tick executes it and reports back (no restart)")
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
        await ctx.writeFileConfig({ [numeric]: value, manual: false })
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
        let heapMB = null
        let cpuMs = null
        try {
            heapMB = Math.round(process.memoryUsage().heapUsed / 1048576)
            const cpu = process.cpuUsage()
            cpuMs = Math.round((cpu.user + cpu.system) / 1000)
        } catch {
            // Health is best-effort; never break status on it.
        }
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
            heapMB,
            cpuMs,
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

    async function clearOneShotFlags() {
        let current = {}
        try {
            current = JSON.parse(await readFile(configPath, "utf8"))
            if (!current || typeof current !== "object") current = {}
        } catch {
            current = {}
        }
        delete current.evictTokensNow
        delete current.evictMessagesNow
        delete current.repairNow
        await mkdir(join(ctx.directory, ".opencode"), { recursive: true })
        await writeFile(configPath, JSON.stringify(current, null, 2) + "\n", "utf8")
        const { evictTokensNow: _t, evictMessagesNow: _m, repairNow: _r, ...rest } = cfg
        cfg = { ...rest, evictTokensNow: 0, evictMessagesNow: 0, repairNow: false }
        try {
            fileMtime = (await stat(configPath)).mtimeMs
        } catch {
            fileMtime = 0
        }
    }

    async function clearRepairFlag() {
        let current = {}
        try {
            current = JSON.parse(await readFile(configPath, "utf8"))
            if (!current || typeof current !== "object") current = {}
        } catch {
            current = {}
        }
        delete current.repairNow
        await mkdir(join(ctx.directory, ".opencode"), { recursive: true })
        await writeFile(configPath, JSON.stringify(current, null, 2) + "\n", "utf8")
        const { repairNow: _r, ...rest } = cfg
        cfg = { ...rest, repairNow: false }
        try {
            fileMtime = (await stat(configPath)).mtimeMs
        } catch {
            fileMtime = 0
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
            const oneShotTokens = Math.floor(Number(cfg.evictTokensNow) || 0)
            const oneShotMessages = Math.floor(Number(cfg.evictMessagesNow) || 0)
            const oneShot = oneShotTokens > 0 || oneShotMessages > 0
            // Repair bus (TODO-13): a repairNow flag becomes a request file
            // the engine tick executes. Works in every mode (repair touches
            // no window) and rides along with normal processing.
            if (cfg.repairNow) {
                try {
                    await mkdir(join(ctx.directory, ".opencode"), { recursive: true })
                    await writeFile(
                        join(ctx.directory, ".opencode", "rtr-re-repair.requested.json"),
                        JSON.stringify({ ts: nowIso(), source: "keeper-flag" }) + "\n",
                        "utf8",
                    )
                } catch (error) {
                    console.error(`[rtr-re-keeper] repair request failed: ${error?.message ?? error}`)
                }
                await clearRepairFlag()
                await recordStatus({ decision: "repair-requested", total: 0, keepTokens: 0, evicted: 0, sinkPath: null })
            }
            if (!cfg.enabled && !oneShot) {
                await recordStatus({ decision: "disabled-identity", total: 0, keepTokens: 0, evicted: 0, sinkPath: null })
                return
            }
            if (cfg.manual && !oneShot) {
                // Manual serves an exact window: already-sunk spans leave
                // (hygiene, zero information loss), nothing new is evicted,
                // and telemetry reports the real window, never zeros.
                const sunkState = await loadSunkDigests(ctx.directory)
                const probe = planKeepIndices(messages, cfg, sunkState.sunk)
                if (probe.reEvicted.length === 0) {
                    await recordStatus({ decision: "manual-identity", total: probe.total, keepTokens: probe.total, evicted: 0, sinkPath: null })
                    return
                }
                const drop = new Set(probe.reEvicted)
                const kept = messages.filter((_, i) => !drop.has(i))
                const keepTokens = kept.reduce((a, m) => a + messageTokens(m), 0)
                messages.length = 0
                messages.push(...kept)
                await recordStatus({ decision: "manual-trimmed", total: probe.total, keepTokens, evicted: drop.size, sinkPath: null })
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
            const sunkState = await loadSunkDigests(ctx.directory)
            const sunkStore = sunkState.sunk
            // Debt-divided quota (RRD-109/117): past over-target misses
            // tighten this firing's keep budget; cfg itself never mutates.
            const quota = Math.floor(sunkState.debt / DEBT_DIVISOR)
            const effectiveTarget = Math.max(0, cfg.targetTokens - quota)
            // One-shot eviction (buttons): an explicit evict-amount
            // overrides the trigger gate; protections still hold via the
            // shared planner, and the flag clears after firing.
            let ovTarget = effectiveTarget
            let ovCfg = cfg
            if (oneShot) {
                const probe = planKeepIndices(messages, cfg, sunkStore)
                const freshCount = messages.length - probe.reEvicted.length
                if (oneShotTokens > 0) {
                    ovTarget = Math.max(0, probe.effectiveTotal - oneShotTokens)
                } else {
                    // Messages-only: neutralize the token target so the
                    // count quota binds instead of the (possibly tiny)
                    // target.
                    ovTarget = probe.effectiveTotal
                }
                if (oneShotMessages > 0) {
                    ovCfg = { ...cfg, maxKeepMessages: Math.max(0, freshCount - oneShotMessages) }
                } else {
                    // Tokens-only: neutralize the message cap so only the
                    // token quota binds. Without this the 200-message cap
                    // massacres big windows (measured: 498 evicted for a
                    // 30k quota).
                    ovCfg = { ...cfg, maxKeepMessages: freshCount }
                }
            }
            const result = await applyKeeper(messages, ovCfg, sink, sunkStore, ovTarget, oneShot)
            if (oneShot) {
                await clearOneShotFlags()
            }
            let debt = sunkState.debt
            if (result.changed) {
                const miss = result.plan.keepTokens - cfg.targetTokens
                debt = Math.max(0, Math.round(sunkState.debt * DEBT_DECAY + miss))
                if (result.sunkAdded && result.sunkAdded.length) {
                    for (const d of result.sunkAdded) sunkStore.set(d, 1)
                }
                await saveSunkDigests(ctx.directory, sunkStore, debt)
            }
            if (result.changed) {
                messages.length = 0
                messages.push(...result.messages)
                await recordStatus({
                    decision: oneShot ? "evicted-oneshot" : result.plan.newlySunk > 0 ? "evicted" : "re-evicted",
                    total: result.plan.total,
                    keepTokens: result.plan.keepTokens,
                    evicted: result.plan.evict.length,
                    sinkPath: result.sinkPath,
                    loopBound: result.plan.loopBound,
                    overrunTokens: result.plan.overrunTokens,
                    overrunBy: result.plan.overrunBy,
                    reEvicted: result.plan.reEvicted.length,
                    newlySunk: result.plan.newlySunk,
                    effectiveTotal: result.plan.effectiveTotal,
                    debt,
                    effectiveTarget,
                })
            } else {
                await recordStatus({
                    decision: "kept-verbatim",
                    total: result.plan.total,
                    keepTokens: result.plan.keepTokens,
                    evicted: 0,
                    sinkPath: null,
                    loopBound: result.plan.loopBound,
                    overrunTokens: result.plan.overrunTokens,
                    overrunBy: result.plan.overrunBy,
                    debt: sunkState.debt,
                    effectiveTarget: cfg.targetTokens,
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
    messageText,
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
    spanDigest,
    spansDigest,
}
