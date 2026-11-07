// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// Framework tests (TODO-65): P1 prompt parser, P3 brief, P5 ESM.

import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test, expect } from "bun:test"
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

test("framework version is 1.1.0", () => {
    expect(FRAMEWORK_VERSION).toBe("1.1.0")
})

test("P1: parseRtrPrompt handles verbs, args and bare /rtr", () => {
    expect(parseRtrPrompt("/rtr status")).toEqual({ verb: "status", args: [] })
    expect(parseRtrPrompt("/rtr preset mugen")).toEqual({
        verb: "preset",
        args: ["mugen"],
    })
    expect(parseRtrPrompt("/rtr max 200")).toEqual({
        verb: "max",
        args: ["200"],
    })
    expect(parseRtrPrompt("/rtr")).toEqual({ verb: "", args: [] })
    expect(parseRtrPrompt("hello world")).toBeNull()
    expect(parseRtrPrompt("")).toBeNull()
    expect(PROMPT_RTR_RE.test("/RTR Status")).toBe(true)
})

test("P5: withTimeout resolves on success and rejects on timeout", async () => {
    const ok = await withTimeout(Promise.resolve(42), 1000, "test")
    expect(ok).toBe(42)
    await expect(
        withTimeout(new Promise(() => {}), 50, "hang"),
    ).rejects.toThrow(/timed out after 50ms/)
})

test("P5: laneCensus groups spans by lane via Object.groupBy", () => {
    const spans = [
        { lane: "read", tokens: 10 },
        { lane: "read", tokens: 20 },
        { lane: "write", tokens: 5 },
    ]
    const census = laneCensus(spans)
    expect(census).toHaveLength(2)
    const read = census.find((r) => r.lane === "read")
    expect(read).toEqual({ lane: "read", count: 2, tokens: 30 })
})

test("P5: nowIso returns an ISO instant", () => {
    const iso = nowIso()
    expect(iso).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
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
        expect(path).toBe(briefPath(dir))
        const text = require("node:fs").readFileSync(path, "utf8")
        expect(text).toContain("re-symbiose-mugen/rtr-full/t8/p80")
        expect(text).toContain("trigger: 400000 tokens")
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
        expect(data.schema).toBe("rtr.preset-registry/v2")
        writeFileSync(p, JSON.stringify({ schema: "other" }), "utf8")
        expect(() => loadPresetRegistryFrom(p)).toThrow(/unsupported schema/)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})
