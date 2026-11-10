// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// Bullet-proof: keeper-side end-to-end plus the cross-language relay
// contract (JS writes the pair Python's drain verifies).
import assert from "node:assert/strict"
import test from "node:test"
import { createRequire } from "node:module"
import { mkdtempSync, readFileSync, rmSync, readdirSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import server from "./rtr-re-keeper.js"

const require = createRequire(import.meta.url)
const core = require("../mjs/hooks/rtr-core.js")

function msg(role, text, extra = {}) {
    return {
        info: { id: `m-${Math.random()}`, role, sessionID: "s1", ...extra.info },
        parts: [{ id: "p1", type: "text", text }],
    }
}

test("full firing writes the relay-readable pair with matching digest", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-bp-"))
    try {
        const hooks = await server(
            { directory: dir },
            { triggerTokens: 100, targetTokens: 40 },
        )
        const messages = []
        for (let i = 0; i < 10; i++) messages.push(msg("assistant", "z".repeat(400)))
        messages.push(msg("user", "go"))
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const mem = join(dir, ".opencode", "memory")
        const files = readdirSync(mem)
        const sidecars = files.filter((f) => f.endsWith(".submit.json"))
        assert.equal(sidecars.length, 1)
        const stem = sidecars[0].slice(0, -".submit.json".length)
        const spansName = `${stem}.dtd`
        assert.ok(files.includes(spansName), "sibling spans share the digest")
        const sidecar = JSON.parse(readFileSync(join(mem, sidecars[0]), "utf8"))
        const body = readFileSync(join(mem, spansName), "utf8")
        // Relay contract: strict open count equals sidecar message count.
        const opens = body.match(/<span id="span-\d+"/g) || []
        assert.equal(opens.length, sidecar.messages.length)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("status plus sunk store carry the viewport and restart contracts", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-bp-"))
    try {
        const hooks = await server(
            { directory: dir },
            { triggerTokens: 100, targetTokens: 40 },
        )
        const messages = []
        for (let i = 0; i < 10; i++) messages.push(msg("assistant", "z".repeat(400)))
        messages.push(msg("user", "go"))
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        const status = JSON.parse(
            readFileSync(join(dir, ".opencode", "rtr-re-keeper-status.json"), "utf8"),
        )
        assert.equal(status.decision, "evicted")
        assert.ok(status.sinkPath)
        assert.equal(typeof status.debt, "number")
        assert.equal(typeof status.heapMB, "number")
        assert.equal(typeof status.cpuMs, "number")
        const sunk = JSON.parse(
            readFileSync(join(dir, ".opencode", "rtr-re-sunk.json"), "utf8"),
        )
        assert.ok(Array.isArray(sunk.digests))
        assert.ok(sunk.digests.length > 0)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("live control roundtrips through the watched config file", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-bp-"))
    try {
        const { mkdir, writeFile } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(
            join(dir, ".opencode", "rtr-re-keeper.json"),
            JSON.stringify({ triggerTokens: 1000000, targetTokens: 400 }),
            "utf8",
        )
        const hooks = await server({ directory: dir }, {})
        const messages = [msg("user", "hello " + "x".repeat(4000))]
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        // 1k-token window under the 1M file trigger: untouched identity.
        assert.equal(messages.length, 1)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("one-shot evict-tokens fires under trigger and clears itself", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-oneshot-"))
    try {
        const { mkdir, writeFile } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(
            join(dir, ".opencode", "rtr-re-keeper.json"),
            JSON.stringify({ triggerTokens: 1000000, evictTokensNow: 300 }),
            "utf8",
        )
        const hooks = await server({ directory: dir }, {})
        const messages = []
        for (let i = 0; i < 6; i++) messages.push(msg("assistant", "w".repeat(400)))
        messages.push(msg("user", "go"))
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        // ~700-token window, 300 evicted oldest-first despite the 1M trigger.
        assert.ok(messages.length < 7, `expected eviction, kept ${messages.length}`)
        const mem = join(dir, ".opencode", "memory")
        assert.ok(readdirSync(mem).some((f) => f.endsWith(".dtd")))
        const cfg = JSON.parse(
            readFileSync(join(dir, ".opencode", "rtr-re-keeper.json"), "utf8"),
        )
        assert.ok(!cfg.evictTokensNow, "one-shot flag clears after firing")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("one-shot evict-messages removes N oldest and clears itself", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-oneshot-"))
    try {
        const { mkdir, writeFile } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(
            join(dir, ".opencode", "rtr-re-keeper.json"),
            JSON.stringify({ triggerTokens: 1000000, evictMessagesNow: 3 }),
            "utf8",
        )
        const hooks = await server({ directory: dir }, {})
        const messages = []
        for (let i = 0; i < 6; i++) messages.push(msg("assistant", "w".repeat(400)))
        messages.push(msg("user", "go"))
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        assert.equal(messages.length, 4)
        const cfg = JSON.parse(
            readFileSync(join(dir, ".opencode", "rtr-re-keeper.json"), "utf8"),
        )
        assert.ok(!cfg.evictMessagesNow, "one-shot flag clears after firing")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("manual mode never auto-evicts but honors one-shots", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-manual-"))
    try {
        const { mkdir, writeFile } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(
            join(dir, ".opencode", "rtr-re-keeper.json"),
            JSON.stringify({ triggerTokens: 100, targetTokens: 40, manual: true }),
            "utf8",
        )
        const hooks = await server({ directory: dir }, {})
        const big = []
        for (let i = 0; i < 10; i++) big.push(msg("assistant", "w".repeat(4000)))
        big.push(msg("user", "go"))
        await hooks["experimental.chat.messages.transform"]({}, { messages: big })
        assert.equal(big.length, 11, "manual never auto-evicts")
        await writeFile(
            join(dir, ".opencode", "rtr-re-keeper.json"),
            JSON.stringify({
                triggerTokens: 100,
                targetTokens: 40,
                manual: true,
                evictMessagesNow: 4,
            }),
            "utf8",
        )
        const messages = []
        for (let i = 0; i < 6; i++) messages.push(msg("assistant", "w".repeat(400)))
        messages.push(msg("user", "go"))
        // Fresh server to pick up the edited flag deterministically.
        const hooks2 = await server({ directory: dir }, {})
        await hooks2["experimental.chat.messages.transform"]({}, { messages })
        assert.equal(messages.length, 3, "one-shot fires in manual mode")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("manual trims served sunk spans without new sinking", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-manual-trim-"))
    try {
        const { mkdir, writeFile } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode"), { recursive: true })
        await writeFile(
            join(dir, ".opencode", "rtr-re-keeper.json"),
            JSON.stringify({ triggerTokens: 1000000, manual: true }),
            "utf8",
        )
        const { spanDigest, messageText } = server._test
        const messages = [
            msg("assistant", "sunk-old-one here"),
            msg("assistant", "sunk-old-two here"),
            msg("assistant", "fresh middle here"),
            msg("assistant", "fresh recent here"),
            msg("user", "go"),
        ]
        const digests = [spanDigest(messageText(messages[0])), spanDigest(messageText(messages[1]))]
        await writeFile(
            join(dir, ".opencode", "rtr-re-sunk.json"),
            JSON.stringify({ v: 1, digests, debt: 0 }),
            "utf8",
        )
        const hooks = await server({ directory: dir }, {})
        await hooks["experimental.chat.messages.transform"]({}, { messages })
        assert.equal(messages.length, 3, "served sunk spans leave the window")
        assert.ok(!messages.some((m) => messageText(m).includes("sunk-old")))
        const status = JSON.parse(
            readFileSync(join(dir, ".opencode", "rtr-re-keeper-status.json"), "utf8"),
        )
        assert.equal(status.decision, "manual-trimmed")
        assert.ok(status.total > 0, "manual reports the real window")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("mjs bridge builds the live-loop CLI shapes", () => {
    assert.deepEqual(
        core.buildCliArgs("symbiose-drain", { project: "demo", limit: 5 }),
        ["symbiose-drain", "demo", "--limit", "5"],
    )
    assert.deepEqual(core.buildCliArgs("index", { force: false, project: "demo" }), [
        "index",
        "--project",
        "demo",
    ])
    assert.throws(() => core.buildCliArgs("nope", {}), /nope/)
})
