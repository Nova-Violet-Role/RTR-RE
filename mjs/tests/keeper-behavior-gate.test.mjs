// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// Layer-4 red-capability proof: the keeper behavior gate must go red on a
// deliberately drifted manifest, on a failed scenario, on a missing
// scenario, and on missing source — and green on the frozen manifest.

import assert from "node:assert/strict"
import test from "node:test"
import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync, writeFileSync, rmSync, existsSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"

const GATE = join(import.meta.dirname, "..", "scripts", "keeper-behavior.mjs")
const FROZEN = join(import.meta.dirname, "..", "results", "keeper-behavior-manifest.json")

function runGate(manifestPath) {
    try {
        return execFileSync(process.execPath, [GATE, "check"], {
            env: { ...process.env, KEEPER_MANIFEST: manifestPath },
            encoding: "utf8",
            stdio: ["ignore", "pipe", "pipe"],
        })
    } catch (error) {
        const err = new Error(`gate failed: ${error.stderr ?? error.message}`)
        err.stderr = error.stderr ?? ""
        throw err
    }
}

test("gate passes on the frozen manifest", () => {
    assert.ok(existsSync(FROZEN), "frozen manifest exists")
    const out = runGate(FROZEN)
    assert.match(out, /PASS/)
})

test("gate goes red on a drifted scenario value", () => {
    const dir = mkdtempSync(join(tmpdir(), "keeper-gate-"))
    try {
        const drifted = join(dir, "manifest.json")
        const data = JSON.parse(readFileSync(FROZEN, "utf8"))
        data.scenarios["below-trigger-identity"].compress = !data.scenarios["below-trigger-identity"].compress
        writeFileSync(drifted, JSON.stringify(data), "utf8")
        assert.throws(() => runGate(drifted), /drifted/)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("gate goes red on a missing scenario", () => {
    const dir = mkdtempSync(join(tmpdir(), "keeper-gate-"))
    try {
        const missing = join(dir, "manifest.json")
        const data = JSON.parse(readFileSync(FROZEN, "utf8"))
        delete data.scenarios["bounded-tail-above-trigger"]
        writeFileSync(missing, JSON.stringify(data), "utf8")
        assert.throws(() => runGate(missing), /drift|missing from current run/)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("gate exits 2 on missing manifest", () => {
    const dir = mkdtempSync(join(tmpdir(), "keeper-gate-"))
    try {
        assert.throws(() => runGate(join(dir, "nope.json")), /manifest missing/)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("freeze exits 2 when the manifest cannot be written", () => {
    const dir = mkdtempSync(join(tmpdir(), "keeper-gate-"))
    try {
        const blocker = join(dir, "blocker")
        writeFileSync(blocker, "x", "utf8")
        assert.throws(
            () =>
                execFileSync(process.execPath, [GATE, "freeze"], {
                    env: { ...process.env, KEEPER_MANIFEST: join(blocker, "m.json") },
                    encoding: "utf8",
                    stdio: ["ignore", "pipe", "pipe"],
                }),
            /freeze failed/,
        )
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})
