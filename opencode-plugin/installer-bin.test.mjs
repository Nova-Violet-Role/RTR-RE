// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import assert from "node:assert/strict"
import test from "node:test"
import { execFileSync } from "node:child_process"
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"

function stageTree(launcherBody) {
    const dir = mkdtempSync(join(tmpdir(), "rtrre-installer-bin-"))
    const launchers = join(dir, "installer", "launchers")
    mkdirSync(launchers, { recursive: true })
    writeFileSync(join(launchers, "node_launcher.mjs"), launcherBody, "utf8")
    copyFileSync(new URL("./installer-bin.mjs", import.meta.url), join(dir, "installer-bin.mjs"))
    return dir
}

test("installer bin propagates the launcher exit code", () => {
    const dir = stageTree("process.exit(7)\n")
    try {
        assert.throws(
            () => execFileSync(process.execPath, [join(dir, "installer-bin.mjs")], { stdio: "pipe" }),
            (e) => e.status === 7,
        )
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("installer bin exits nonzero when the launcher dies on a signal", () => {
    const dir = stageTree("process.kill(process.pid, 'SIGTERM')\n")
    try {
        assert.throws(
            () => execFileSync(process.execPath, [join(dir, "installer-bin.mjs")], { stdio: "pipe" }),
            (e) => e.status !== 0,
        )
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("signal death (null code) maps to a failing exit, never success", async () => {
    const { installerExitCode } = await import("./installer-bin.mjs")
    assert.equal(installerExitCode(7), 7)
    assert.equal(installerExitCode(0), 0)
    assert.equal(installerExitCode(null), 1)
})
