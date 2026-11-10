// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// Framework tests (TODO-65): P1 prompt parser, P3 brief, P5 ESM.
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import assert from "node:assert/strict"
import {
    FRAMEWORK_VERSION,
    PROMPT_RTR_RE,
    briefPath,
    laneCensus,
    loadPresetRegistryFrom,
    nowIso,
    parseRtrPrompt,
    resolveRegistryPath,
    withTimeout,
    writeSubagentBrief,
} from "../framework/rtr-keeper-framework.mjs"

test("framework version is 1.2.0", () => {
    assert.strictEqual(FRAMEWORK_VERSION, "1.2.0")
})

test("P1: parseRtrPrompt handles verbs, args and bare /rtr", () => {
    assert.deepStrictEqual(parseRtrPrompt("/rtr status"), { verb: "status", args: [] })
    assert.deepStrictEqual(parseRtrPrompt("/rtr preset mugen"), {
        verb: "preset",
        args: ["mugen"],
    })
    assert.deepStrictEqual(parseRtrPrompt("/rtr max 200"), {
        verb: "max",
        args: ["200"],
    })
    assert.deepStrictEqual(parseRtrPrompt("/rtr"), { verb: "", args: [] })
    assert.strictEqual(parseRtrPrompt("hello world"), null)
    assert.strictEqual(parseRtrPrompt(""), null)
    assert.strictEqual(PROMPT_RTR_RE.test("/RTR Status"), true)
})

test("P5: withTimeout resolves on success and rejects on timeout", async () => {
    const ok = await withTimeout(Promise.resolve(42), 1000, "test")
    assert.strictEqual(ok, 42)
    await assert.rejects(
        withTimeout(new Promise(() => {}), 50, "hang"),
        /timed out after 50ms/,
    )
})

test("P5: laneCensus groups spans by lane via Object.groupBy", () => {
    const spans = [
        { lane: "read", tokens: 10 },
        { lane: "read", tokens: 20 },
        { lane: "write", tokens: 5 },
    ]
    const census = laneCensus(spans)
    assert.strictEqual(census.length, 2)
    const read = census.find((r) => r.lane === "read")
    assert.deepStrictEqual(read, { lane: "read", count: 2, tokens: 30 })
})

test("P5: nowIso returns an ISO instant", () => {
    const iso = nowIso()
    assert.match(iso, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
})

test("P3: writeSubagentBrief writes the shared brief", () => {
    const dir = mkdtempSync(join(tmpdir(), "rtr-fw-"))
    try {
        const cfg = {
            profileCode: "re-symbiose-mugen/rtr-full/t8/p80",
            enabled: true,
            triggerTokens: 400000,
            targetTokens: 200000,
            maxKeepMessages: 200,
        }
        const path = writeSubagentBrief(dir, cfg, null)
        assert.strictEqual(path, briefPath(dir))
        const text = readFileSync(path, "utf8")
        assert.ok(text.includes("re-symbiose-mugen/rtr-full/t8/p80"))
        assert.ok(text.includes("trigger: 400000 tokens"))
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("registry loading validates schema and records the path", () => {
    const dir = mkdtempSync(join(tmpdir(), "rtr-fw-"))
    try {
        const p = join(dir, "registry.json")
        writeFileSync(p, JSON.stringify({ schema: "rtr.preset-registry/v2" }), "utf8")
        const data = loadPresetRegistryFrom(p)
        assert.strictEqual(data.schema, "rtr.preset-registry/v2")
        writeFileSync(p, JSON.stringify({ schema: "other" }), "utf8")
        assert.throws(() => loadPresetRegistryFrom(p), /unsupported schema/)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})
