// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import assert from "node:assert/strict"
import test, { before, after } from "node:test"
import { createRequire } from "node:module"
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"

const require = createRequire(import.meta.url)

// Isolate the OpenCode off-flag: the plugin reads XDG_CONFIG_HOME at import.
const cfgHome = mkdtempSync(join(tmpdir(), "rtr-mjs-test-"))
process.env.XDG_CONFIG_HOME = cfgHome
const flagPath = join(cfgHome, "opencode", ".rtr-off")
mkdirSync(join(cfgHome, "opencode"), { recursive: true })
writeFileSync(flagPath, "") // stale "off" from a previous session

const core = require("../hooks/rtr-core.js")
const plugin = (await import("../.opencode/plugins/rtr.mjs")).default

after(() => rmSync(cfgHome, { recursive: true, force: true }))

test("mode starts on: loading the plugin clears a stale off flag", async () => {
    await plugin({})
    assert.equal(existsSync(flagPath), false)
})

test("toggle phrases must be the whole prompt, never a sentence inside one", () => {
    assert.ok(core.DEACTIVATE.test("/rtr off"))
    assert.ok(core.DEACTIVATE.test("stop rtr"))
    assert.ok(!core.DEACTIVATE.test("please stop rtr now and keep going"))
    assert.ok(core.REACTIVATE.test("/rtr"))
    assert.ok(core.REACTIVATE.test("/rtr on"))
    assert.ok(!core.REACTIVATE.test("the /rtr command is neat"))
})

test("instructions name the mode, the memory loop, and auto-optimize", () => {
    const body = core.getInstructions()
    assert.ok(body.startsWith("RTR-RE MODE ACTIVE"))
    assert.match(body, /AUTO-OPTIMIZE/)
    assert.match(body, /rtr-cli/)
})

test("reminder is one short line, never the full ruleset again", () => {
    const r = core.getReminder()
    assert.ok(!r.includes("\n"))
    assert.ok(r.length < 220)
    assert.match(r, /RTR-RE MODE ACTIVE/)
})

test("auto-optimize: first read after start earns one note, second read stays silent, a write re-arms", () => {
    const auto = core.createAutoOptimizer()
    const first = auto.noteForToolAfter("read")
    assert.match(first ?? "", /AUTO-OPTIMIZE/)
    assert.equal(auto.noteForToolAfter("read"), null)
    assert.equal(auto.noteForToolAfter("bash"), null)
    assert.equal(auto.noteForToolAfter("edit"), null)
    const rearmed = auto.noteForToolAfter("read")
    assert.match(rearmed ?? "", /AUTO-OPTIMIZE/)
})

test("auto-optimize: a write with no read before it earns no note", () => {
    const auto = core.createAutoOptimizer()
    assert.equal(auto.noteForToolAfter("write"), null)
    assert.equal(auto.noteForToolAfter("bash"), null)
})

test("context plan keeps verbatim below the trigger and evicts above it", () => {
    const under = core.planContext(100000, 50)
    assert.equal(under.triggerTokens, 400000)
    assert.equal(under.targetTokens, 200000)
    assert.equal(under.maxKeepMessages, 200)
    assert.match(under.decision, /keep verbatim/)
    const over = core.planContext(500000, 90)
    assert.match(over.decision, /evict/)
})

test("context plan boundary matches Python: exactly at trigger keeps verbatim", () => {
    const at = core.planContext(400000, 90)
    assert.match(at.decision, /keep verbatim/)
})

test("standalone fallback defaults mirror the shipped registry default (mugen)", () => {
    assert.deepEqual(core.PLAN_DEFAULTS, {
        triggerTokens: 400000,
        targetTokens: 200000,
        maxKeepMessages: 200,
        maxSummaryChars: 20000,
        maxRestoreChars: 4000,
    })
})

test("context plan defaults come from the shared preset registry, not hardcoded values", () => {
    const reg = core.registryContextProfile()
    assert.ok(reg)
    assert.equal(reg.preset, "re-symbiose-mugen")
    assert.equal(reg.triggerTokens, 400000)
    assert.equal(reg.targetTokens, 200000)
    assert.equal(reg.maxKeepMessages, 200)
    assert.equal(reg.cpuProfile, "public-default")
    assert.equal(reg.modality, "rtr-full")
    assert.equal(reg.threadsPerModel, 4)
    assert.equal(reg.parkingPercent, 60)
    assert.equal(reg.hybrid, true)
    assert.equal(reg.expansion, true)
})

test("optimizer note carries the resolved profile numbers when a provider is present", () => {
    const note = core.buildOptimizeNote(core.registryContextProfile())
    assert.match(note, /AUTO-OPTIMIZE/)
    assert.match(note, /Re-Symbiose-Mugen/)
    assert.match(note, /400000\/200000\/200/)
    assert.match(note, /RTR-FULL/)
    assert.match(note, /T4\/P60/)
    assert.match(note, /hybrid=true expansion=true/)
})

test("optimizer with provider emits the data-rich note; without it, the static fallback", () => {
    const withProvider = core.createAutoOptimizer({
        getContext: () => core.registryContextProfile(),
    })
    const rich = withProvider.noteForToolAfter("read")
    assert.match(rich ?? "", /AUTO-OPTIMIZE/)
    assert.match(rich ?? "", /Re-Symbiose-Mugen/)

    const plain = core.createAutoOptimizer()
    const fallback = plain.noteForToolAfter("read")
    assert.match(fallback ?? "", /AUTO-OPTIMIZE/)
    assert.ok(!(fallback ?? "").includes("Re-Symbiose-Mugen"))
})

test("cli bridge builds measured rtr-cli arguments and refuses unknown commands by name", () => {
    assert.deepEqual(
        core.buildCliArgs("search", { query: "piper tts", k: 2, project: "demo" }),
        ["search", "piper tts", "--k", "2", "--project", "demo"],
    )
    assert.deepEqual(
        core.buildCliArgs("search", { query: "x", denseOnly: true }),
        ["search", "x", "--dense-only"],
    )
    assert.deepEqual(core.buildCliArgs("stats", {}), ["stats"])
    assert.deepEqual(
        core.buildCliArgs("index", { force: true, project: "demo" }),
        ["index", "--force", "--project", "demo"],
    )
    assert.deepEqual(
        core.buildCliArgs("write", { project: "p", filename: "f", content: "c" }),
        ["write", "p", "f", "c"],
    )
    assert.deepEqual(core.buildCliArgs("janitor", { dryRun: true }), ["janitor", "--dry-run"])
    assert.deepEqual(
        core.buildCliArgs("session-commit", { project: "demo" }),
        ["session-commit", "demo"],
    )
    assert.deepEqual(
        core.buildCliArgs("session-commit", { project: "demo", chat: "did x" }),
        ["session-commit", "demo", "--chat", "did x"],
    )
    assert.deepEqual(
        core.buildCliArgs("symbiose-submit", { project: "demo", messagesJson: "[{}]" }),
        ["symbiose-submit", "demo", "[{}]"],
    )
    assert.deepEqual(
        core.buildCliArgs("symbiose-drain", { project: "demo", limit: 2 }),
        ["symbiose-drain", "demo", "--limit", "2"],
    )
    assert.deepEqual(
        core.buildCliArgs("symbiose-compress", { project: "demo", target: 50, messagesFile: "m.json" }),
        ["symbiose-compress", "demo", "50", "--messages-file", "m.json"],
    )
    assert.deepEqual(
        core.buildCliArgs("context-plan", { totalTokens: 10, messageCount: 2 }),
        ["context-plan", "10", "2"],
    )
    assert.deepEqual(
        core.buildCliArgs("keeper-evict-now", { project: "demo", tokens: 200000 }),
        ["keeper-evict-now", "demo", "--tokens", "200000"],
    )
    assert.throws(() => core.buildCliArgs("nope", {}), /nope/)
})

test("system transform appends the ruleset when on and stays silent when off", async () => {
    const hooks = await plugin({})
    const out1 = { system: ["base"] }
    await hooks["experimental.chat.system.transform"]({}, out1)
    assert.match(out1.system[0], /RTR-RE MODE ACTIVE/)

    writeFileSync(flagPath, "")
    const out2 = { system: ["base"] }
    await hooks["experimental.chat.system.transform"]({}, out2)
    assert.equal(out2.system[0], "base")
    rmSync(flagPath, { force: true })
})

test("tool hook appends the auto-optimize note after a read, once per read-write cycle", async () => {
    const hooks = await plugin({})
    const readOut = { output: "file body" }
    await hooks["tool.execute.after"]({ tool: "read", args: { filePath: "a.py" } }, readOut)
    assert.match(readOut.output, /AUTO-OPTIMIZE/)

    const readOut2 = { output: "more body" }
    await hooks["tool.execute.after"]({ tool: "read", args: { filePath: "b.py" } }, readOut2)
    assert.equal(readOut2.output, "more body")

    const writeOut = { output: "ok" }
    await hooks["tool.execute.after"]({ tool: "edit", args: { filePath: "a.py" } }, writeOut)
    const readOut3 = { output: "again" }
    await hooks["tool.execute.after"]({ tool: "read", args: { filePath: "a.py" } }, readOut3)
    assert.match(readOut3.output, /AUTO-OPTIMIZE/)
})

test("/rtr off writes the flag and /rtr on removes it", async () => {
    const hooks = await plugin({})
    await hooks["command.execute.before"]({ command: "rtr", arguments: "off" })
    assert.equal(existsSync(flagPath), true)
    await hooks["command.execute.before"]({ command: "rtr", arguments: "on" })
    assert.equal(existsSync(flagPath), false)
})

test("AGENTS.md is the skill body verbatim (regenerate after skill edits)", () => {
    const skill = readFileSync(new URL("../skills/rtr/SKILL.md", import.meta.url), "utf8")
    const body = skill.replace(/^---[\s\S]*?\n---\s*/, "").trim()
    const agents = readFileSync(new URL("../AGENTS.md", import.meta.url), "utf8").trim()
    assert.equal(agents, body)
})

test("plugin registers the rtr command from the command directory", async () => {
    const hooks = await plugin({})
    const config = {}
    await hooks.config(config)
    assert.ok(config.command?.rtr?.template)
    assert.ok(config.command?.rtr?.description)
})

test("optimizer recommendation is machine-aware and grounded in the measured axis", () => {
    const high = core.recommendProfile({}, 32)
    const mid = core.recommendProfile({}, 8)
    const low = core.recommendProfile({}, 4)
    assert.match(high.line, /Saimonokuma: T8 \+ P40/)
    assert.match(mid.line, /T4 \+ P40/)
    assert.match(low.line, /T2 \+ P20/)
    assert.match(low.line, /SSD mitigates RAM/)
    const note = core.buildOptimizeNote({
        preset: "re-symbiose-mugen",
        presetDisplay: "Re-Symbiose-Mugen",
        triggerTokens: 400000,
        targetTokens: 200000,
        maxKeepMessages: 200,
        modality: "rtr-full",
        threadsPerModel: 8,
        parkingPercent: 40,
        hybrid: true,
        expansion: true,
        logicalProcessors: 32,
    })
    assert.ok(note.includes("Re-Symbiose-Mugen (400000/200000/200)"))
    assert.ok(note.includes("Recommended from Saimonokuma"))
    assert.ok(note.includes("Did you know"))
})

before(() => {})
