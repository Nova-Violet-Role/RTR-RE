// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import assert from "node:assert/strict"
import test from "node:test"
import { execFileSync } from "node:child_process"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { mkdtempSync, rmSync, writeFileSync, readFileSync } from "node:fs"
import { parseArgs, planFor, executePlan, linuxPlayerCmd, whichSync, animateParams, readScene, validatedInt, windowsMediaCommand } from "../installer/launchers/node_launcher.mjs"

const LAUNCHER = join(import.meta.dirname, "..", "installer", "launchers", "node_launcher.mjs")

test("node launcher refuses unknown themes by name", () => {
    assert.throws(() => parseArgs(["--theme", "bogus"], {}), /unknown theme bogus/)
})

test("node launcher exits 2 on unknown theme", () => {
    assert.throws(
        () => execFileSync(process.execPath, [LAUNCHER, "--theme", "bogus"], { encoding: "utf8" }),
        (e) => e.status === 2,
    )
})

test("node planFor mirrors the Python quick plan", () => {
    assert.deepEqual(planFor({ preset: "quick" }), [
        ["preset", "re-symbiose-mugen (400k/200k/200)"],
        ["engine", "rtr-full · dual-ONNX"],
        ["profile", "local-system · T8/P80"],
        ["plugin", "keeper + ctrl+p palette"],
        ["memory", ".opencode/memory/ (DTD-shaped)"],
    ])
})

test("node executePlan writes the keeper config", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-nodeexec-"))
    try {
        const ok = await executePlan({ preset: "quick" }, join(dir, "proj"), null)
        assert.equal(ok, true)
        const cfg = JSON.parse(readFileSync(join(dir, "proj", ".opencode", "rtr-re-keeper.json"), "utf8"))
        assert.equal(cfg.preset, "re-symbiose-mugen")
        assert.equal(cfg.cpuProfile, "local-system")
        assert.equal(cfg.enabled, true)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("node executePlan reports npm failure", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-nodeexec-"))
    try {
        const junk = join(dir, "bogus.tgz")
        writeFileSync(junk, "not a tarball", "utf8")
        const ok = await executePlan({ preset: "quick" }, join(dir, "proj"), junk)
        assert.equal(ok, false)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("linux player chain prefers mpg123, then mpv, then ffplay", () => {
    assert.equal(linuxPlayerCmd("x.mp3", () => "/usr/bin/x")[0], "mpg123")
    assert.deepEqual(linuxPlayerCmd("x.mp3", (n) => (n === "mpv" ? "/usr/bin/mpv" : null)), ["mpv", "--no-video", "x.mp3"])
    assert.equal(linuxPlayerCmd("x.mp3", () => null), null)
})

test("whichSync finds binaries on PATH and misses cleanly", () => {
    assert.ok(whichSync("node"))
    assert.equal(whichSync("definitely-not-a-binary-xyz"), null)
})

test("animate params follow the declared scene, degenerate falls back", () => {
    const p = animateParams({ particles: { count: 900, speed: 0.6, mix: 0.6 } })
    assert.ok(Math.abs(p.density - 0.06) < 1e-9)
    assert.ok(Math.abs(p.sleep - 1 / 12) < 1e-9)
    assert.equal(p.ratio, 0.6)
    const d = animateParams({})
    assert.ok(Math.abs(d.density - 0.06) < 1e-9)
    const g = animateParams({ particles: { count: "xx", speed: NaN, mix: null } })
    assert.ok(Math.abs(g.density - 0.06) < 1e-9)
    assert.ok(Math.abs(g.sleep - 1 / 12) < 1e-9)
    assert.equal(g.ratio, 0.6)
})

test("node quick flow completes and writes config", () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-nodee2e-"))
    try {
        const project = join(dir, "proj")
        execFileSync(process.execPath, [LAUNCHER, "--project", project], {
            input: "1\ny\n\n\n",
            encoding: "utf8",
            stdio: ["pipe", "pipe", "pipe"],
            env: { ...process.env, RTRRE_INSTALL_NO_AUDIO: "1" },
            timeout: 120000,
        })
        const cfg = JSON.parse(readFileSync(join(project, ".opencode", "rtr-re-keeper.json"), "utf8"))
        assert.equal(cfg.preset, "re-symbiose-mugen")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("node manual flow shows guide and writes roomy bounds plus guide copy", () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-nodee2e-"))
    try {
        const project = join(dir, "proj")
        const out = execFileSync(process.execPath, [LAUNCHER, "--project", project], {
            input: "4\n\n\ny\nn\n\n",
            encoding: "utf8",
            stdio: ["pipe", "pipe", "pipe"],
            env: { ...process.env, RTRRE_INSTALL_NO_AUDIO: "1" },
            timeout: 120000,
        })
        assert.match(out, /palette guide for professional manual context care/)
        const cfg = JSON.parse(readFileSync(join(project, ".opencode", "rtr-re-keeper.json"), "utf8"))
        assert.equal(cfg.manual, true)
        assert.equal(cfg.threadsPerModel, 8)
        assert.equal(cfg.parkingPercent, 60)
        const guide = readFileSync(join(project, ".opencode", "memory", "rtrre-palette-guide.txt"), "utf8")
        assert.match(guide, /evict-tokens/)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("node theme falls back through both env names", () => {
    assert.equal(parseArgs([], { RTRRE_THEME: "forge" }).theme, "forge")
    assert.equal(parseArgs([], { RTRRE_INSTALL_THEME: "instrument", RTRRE_THEME: "forge" }).theme, "instrument")
    assert.equal(parseArgs([], {}).theme, "network")
})

test("node readScene falls back on missing or broken scenes", () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-scene-"))
    try {
        assert.deepEqual(readScene("nope", dir), {})
        writeFileSync(join(dir, "bad.xml"), '<scene version="1.0" theme="bad"><camera drift="xx"/><core/></scene>', "utf8")
        const scene = readScene("bad", dir)
        assert.equal(scene.camera.drift, 0.0012)
        assert.equal(scene.camera.pitch, -0.16)
        writeFileSync(join(dir, "pitched.xml"), '<scene version="1.0" theme="pitched"><camera pitch="0.5"/><core/></scene>', "utf8")
        assert.equal(readScene("pitched", dir).camera.pitch, 0.5)
        assert.deepEqual(scene.core.glow, [128, 128, 255])
        assert.equal(scene.particles.speed, 0.6)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("node validatedInt gates empty, ints, garbage and range", () => {
    assert.deepEqual(validatedInt("", 8, 1, 64), [true, 8])
    assert.deepEqual(validatedInt("12", 8, 1, 64), [true, 12])
    assert.deepEqual(validatedInt("abc", 8, 1, 64), [false, null])
    assert.deepEqual(validatedInt("99", 8, 1, 64), [false, null])
})

test("node hardcore flow retries then completes", () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-nodee2e-"))
    try {
        const project = join(dir, "proj")
        const out = execFileSync(process.execPath, [LAUNCHER, "--project", project], {
            input: "3\nabc\n8\nxx\n40\n\n\n700000\n350000\n250\ny\n\n\n",
            encoding: "utf8",
            stdio: ["pipe", "pipe", "pipe"],
            env: { ...process.env, RTRRE_INSTALL_NO_AUDIO: "1" },
            timeout: 120000,
        })
        assert.ok(out.split("whole number").length - 1 >= 2)
        const cfg = JSON.parse(readFileSync(join(project, ".opencode", "rtr-re-keeper.json"), "utf8"))
        assert.equal(cfg.preset, "re-symbiose-mugen")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("node hardcore flow writes chosen values", () => {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-nodee2e-"))
    try {
        const project = join(dir, "proj")
        const out = execFileSync(process.execPath, [LAUNCHER, "--project", project], {
            input: "3\n16\n60\nwide\nrtr-bge\n700000\n350000\n250\ny\n\n\n",
            encoding: "utf8",
            stdio: ["pipe", "pipe", "pipe"],
            env: { ...process.env, RTRRE_INSTALL_NO_AUDIO: "1" },
            timeout: 120000,
        })
        assert.ok(out.includes("RTR-RE installed"))
        const cfg = JSON.parse(readFileSync(join(project, ".opencode", "rtr-re-keeper.json"), "utf8"))
        assert.equal(cfg.preset, "wide")
        assert.equal(cfg.threadsPerModel, 16)
        assert.equal(cfg.parkingPercent, 60)
        assert.equal(cfg.modality, "rtr-bge")
        assert.equal(cfg.triggerTokens, 700000)
        assert.equal(cfg.targetTokens, 350000)
        assert.equal(cfg.maxKeepMessages, 250)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("node windows command keeps host alive for track", () => {
    const cmd = windowsMediaCommand("C:/x/obsession-quick.mp3")
    assert.ok(cmd.includes("WMPlayer.OCX"))
    assert.ok(cmd.includes("playState"))
    assert.ok(cmd.includes("C:/x/obsession-quick.mp3"))
})
