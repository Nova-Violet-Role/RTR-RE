// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import assert from "node:assert/strict"
import test from "node:test"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { writeFile, readFile } from "node:fs/promises"
import { join } from "node:path"
import { tmpdir } from "node:os"
import server from "./rtr-re-keeper.js"

const {
    applyKeeper,
    estimateTokens,
    handleRtrCommand,
    loadKeeperFileConfig,
    planKeepIndices,
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
        // Make directives/sessions creation fail: directory component is a file path.
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
        const messages = [msg("assistant", `UNIQUE-MARKER ${blob} ` + "v".repeat(4000))]
        for (let i = 0; i < 10; i++) messages.push(msg("assistant", "w".repeat(400)))
        messages.push(msg("user", "go"))
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const { readdirSync } = await import("node:fs")
        const files = readdirSync(join(dir, "directives", "sessions"))
        assert.equal(files.length, 1)
        const body = readFileSync(join(dir, "directives", "sessions", files[0]), "utf8")
        assert.ok(body.includes("UNIQUE-MARKER"))
        assert.ok(!body.includes(blob))
        assert.ok(body.includes("[NDATA]"))
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
    assert.ok(out.startsWith("# RE:Symbiose evicted spans abc"))
    assert.ok(out.includes("## span 0"))
    assert.ok(out.includes("lane: read"))
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
