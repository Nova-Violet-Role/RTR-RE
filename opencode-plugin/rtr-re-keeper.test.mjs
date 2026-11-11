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
    evictedSpans,
    handleRtrCommand,
    loadKeeperFileConfig,
    messageTokens,
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

test("config defaults are Re-Symbiose-Mugen public profile", () => {
    const c = resolveKeeperConfig({}, {})
    assert.equal(c.preset, "re-symbiose-mugen")
    assert.equal(c.presetDisplay, "Re-Symbiose-Mugen")
    assert.equal(c.triggerTokens, 400000)
    assert.equal(c.targetTokens, 200000)
    assert.equal(c.maxKeepMessages, 200)
    assert.equal(c.modality, "rtr-full")
    assert.equal(c.threadsPerModel, 4)
    assert.equal(c.parkingPercent, 60)
    assert.equal(c.profileCode, "re-symbiose-mugen/rtr-full/t4/p60")
    assert.equal(c.profileLabel, "Re-Symbiose-Mugen · RTR-FULL · T4 · P60")
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

test("eviction order is oldest-first (keeper)", async () => {
    const messages = []
    for (let i = 0; i < 10; i++) messages.push(msg("assistant", "y".repeat(400)))
    messages.push(msg("user", "go"))
    const result = await applyKeeper(
        messages,
        cfg({ triggerTokens: 500, targetTokens: 200 }),
        async () => "sink",
    )
    assert.equal(result.changed, true)
    const evict = result.plan.evict
    assert.deepEqual([...evict].sort((a, b) => a - b), evict)
    assert.equal(evict[0], 0)
    for (let i = 1; i < evict.length; i++) assert.equal(evict[i], evict[i - 1] + 1)
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

test("plan reports loopBound target with zero overrun when the budget binds", () => {
    const messages = []
    for (let i = 0; i < 11; i++) messages.push(msg("user", "x".repeat(400)))
    const plan = planKeepIndices(messages, cfg({ triggerTokens: 1000, targetTokens: 400, maxKeepMessages: 40 }))
    assert.equal(plan.loopBound, "target")
    assert.equal(plan.overrunTokens, 0)
    assert.equal(plan.overrunBy, "none")
})

test("plan reports loopBound maxKeep when the message cap binds", () => {
    const messages = []
    for (let i = 0; i < 120; i++) messages.push(msg("user", "x".repeat(40)))
    const plan = planKeepIndices(messages, cfg({ triggerTokens: 1000, targetTokens: 400, maxKeepMessages: 40 }))
    assert.equal(plan.loopBound, "maxKeep")
    assert.equal(plan.overrunTokens, 0)
    assert.equal(plan.overrunBy, "none")
})

test("plan reports protection overrun with tokens in protect-all mode", () => {
    // Unbounded overrun accounting lives here (young session, nothing
    // archived yet); gated-mode capping is pinned by the budget tests.
    const messages = []
    for (let i = 0; i < 40; i++) {
        if (i >= 25 && i <= 35) messages.push(msg("tool", "x".repeat(40), { tool: "todowrite" }))
        else messages.push(msg("user", "x".repeat(40)))
    }
    for (let i = 0; i < 20; i++) messages.push(msg("user", "x".repeat(1200)))
    const plan = planKeepIndices(
        messages,
        cfg({ triggerTokens: 1000, targetTokens: 400, maxKeepMessages: 40, cumulativeMessages: 500 }),
    )
    assert.equal(plan.loopBound, "target")
    // 11 todowrite pulls x 14 tokens each: partText counts tool name (9)
    // + JSON input (2) + output (40) + joins = 53 chars -> 14 tokens.
    assert.equal(plan.overrunTokens, 154)
    assert.equal(plan.overrunBy, "protection")
})

test("under-trigger plan reports loopBound none", () => {
    const messages = [msg("user", "hi"), msg("assistant", "hello")]
    const plan = planKeepIndices(messages, cfg({ triggerTokens: 1000, targetTokens: 400 }))
    assert.equal(plan.compress, false)
    assert.equal(plan.loopBound, "none")
    assert.equal(plan.overrunTokens, 0)
    assert.equal(plan.overrunBy, "none")
})

test("plan pre-partitions sunk spans out without re-sinking", () => {
    const { spanDigest, messageText } = server._test
    const olds = []
    for (let i = 0; i < 5; i++) olds.push(msg("user", `old ${i} ` + "x".repeat(1200)))
    const fresh = msg("user", "fresh " + "x".repeat(1200))
    const messages = [...olds, fresh]
    const sunk = new Map()
    for (const m of olds) sunk.set(spanDigest(messageText(m)), 302)
    const plan = planKeepIndices(messages, cfg({ triggerTokens: 1000, targetTokens: 400 }), sunk)
    assert.deepEqual(plan.evict, [0, 1, 2, 3, 4])
    assert.deepEqual(plan.reEvicted, [0, 1, 2, 3, 4])
    assert.equal(plan.newlySunk, 0)
    assert.deepEqual([...plan.keep].sort((a, b) => a - b), [5])
    assert.equal(plan.effectiveTotal, plan.keepTokens)
})

test("plan honors a debt-tightened target override", () => {
    const messages = []
    for (let i = 0; i < 120; i++) messages.push(msg("user", "x".repeat(40)))
    const plan = planKeepIndices(messages, cfg({ triggerTokens: 1000, targetTokens: 400 }), new Map(), 390)
    assert.equal(plan.keepTokens, 390)
    assert.equal(plan.keep.size, 39)
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
        const dtd = files.filter((f) => f.endsWith(".dtd"))
        assert.equal(dtd.length, 2) // span file + paraphrase companion (.submit.json aside)
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

test("re-eviction trims served sunk spans without re-sinking", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const { spanDigest, messageText } = server._test
        const olds = []
        for (let i = 0; i < 5; i++) olds.push(msg("user", `old ${i} ` + "x".repeat(1200)))
        const fresh = msg("user", "fresh " + "x".repeat(1200))
        const messages = [...olds, fresh]
        const digests = olds.map((m) => spanDigest(messageText(m)))
        await mkdir(join(dir, ".opencode"), { recursive: true })
        writeFileSync(join(dir, ".opencode", "rtr-re-sunk.json"), JSON.stringify({ v: 1, digests }))
        const hooks = await server({ directory: dir }, { triggerTokens: 1000, targetTokens: 400 })
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        assert.equal(messages.length, 1)
        assert.ok(messages[0].parts[0].text.startsWith("fresh "))
        const { readdirSync, existsSync: exists } = await import("node:fs")
        const memDir = join(dir, ".opencode", "memory")
        const files = exists(memDir) ? readdirSync(memDir) : []
        assert.ok(!files.some((f) => f.endsWith(".submit.json")), "no sidecar on pure re-eviction")
        const status = JSON.parse(readFileSync(join(dir, ".opencode", "rtr-re-keeper-status.json"), "utf8"))
        assert.equal(status.decision, "re-evicted")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("corrupt sunk store heals empty and rewrites valid", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const messages = [msg("user", "hello " + "x".repeat(4000))]
        await mkdir(join(dir, ".opencode"), { recursive: true })
        writeFileSync(join(dir, ".opencode", "rtr-re-sunk.json"), "{not json")
        const hooks = await server({ directory: dir }, { triggerTokens: 1000, targetTokens: 400 })
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const healed = JSON.parse(readFileSync(join(dir, ".opencode", "rtr-re-sunk.json"), "utf8"))
        assert.deepEqual(healed.digests, [])
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("protection budget caps gap pulls newest-first in gated mode", () => {
    const { messageTokens } = server._test
    const messages = []
    for (let i = 0; i < 60; i++) {
        if (i >= 20 && i < 50) messages.push(msg("tool", "x".repeat(40), { tool: "todowrite" }))
        else if (i < 20) messages.push(msg("user", "x".repeat(40)))
        else messages.push(msg("user", "x".repeat(1200)))
    }
    const plan = planKeepIndices(
        messages,
        cfg({ triggerTokens: 2000, targetTokens: 400, maxKeepMessages: 40, cumulativeMessages: 5000 }),
    )
    // Budget 100 (25% of 400); each pull 14 tokens -> 7 newest kept (98).
    const perPull = messageTokens(msg("tool", "x".repeat(40), { tool: "todowrite" }))
    assert.equal(plan.overrunTokens, 7 * perPull)
    assert.equal(plan.overrunBy, "protection")
    for (let i = 43; i <= 49; i++) assert.ok(plan.keep.has(i), `keeps protected ${i}`)
    for (let i = 20; i <= 42; i++) assert.ok(!plan.keep.has(i), `sheds protected ${i}`)
})

test("protection budget always keeps the newest protected as floor", () => {
    const { messageTokens } = server._test
    const messages = []
    for (let i = 0; i < 20; i++) messages.push(msg("user", "x".repeat(40)))
    messages.push(msg("tool", "x".repeat(4000), { tool: "todowrite" }))
    for (let i = 21; i < 40; i++) messages.push(msg("user", "x".repeat(40)))
    for (let i = 0; i < 20; i++) messages.push(msg("user", "x".repeat(1200)))
    const plan = planKeepIndices(
        messages,
        cfg({ triggerTokens: 2000, targetTokens: 400, maxKeepMessages: 40, cumulativeMessages: 5000 }),
    )
    assert.ok(plan.keep.has(20), "newest protected kept over budget")
    assert.equal(plan.overrunTokens, messageTokens(messages[20]))
    assert.equal(plan.overrunBy, "protection")
})

test("debt from over-target firing tightens the next firing", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server({ directory: dir }, { triggerTokens: 1000, targetTokens: 400 })
        const leanA = []
        for (let i = 0; i < 60; i++) leanA.push(msg("user", `a${String(i).padStart(3, "0")}#` + "x".repeat(35)))
        const fat = msg("user", "fat " + "x".repeat(1996))
        const m1 = [...leanA, fat]
        await hooks["experimental.chat.messages.transform"]({}, { messages: m1 })
        const s1 = JSON.parse(readFileSync(join(dir, ".opencode", "rtr-re-keeper-status.json"), "utf8"))
        // Firing 2: sunk A filtered; 110 fresh lean; debt tightens the walk.
        // Expectations derive from firing 1's reported debt (robust to the
        // P2 status injection riding on the fat message, pinned separately).
        const leanB = []
        for (let i = 0; i < 110; i++) leanB.push(msg("user", `b${String(i).padStart(3, "0")}#` + "x".repeat(35)))
        const m2 = [...leanA, ...leanB]
        await hooks["experimental.chat.messages.transform"]({}, { messages: m2 })
        const eff = 400 - Math.floor(s1.debt / 10)
        const served = Math.floor(eff / 10)
        assert.equal(m2.length, served)
        const status = JSON.parse(readFileSync(join(dir, ".opencode", "rtr-re-keeper-status.json"), "utf8"))
        assert.equal(status.effectiveTarget, eff)
        assert.equal(status.debt, Math.max(0, Math.round(s1.debt * 0.8 + (served * 10 - 400))))
        const sunk = JSON.parse(readFileSync(join(dir, ".opencode", "rtr-re-sunk.json"), "utf8"))
        assert.equal(sunk.digests.length, 60 + (110 - served))
        assert.equal(sunk.debt, status.debt)
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

test("serializeSpans escapes attributes and covers producer values", () => {
    const out = serializeSpans(
        [{ index: 0, role: "system", lane: "written", dtype: "PCDATA", text: 'say "hi"', ts: 'a"b', source: "s", session: "x" }],
        "abc",
    )
    assert.ok(out.spans.includes("role (user|assistant|tool|system|unknown) #REQUIRED"))
    assert.ok(out.spans.includes("lane (read|written|think|plan|unknown) #IMPLIED"))
    assert.ok(out.spans.includes("dtype (PCDATA|CDATA|NDATA) #IMPLIED"))
    assert.ok(out.spans.includes('role="system"'))
    assert.ok(out.spans.includes('ts="a&quot;b"'))
    assert.ok(!out.spans.includes('ts="a"b"'))
    assert.ok(out.summaries.includes('text="say &quot;hi&quot;"'))
})

test("hook writes a submit sidecar per firing for the worker drain", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server(
            { directory: dir },
            { triggerTokens: 100, targetTokens: 40 },
        )
        const messages = []
        for (let i = 0; i < 10; i++) messages.push(msg("assistant", "q".repeat(400)))
        messages.push(msg("user", "go"))
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const { readdirSync } = await import("node:fs")
        const files = readdirSync(join(dir, ".opencode", "memory")).filter((f) => f.endsWith(".submit.json"))
        assert.equal(files.length, 1)
        const sidecar = JSON.parse(readFileSync(join(dir, ".opencode", "memory", files[0]), "utf8"))
        assert.equal(typeof sidecar.digest, "string")
        assert.equal(typeof sidecar.ts, "string")
        assert.ok(Array.isArray(sidecar.messages))
        assert.ok(sidecar.messages.length > 0)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("reasoning parts count toward the window (DB-verified shape)", () => {
    const thinking = {
        info: { id: "r1", role: "assistant", sessionID: "s1" },
        parts: [{ id: "p1", type: "reasoning", text: "deliberate ".repeat(500) }],
    }
    assert.ok(messageTokens(thinking) > 1000)
})

test("thinking-only messages sink on the think lane", () => {
    const thinking = {
        info: { id: "r1", role: "assistant", sessionID: "s1" },
        parts: [{ id: "p1", type: "reasoning", text: "deliberate ".repeat(500) }],
    }
    const spans = evictedSpans([thinking], [0])
    assert.equal(spans[0].lane, "think")
    assert.ok(spans[0].text.includes("deliberate"))
})

test("patch parts contribute their file list", () => {
    const patched = {
        info: { id: "p1", role: "assistant", sessionID: "s1" },
        parts: [{ id: "p1", type: "patch", hash: "abc", files: ["src/a.js", "src/b.js"] }],
    }
    assert.ok(messageTokens(patched) > 0)
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
        assert.equal(st.triggerTokens, 400000)
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

test("rtr evict-tokens and evict-messages arm one-shots", async () => {
    const ctx = commandCtx()
    let output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "evict-tokens 200000" }, output, ctx)
    assert.equal(ctx.fileCfg().evictTokensNow, 200000)
    assert.match(output.parts[0].text, /armed/)
    output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "evict-messages 500" }, output, ctx)
    assert.equal(ctx.fileCfg().evictMessagesNow, 500)
    output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "evict-tokens abc" }, output, ctx)
    assert.match(output.parts[0].text, /refused/)
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
            { triggerTokens: 2000, targetTokens: 1500, maxKeepMessages: 40, cumulativeFile },
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

test("evicted markers leave the kept window and survive in the sink file", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-keeper-"))
    try {
        const hooks = await server(
            { directory: dir },
            { triggerTokens: 100, targetTokens: 40 },
        )
        const { messageText } = server._test
        const messages = [
            {
                info: { id: "u0", role: "user", sessionID: "s1" },
                parts: [{ id: "p", type: "text", text: "READ-OLD question" }],
            },
            {
                info: { id: "a0", role: "assistant", sessionID: "s1" },
                parts: [{ id: "p", type: "reasoning", text: "THINK-ONLY " + "deliberate ".repeat(100) }],
            },
            {
                info: { id: "a1", role: "assistant", sessionID: "s1" },
                parts: [
                    { id: "p1", type: "text", text: "WROTE-1 " + "word ".repeat(100) },
                    { id: "p2", type: "reasoning", text: "THINK-1 " + "deliberate ".repeat(100) },
                    { id: "p3", type: "tool", tool: "bash", state: { input: { q: "TOOLSTATE-1" }, output: "done" } },
                ],
            },
            {
                info: { id: "t1", role: "tool", sessionID: "s1" },
                parts: [{ id: "p", type: "text", text: "TOOLROLE-1 " + "word ".repeat(100) }],
            },
            {
                info: { id: "u3", role: "user", sessionID: "s1" },
                parts: [{ id: "p", type: "text", text: "READ-NEW latest" }],
            },
        ]
        const out = { messages }
        await hooks["experimental.chat.messages.transform"]({}, out)
        const keptTexts = out.messages.map(messageText)
        const { readdirSync } = await import("node:fs")
        const dtd = readdirSync(join(dir, ".opencode", "memory")).filter(
            (f) => f.endsWith(".dtd") && !f.includes("summary"),
        )
        assert.ok(dtd.length >= 1)
        const sunk = dtd
            .map((f) => readFileSync(join(dir, ".opencode", "memory", f), "utf8"))
            .join("\n")
        for (const marker of ["READ-OLD", "THINK-ONLY", "WROTE-1", "THINK-1", "TOOLSTATE-1", "TOOLROLE-1"]) {
            const inKept = keptTexts.some((t) => t.includes(marker))
            const inSunk = sunk.includes(marker)
            assert.equal(inKept, false, `${marker} still in kept window`)
            assert.equal(inSunk, true, `${marker} missing from sink`)
        }
        assert.ok(keptTexts.some((t) => t.includes("READ-NEW")))
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("rtr repair arms the repair flag", async () => {
    const ctx = commandCtx()
    const output = { parts: [] }
    await handleRtrCommand({ command: "rtr", sessionID: "s", arguments: "repair" }, output, ctx)
    assert.equal(ctx.fileCfg().repairNow, true)
    assert.match(output.parts[0].text, /repair requested/)
})

test("repair flag becomes a request file and clears itself", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-repair-"))
    try {
        const { mkdir } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(
            join(dir, ".opencode", "rtr-re-keeper.json"),
            JSON.stringify({ triggerTokens: 1000000, manual: true, repairNow: true }),
            "utf8",
        )
        const hooks = await server({ directory: dir }, {})
        const messages = [msg("user", "hello")]
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        assert.equal(messages.length, 1, "repair touches no window")
        const req = JSON.parse(
            readFileSync(join(dir, ".opencode", "rtr-re-repair.requested.json"), "utf8"),
        )
        assert.equal(req.source, "keeper-flag")
        const cfg = JSON.parse(
            readFileSync(join(dir, ".opencode", "rtr-re-keeper.json"), "utf8"),
        )
        assert.ok(!cfg.repairNow, "repair flag clears after requesting")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})
