// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import assert from "node:assert/strict"
import test from "node:test"
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { mkdir, writeFile, readFile } from "node:fs/promises"
import { join } from "node:path"
import { tmpdir } from "node:os"
import server from "./rtr-re-keeper.js"

const {
    applyKeeper,
    estimateTokens,
    handleRtrCommand,
    loadKeeperFileConfig,
    planKeepIndices,
    readCumulativeFile,
    reloadRegistry,
    resolveKeeperConfig,
    serializeSpans,
} = server._test

const cfg = (over = {}) =>
    resolveKeeperConfig(
        { triggerTokens: 1000, targetTokens: 400, maxKeepMessages: 40, ...over },
        {},
    )

function msg(role, text, extra = {}) {
    return {
        info: { id: `m-${Math.random()}`, role, sessionID: "s1", ...extra.info },
        parts: [
            ...(extra.tool
                ? [
                      {
                          id: "tp",
                          type: "tool",
                          tool: extra.tool,
                          state: { status: "completed", input: {}, output: text },
                      },
                  ]
                : [{ id: "p1", type: "text", text }]),
        ],
    }
}

test("config defaults are Symbiose-AH! public profile", () => {
    const c = resolveKeeperConfig({}, {})
    assert.equal(c.preset, "symbiose-ah")
    assert.equal(c.presetDisplay, "Symbiose-AH!")
    assert.equal(c.triggerTokens, 250000)
    assert.equal(c.targetTokens, 100000)
    assert.equal(c.maxKeepMessages, 40)
    assert.equal(c.modality, "rtr-full")
    assert.equal(c.threadsPerModel, 4)
    assert.equal(c.parkingPercent, 60)
    assert.equal(c.profileCode, "symbiose-ah/rtr-full/t4/p60")
    assert.equal(c.profileLabel, "Symbiose-AH! · RTR-FULL · T4 · P60")
})

test("config refuses invalid bounds by name", () => {
    assert.throws(
        () => resolveKeeperConfig({}, { OPENCODE_MEMORY_RTRRE_TRIGGER: "abc" }),
        /OPENCODE_MEMORY_RTRRE_TRIGGER/,
    )
    assert.throws(
        () =>
            resolveKeeperConfig(
                {},
                {
                    OPENCODE_MEMORY_RTRRE_TRIGGER: "100",
                    OPENCODE_MEMORY_RTRRE_TARGET: "200",
                },
            ),
        /TARGET must be below TRIGGER/,
    )
})

test("estimateTokens mirrors the Python estimator", () => {
    assert.equal(estimateTokens(""), 0)
    assert.equal(estimateTokens("abcd"), 1)
    assert.equal(estimateTokens("x".repeat(400)), 100)
})

test("below trigger the window is untouched identity", async () => {
    const messages = [msg("user", "hello"), msg("assistant", "hi")]
    const result = await applyKeeper(messages, cfg(), () => {
        throw new Error("sink must not run below trigger")
    })
    assert.equal(result.changed, false)
    assert.equal(result.messages, messages)
})

test("eviction keeps bounded tail, protected and last user", async () => {
    const messages = [msg("assistant", "keepme", { tool: "todowrite" })]
    for (let i = 0; i < 30; i++) messages.push(msg("assistant", "y".repeat(400)))
    messages.push(msg("user", "latest question"))
    const sunk = []
    const result = await applyKeeper(messages, cfg(), async (spans, digest) => {
        sunk.push(...spans)
        return `sink-${digest}`
    })
    assert.equal(result.changed, true)
    assert.ok(result.plan.keepTokens <= 400 + 200) // target + protected slack
    assert.ok(result.messages.length <= 41)
    assert.equal(result.messages[result.messages.length - 1].info.role, "user")
    assert.ok(sunk.length > 0)
    const note = result.messages
        .flatMap((m) => m.parts)
        .find((p) => typeof p.text === "string" && p.text.includes("RTR-RE:Symbiose"))
    assert.ok(note, "eviction note is injected")
})

test("tool chain is repaired to its call (fixpoint parity)", () => {
    const messages = [
        { info: { id: "c", role: "assistant" }, parts: [{ id: "p", type: "text", text: "x".repeat(400) }] },
        { info: { id: "t1", role: "tool" }, parts: [{ id: "p", type: "text", text: "x".repeat(400) }] },
        { info: { id: "t2", role: "tool" }, parts: [{ id: "p", type: "text", text: "x".repeat(400) }] },
    ]
    const plan = planKeepIndices(messages, cfg({ triggerTokens: 250, targetTokens: 150 }))
    assert.deepEqual([...plan.keep].sort((a, b) => a - b), [0, 1, 2])
})

test("sink failure leaves the window untouched through the hook", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server(
            { directory: join(dir, "a-file-not-a-dir") },
            { triggerTokens: 100, targetTokens: 40 },
        )
        // Make .opencode/memory creation fail: directory component is a file path.
        const { writeFileSync } = await import("node:fs")
        writeFileSync(join(dir, "a-file-not-a-dir"), "x")
        const messages = []
        for (let i = 0; i < 10; i++) messages.push(msg("assistant", "z".repeat(400)))
        messages.push(msg("user", "go"))
        const before = messages.length
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        assert.equal(messages.length, before)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("hook sinks verbatim spans with NDATA masked before evicting", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server(
            { directory: dir },
            { triggerTokens: 1000, targetTokens: 400 },
        )
        const blob = "QUJD".repeat(40)
        const cdataLong = "the keeper memory is infinite and retrievable. ".repeat(120)
        const messages = [
            msg("assistant", "UNIQUE-MARKER " + cdataLong),
            msg("assistant", blob),
        ]
        for (let i = 0; i < 10; i++) messages.push(msg("assistant", "w".repeat(400)))
        messages.push(msg("user", "go"))
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const { readdirSync } = await import("node:fs")
        const files = readdirSync(join(dir, ".opencode", "memory"))
        assert.equal(files.length, 2) // span file + paraphrase companion
        const spans = files.filter((f) => f.endsWith(".dtd") && !f.includes("summary"))
        assert.equal(spans.length, 1)
        const body = readFileSync(join(dir, ".opencode", "memory", spans[0]), "utf8")
        assert.ok(body.includes("UNIQUE-MARKER"))
        assert.ok(!body.includes(blob))
        assert.ok(body.includes("[NDATA]"))
        assert.ok(body.includes("<span id="))
        assert.ok(!body.includes("\r"))
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("serializeSpans matches the Python sink shape", () => {
    const out = serializeSpans(
        [{ index: 0, role: "user", lane: "read", dtype: "PCDATA", text: "exact" }],
        "abc",
    )
    assert.ok(out.spans.startsWith("<!-- RTR-RE:Symbiose keeper memory span v2"))
    assert.ok(out.spans.includes("<!ELEMENT span EMPTY>"))
    assert.ok(out.spans.includes('<span id="span-0" role="user" lane="read" dtype="PCDATA"'))
    assert.ok(out.spans.includes("exact"))
    assert.ok(out.summaries.includes('<paraphrase spanref="span-0" text="exact"'))
})

// --- Live control: watched config file ---

test("config file reload changes bounds without restart", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server({ directory: dir }, {})
        const cfgPath = join(dir, ".opencode", "rtr-re-keeper.json")
        const transform = hooks["experimental.chat.messages.transform"]
        // Baseline: default 320k trigger, small window stays verbatim.
        const small = [msg("user", "hello")]
        await transform({}, { messages: small })
        assert.equal(small.length, 1)
        // Write a tight config file; next exchange must honor it.
        const { mkdir } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(cfgPath, JSON.stringify({ triggerTokens: 100, targetTokens: 40 }), "utf8")
        const big = []
        for (let i = 0; i < 10; i++) big.push(msg("assistant", "z".repeat(400)))
        big.push(msg("user", "go"))
        const before = big.length
        await transform({}, { messages: big })
        assert.ok(big.length < before, "new bounds evicted on the next exchange")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("invalid config file is refused, live window untouched", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server({ directory: dir }, {})
        const { mkdir } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(join(dir, ".opencode", "rtr-re-keeper.json"), "{not json", "utf8")
        const messages = [msg("user", "hello"), msg("assistant", "hi")]
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        assert.equal(messages.length, 2)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("loadKeeperFileConfig validates shape and values", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const p = join(dir, "k.json")
        await writeFile(p, JSON.stringify({ triggerTokens: 100, targetTokens: 40 }), "utf8")
        const { values } = await loadKeeperFileConfig(p)
        assert.equal(values.triggerTokens, 100)
        await writeFile(p, "[1,2]", "utf8")
        await assert.rejects(loadKeeperFileConfig(p), /JSON object/)
        await writeFile(p, JSON.stringify({ triggerTokens: "abc" }), "utf8")
        await assert.rejects(loadKeeperFileConfig(p), /positive integer/)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("enabled:false turns the transform into identity", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server({ directory: dir }, { triggerTokens: 100, targetTokens: 40 })
        const { mkdir } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(join(dir, ".opencode", "rtr-re-keeper.json"), JSON.stringify({ enabled: false }), "utf8")
        const messages = []
        for (let i = 0; i < 10; i++) messages.push(msg("assistant", "z".repeat(400)))
        messages.push(msg("user", "go"))
        const before = messages.length
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        assert.equal(messages.length, before)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("status file is written at the exchange boundary", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server({ directory: dir }, {})
        await hooks["experimental.chat.messages.transform"]({}, { messages: [msg("user", "hi")] })
        const raw = await readFile(join(dir, ".opencode", "rtr-re-keeper-status.json"), "utf8")
        const st = JSON.parse(raw)
        assert.equal(st.keeper, "rtr-re-keeper")
        assert.equal(st.triggerTokens, 250000)
        assert.ok(st.time)
        assert.equal(st.decision, "kept-verbatim")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

// --- Live control: /rtr commands ---

function commandCtx(dir) {
    let fileCfg = {}
    return {
        getConfig: () => cfg(),
        last: null,
        writeFileConfig: async (values) => {
            fileCfg = { ...fileCfg, ...values }
        },
        fileCfg: () => fileCfg,
    }
}

test("rtr status reports bounds without changing anything", async () => {
    const output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "status" }, output, commandCtx())
    assert.match(output.parts[0].text, /trigger: 1000 tokens/)
    assert.match(output.parts[0].text, /target: 400 tokens \(hold\)/)
})

test("rtr hold writes target and confirms", async () => {
    const ctx = commandCtx()
    const output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "hold 64000" }, output, ctx)
    assert.equal(ctx.fileCfg().targetTokens, 64000)
    assert.match(output.parts[0].text, /64000/)
})

test("rtr rejects bad values without touching config", async () => {
    const ctx = commandCtx()
    const output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "trigger abc" }, output, ctx)
    assert.deepEqual(ctx.fileCfg(), {})
    assert.match(output.parts[0].text, /refused/)
})

test("rtr preset + enable/disable round-trip", async () => {
    const ctx = commandCtx()
    let output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "preset calibrated" }, output, ctx)
    assert.equal(ctx.fileCfg().triggerTokens, 40000)
    output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "disable" }, output, ctx)
    assert.equal(ctx.fileCfg().enabled, false)
    output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "enable" }, output, ctx)
    assert.equal(ctx.fileCfg().enabled, true)
    output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "preset nope" }, output, ctx)
    assert.match(output.parts[0].text, /unknown preset/)
})

test("operator presets Fusion-AH!, Symbiose-AH!, Re-Symbiose carry the declared bounds", () => {
    // Operator vocabulary: Target = when to fire (keeper triggerTokens),
    // Retrieval = the maintained tail (keeper targetTokens).
    const { KEEPER_PRESETS: presets } = server._test
    // Operator 2026-11-04 final decision: every user starts on
    // Symbiose-AH!, and the retained windows are 30, 40, 50.
    assert.deepEqual(presets["fusion-ah"], {
        displayName: "Fusion-AH!",
        triggerTokens: 200000,
        targetTokens: 100000,
        maxKeepMessages: 30,
    })
    assert.deepEqual(presets["symbiose-ah"], {
        displayName: "Symbiose-AH!",
        triggerTokens: 250000,
        targetTokens: 100000,
        maxKeepMessages: 40,
    })
    assert.deepEqual(presets["re-symbiose"], {
        displayName: "Re-Symbiose",
        triggerTokens: 320000,
        targetTokens: 128000,
        maxKeepMessages: 50,
    })
    assert.equal(presets["re-symbiose-ah"], undefined)
})

test("rtr preset Symbiose-ah! round-trips its exact numbers", async () => {
    const ctx = commandCtx()
    const output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "preset Symbiose-ah!" }, output, ctx)
    assert.equal(ctx.fileCfg().triggerTokens, 250000)
    assert.equal(ctx.fileCfg().targetTokens, 100000)
    assert.equal(ctx.fileCfg().maxKeepMessages, 40)
    assert.match(output.parts[0].text, /symbiose-ah/)
})

test("every bound is independently settable after a preset (user override)", async () => {
    const ctx = commandCtx()
    let output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "preset Symbiose-ah!" }, output, ctx)
    output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "max 45" }, output, ctx)
    assert.equal(ctx.fileCfg().maxKeepMessages, 45)
    assert.equal(ctx.fileCfg().triggerTokens, 250000)
    output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "trigger 900000" }, output, ctx)
    assert.equal(ctx.fileCfg().triggerTokens, 900000)
    assert.equal(ctx.fileCfg().maxKeepMessages, 45)
})

test("config hook registers the rtr command once", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server({ directory: dir }, {})
        const oc = {}
        await hooks.config(oc)
        assert.ok(oc.command["rtr"])
        assert.match(oc.command["rtr"].description, /status/)
        const before = oc.command["rtr"]
        await hooks.config(oc)
        assert.equal(oc.command["rtr"], before)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("readCumulativeFile reads the worker file, absent means 0, corrupt refuses", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const path = join(dir, "rtr-re-cumulative.json")
        assert.equal(await readCumulativeFile(path), 0)
        await writeFile(path, JSON.stringify({ cumulative_messages: 1001 }), "utf8")
        assert.equal(await readCumulativeFile(path), 1001)
        await writeFile(path, "{ not json", "utf8")
        await assert.rejects(() => readCumulativeFile(path), /JSON/)
        await writeFile(path, JSON.stringify({ cumulative_messages: -3 }), "utf8")
        await assert.rejects(() => readCumulativeFile(path), />= 0/)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

function recencyWindow() {
    const messages = []
    for (let i = 0; i < 60; i++) {
        messages.push(msg("assistant", "x".repeat(400)))
    }
    messages[5] = msg("assistant", "x".repeat(400), { tool: "todowrite" })
    messages[55] = msg("assistant", "x".repeat(400), { tool: "todowrite" })
    messages.push(msg("user", "go"))
    return messages
}

test("recency parity: past 1000 cumulative old protected todowrite is evicted", () => {
    const messages = recencyWindow()
    const plan = planKeepIndices(
        messages,
        cfg({ triggerTokens: 2000, targetTokens: 1500, cumulativeMessages: 1001 }),
    )
    assert.ok(plan.keep.has(55), "recent protected todowrite stays")
    assert.ok(!plan.keep.has(5), "old protected todowrite yields to newer context")
    assert.ok(plan.keep.has(60), "last user stays")
})

test("below 1000 cumulative every protected todowrite is kept (all-protect)", () => {
    const messages = recencyWindow()
    const plan = planKeepIndices(
        messages,
        cfg({ triggerTokens: 2000, targetTokens: 1500, cumulativeMessages: 999 }),
    )
    assert.ok(plan.keep.has(5), "old protected todowrite stays below threshold")
    assert.ok(plan.keep.has(55))
})

test("server reads the cumulative file and applies recency through the hook", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const cumulativeFile = join(dir, ".opencode", "rtr-re-cumulative.json")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(cumulativeFile, JSON.stringify({ cumulative_messages: 1001 }), "utf8")
        const hooks = await server(
            { directory: dir },
            { triggerTokens: 2000, targetTokens: 1500, cumulativeFile },
        )
        const messages = recencyWindow()
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const keptTools = messages.map((m) => m.parts[0]?.tool).filter(Boolean)
        assert.ok(keptTools.includes("todowrite"), "recent protected survives")
        assert.equal(
            keptTools.filter((t) => t === "todowrite").length,
            1,
            "old protected evicted",
        )
        assert.ok(messages.some((m) => m.info.role === "user"))
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("status file is written atomically with no .tmp leftover", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server(
            { directory: dir },
            { triggerTokens: 100, targetTokens: 40 },
        )
        const messages = []
        for (let i = 0; i < 10; i++) messages.push(msg("assistant", "z".repeat(400)))
        messages.push(msg("user", "go"))
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const statusPath = join(dir, ".opencode", "rtr-re-keeper-status.json")
        const status = JSON.parse(readFileSync(statusPath, "utf8"))
        assert.equal(status.keeper, "rtr-re-keeper")
        assert.equal(status.decision, "evicted")
        assert.ok(!existsSync(`${statusPath}.tmp`), "no temp status file remains")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

// --- TODO-65 implementations: P1 prompt parser, P2 injection, P4 dedup,
// --- registry reload (finding d) ---

test("P1: prompt-level /rtr status appends a synthetic reply part", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server({ directory: dir }, {})
        const user = msg("user", "/rtr status")
        const messages = [user, msg("assistant", "hi")]
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const reply = user.parts.find((p) => p.synthetic === true)
        assert.ok(reply, "synthetic reply part appended")
        assert.match(reply.text, /profile:/)
        assert.match(reply.text, /trigger:/)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("P1: prompt-level /rtr preset mugen writes the config file", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server({ directory: dir }, {})
        const user = msg("user", "/rtr preset mugen")
        const messages = [user]
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const cfgPath = join(dir, ".opencode", "rtr-re-keeper.json")
        const written = JSON.parse(readFileSync(cfgPath, "utf8"))
        assert.equal(written.preset, "re-symbiose-mugen")
        assert.equal(written.triggerTokens, 400000)
        assert.equal(written.targetTokens, 200000)
        assert.equal(written.maxKeepMessages, 200)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("P1: prompt-level /rtr enable works while disabled", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const { mkdir } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(
            join(dir, ".opencode", "rtr-re-keeper.json"),
            JSON.stringify({ enabled: false }),
            "utf8",
        )
        const hooks = await server({ directory: dir }, {})
        const user = msg("user", "/rtr enable")
        const messages = [user]
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const cfgPath = join(dir, ".opencode", "rtr-re-keeper.json")
        const written = JSON.parse(readFileSync(cfgPath, "utf8"))
        assert.equal(written.enabled, true)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("P2: first exchange injects full status, later exchanges stay lean", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server({ directory: dir }, {})
        const first = [msg("user", "hello")]
        await hooks["experimental.chat.messages.transform"]({}, { messages: first })
        const firstNote = first[0].parts.find((p) => p.synthetic === true)
        assert.ok(firstNote, "full status injected on first exchange")
        assert.match(firstNote.text, /RTR-RE Keeper status/)
        const second = [msg("user", "again")]
        await hooks["experimental.chat.messages.transform"]({}, { messages: second })
        const secondNote = second[0].parts.find((p) => p.synthetic === true)
        assert.equal(secondNote, undefined, "no reminder before the cadence")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("P4: the same messages array is processed exactly once", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server(
            { directory: dir },
            { triggerTokens: 100, targetTokens: 40 },
        )
        const messages = []
        for (let i = 0; i < 10; i++) messages.push(msg("assistant", "z".repeat(400)))
        messages.push(msg("user", "go"))
        const before = messages.length
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const afterFirst = messages.length
        assert.ok(afterFirst < before, "first pass evicted")
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        assert.equal(messages.length, afterFirst, "second pass is a no-op")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("registry reload picks up a newly added preset without restart", () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const base = JSON.parse(
            readFileSync(join(import.meta.dirname, "assets", "rtr_presets.json"), "utf8"),
        )
        base.keeperPresets["test-fresh"] = {
            displayName: "Test Fresh",
            triggerTokens: 2000,
            targetTokens: 1000,
            maxKeepMessages: 10,
        }
        const p = join(dir, "registry.json")
        writeFileSync(p, JSON.stringify(base), "utf8")
        reloadRegistry(p)
        const c = resolveKeeperConfig({ preset: "test-fresh" }, {})
        assert.equal(c.triggerTokens, 2000)
        assert.equal(c.targetTokens, 1000)
        assert.equal(c.maxKeepMessages, 10)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})
