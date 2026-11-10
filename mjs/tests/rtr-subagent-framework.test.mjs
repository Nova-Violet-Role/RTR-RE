// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// Subagent framework tests (TODO-65 P3): spawn, tracking, idle, prune.
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import assert from "node:assert/strict"
import {
    SUBAGENT_TITLE_PREFIX,
    instantNowIso,
    isTrackedIdle,
    loadMappings,
    makeIdleHandler,
    msSince,
    pruneStaleMappings,
    recordFork,
    spawnSubagent,
    spawnSubagentWithRetry,
    storagePaths,
    trackedForkIds,
} from "../framework/rtr-subagent-framework.mjs"

function mockClient(over = {}) {
    const calls = { fork: 0, promptAsync: 0, update: 0, get: 0 }
    const state = {
        forkedIds: ["fork-1", "fork-2"],
        forkCount: 0,
        deletedIds: new Set(),
        titles: {},
    }
    return {
        calls,
        state,
        session: {
            fork: async ({ path, throwOnError }) => {
                calls.fork += 1
                if (over.forkFails) throw new Error("fork failed")
                const id = state.forkedIds[state.forkCount++]
                return { data: { id } }
            },
            get: async ({ path }) => {
                calls.get += 1
                return { data: { id: path.id, title: state.titles[path.id] ?? "Parent Task" } }
            },
            update: async ({ path, body }) => {
                calls.update += 1
                state.titles[path.id] = body.title
                return { data: { id: path.id } }
            },
            promptAsync: async ({ path, body }) => {
                calls.promptAsync += 1
                if (state.deletedIds.has(path.id)) {
                    const err = new Error("session not found")
                    err.status = 404
                    throw err
                }
                state.lastPrompt = body.parts[0].text
                return { data: { id: path.id } }
            },
        },
    }
}

test("spawnSubagent forks, titles, prompts and records the mapping", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtr-sa-"))
    try {
        const client = mockClient()
        const id = await spawnSubagent(client, "parent-1", "do the thing", {
            projectDir: dir,
            briefText: "# RTR-RE Keeper brief",
        })
        assert.strictEqual(id, "fork-1")
        assert.strictEqual(client.calls.fork, 1)
        assert.strictEqual(client.calls.promptAsync, 1)
        assert.strictEqual(client.state.titles["fork-1"], `${SUBAGENT_TITLE_PREFIX}Parent Task`)
        assert.ok(client.state.lastPrompt.includes("# RTR-RE Keeper brief"))
        assert.ok(client.state.lastPrompt.includes("do the thing"))
        const mappings = await loadMappings(dir)
        assert.strictEqual(mappings.length, 1)
        assert.strictEqual(mappings[0].parentSessionID, "parent-1")
        assert.strictEqual(mappings[0].forkedSessionID, "fork-1")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("spawnSubagentWithRetry re-forks when the fork vanished", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtr-sa-"))
    try {
        const client = mockClient()
        client.state.deletedIds.add("fork-1")
        const id = await spawnSubagentWithRetry(client, "parent-1", "again", {
            projectDir: dir,
        })
        assert.strictEqual(id, "fork-2")
        assert.strictEqual(client.calls.fork, 2)
        assert.strictEqual(client.calls.promptAsync, 2)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("spawnSubagent returns the fork id when mapping persistence fails", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtr-sa-"))
    try {
        const blocker = join(dir, "blocker")
        await (await import("node:fs/promises")).writeFile(blocker, "x", "utf8")
        const client = mockClient()
        const id = await spawnSubagent(client, "parent-1", "again", {
            projectDir: blocker,
        })
        assert.strictEqual(id, "fork-1")
        assert.strictEqual(client.calls.promptAsync, 1)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("isTrackedIdle recognizes tracked fork idles only", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtr-sa-"))
    try {
        await recordFork(dir, "parent-1", "fork-9", "p")
        assert.strictEqual(await isTrackedIdle({ type: "session.idle", properties: { sessionID: "fork-9" } }, dir), true)
        assert.strictEqual(await isTrackedIdle({ type: "session.idle", properties: { sessionID: "other" } }, dir), false)
        assert.strictEqual(await isTrackedIdle({ type: "session.updated", properties: { sessionID: "fork-9" } }, dir), false)
        assert.strictEqual(await isTrackedIdle({}, dir), false)
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("makeIdleHandler fires onComplete for a tracked fork", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtr-sa-"))
    try {
        await recordFork(dir, "parent-1", "fork-9", "p")
        const client = mockClient()
        client.state.titles["fork-9"] = `${SUBAGENT_TITLE_PREFIX}Parent Task`
        let completed = null
        const handler = makeIdleHandler(client, dir, (info) => {
            completed = info
        })
        await handler({ event: { type: "session.idle", properties: { sessionID: "fork-9" } } })
        assert.notStrictEqual(completed, null)
        assert.strictEqual(completed.sessionID, "fork-9")
        assert.strictEqual(completed.title, "Parent Task")
        await handler({ event: { type: "session.idle", properties: { sessionID: "other" } } })
        assert.strictEqual(completed.sessionID, "fork-9") // unchanged
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})

test("pruneStaleMappings drops old mappings using duration arithmetic", async () => {
    const dir = mkdtempSync(join(tmpdir(), "rtr-sa-"))
    try {
        const old = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString()
        const fresh = instantNowIso()
        assert.ok(msSince(fresh) < 1000)
        const mappings = [
            { parentSessionID: "p-old", forkedSessionID: "f-old", createdAt: old, lastUsedAt: old },
            { parentSessionID: "p-fresh", forkedSessionID: "f-fresh", createdAt: fresh, lastUsedAt: fresh },
        ]
        const { file } = storagePaths(dir)
        const { mkdir } = await import("node:fs/promises")
        await mkdir(join(dir, ".opencode", "subagents"), { recursive: true })
        await (await import("node:fs/promises")).writeFile(file, JSON.stringify(mappings), "utf8")
        const pruned = await pruneStaleMappings(dir)
        assert.strictEqual(pruned, 1)
        const remaining = await loadMappings(dir)
        assert.strictEqual(remaining.length, 1)
        assert.strictEqual(remaining[0].forkedSessionID, "f-fresh")
    } finally {
        rmSync(dir, { recursive: true, force: true })
    }
})
