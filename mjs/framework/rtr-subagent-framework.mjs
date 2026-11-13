// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// RTR-RE:Symbiose subagent framework — a subagent spawn hook re-created
// from zero (TODO-65 P3). The host has no subagent hook; the mechanism is
// built on the SDK primitives the btw-opencode plugin proved:
//   session.fork       spawn a child session that inherits the parent's
//                      conversation (the "same context session as a
//                      subagent would")
//   session.promptAsync send a prompt to the fork in the background
//   session.idle event  the fork's completion signal
//   session.messages     read context from any session
// Grounded in the ECMAScript sources (read whole, 2026-11-07):
//   ES2024 Object.groupBy, Promise.withResolvers
//   ES2025 Temporal (Instant/Duration), iterator helpers
//   (map/filter/take/drop/flatMap/reduce/toArray/forEach/some/every),
//   Set methods (union/intersection/difference/symmetricDifference/
//   isSubsetOf/isSupersetOf/isDisjointFrom)

import { homedir } from "node:os"
import { join } from "node:path"
import { readFile, writeFile, mkdir } from "node:fs/promises"
import { existsSync } from "node:fs"

export const SUBAGENT_VERSION = "1.2.2"
export const SUBAGENT_TITLE_PREFIX = "#RTR-SUBAGENT "
export const STALE_AFTER_MS = 24 * 60 * 60 * 1000 // 24h (Temporal.Duration)

// Temporal is ES2025 and present in Node 26, but not yet in every runtime
// (Bun 1.3.14). These helpers use Temporal when available and fall back to
// Date otherwise, so the framework runs on both.
export function instantNowIso() {
    if (typeof Temporal !== "undefined" && Temporal.Now?.instant) {
        return Temporal.Now.instant().toString()
    }
    return new Date().toISOString()
}

export function msSince(iso) {
    if (typeof Temporal !== "undefined" && Temporal.Instant) {
        return Temporal.Duration.from(
            Temporal.Now.instant().since(Temporal.Instant.from(iso)),
        ).total("milliseconds")
    }
    return Date.now() - new Date(iso).getTime()
}

// --- Storage (mirrors btw-opencode storage.ts, project-scoped) ------------

export function storagePaths(projectDir) {
    const dir = join(projectDir, ".opencode", "subagents")
    return { dir, file: join(dir, "mappings.json") }
}

export async function loadMappings(projectDir) {
    const { file } = storagePaths(projectDir)
    if (!existsSync(file)) return []
    try {
        const data = JSON.parse(await readFile(file, "utf8"))
        return Array.isArray(data) ? data : []
    } catch {
        return []
    }
}

export async function saveMappings(projectDir, mappings) {
    const { dir, file } = storagePaths(projectDir)
    await mkdir(dir, { recursive: true })
    await writeFile(file, JSON.stringify(mappings, null, 2) + "\n", "utf8")
}

export async function recordFork(projectDir, parentSessionID, forkedSessionID, prompt) {
    const mappings = await loadMappings(projectDir)
    const now = instantNowIso()
    const existing = mappings.findIndex((m) => m.parentSessionID === parentSessionID)
    const entry = {
        parentSessionID,
        forkedSessionID,
        prompt: prompt.slice(0, 200),
        createdAt: existing >= 0 ? mappings[existing].createdAt : now,
        lastUsedAt: now,
    }
    if (existing >= 0) mappings[existing] = entry
    else mappings.push(entry)
    await saveMappings(projectDir, mappings)
    return entry
}

export async function trackedForkIds(projectDir) {
    const mappings = await loadMappings(projectDir)
    return new Set(mappings.map((m) => m.forkedSessionID))
}

/**
 * ES2025 Set methods + Temporal.Duration: prune mappings whose last use
 * is older than STALE_AFTER_MS. Returns the pruned mapping count.
 */
export async function pruneStaleMappings(projectDir) {
    const mappings = await loadMappings(projectDir)
    if (!mappings.length) return 0
    const stale = new Set(
        mappings
            .filter((m) => msSince(m.lastUsedAt) > STALE_AFTER_MS)
            .map((m) => m.forkedSessionID),
    )
    if (!stale.size) return 0
    const fresh = mappings.filter((m) => !stale.has(m.forkedSessionID))
    await saveMappings(projectDir, fresh)
    return stale.size
}

// --- Spawn ----------------------------------------------------------------

function isSessionNotFound(err) {
    const status = err?.status ?? err?.response?.status ?? err?.data?.status
    const message = String(err?.message ?? "").toLowerCase()
    const dataMessage = String(err?.data?.message ?? "").toLowerCase()
    return (
        status === 404 ||
        message.includes("not found") ||
        message.includes("notfound") ||
        dataMessage.includes("not found")
    )
}

/**
 * Spawn a subagent session from the current session. The fork inherits
 * the parent's conversation — the "same context session as a subagent
 * would". The prompt is prefixed with the keeper brief (P3) so the
 * subagent carries the keeper context. Returns the forked session id.
 */
export async function spawnSubagent(client, parentSessionID, prompt, options = {}) {
    const projectDir = options.projectDir ?? process.env.OPENCODE_MEMORY_PROJECTS_DIR ?? ""
    const briefText = options.briefText ?? ""
    const fullPrompt = briefText ? `${briefText}\n\n${prompt}` : prompt

    const forkResult = await client.session.fork({
        path: { id: parentSessionID },
        throwOnError: true,
    })
    const forkedData = forkResult?.data || forkResult
    if (!forkedData?.id) {
        throw new Error("rtr-subagent: fork returned no session id")
    }
    const forkedSessionID = forkedData.id

    const parentResult = await client.session.get({ path: { id: parentSessionID } })
    const parentTitle = parentResult?.data?.title || parentResult?.title || "Untitled"
    try {
        await client.session.update({
            path: { id: forkedSessionID },
            body: { title: `${SUBAGENT_TITLE_PREFIX}${parentTitle}` },
            throwOnError: true,
        })
    } catch {
        // Title rename is cosmetic; never fail the spawn on it.
    }

    await client.session.promptAsync({
        path: { id: forkedSessionID },
        body: { parts: [{ type: "text", text: fullPrompt }] },
        throwOnError: true,
    })

    if (projectDir) {
        try {
            await recordFork(projectDir, parentSessionID, forkedSessionID, prompt)
        } catch (err) {
            // Tracking is auxiliary: the fork exists and runs. Never fail
            // the spawn (orphaning a live fork) on a mapping write error.
            console.error(`[rtr-subagent] mapping write failed: ${err?.message ?? err}`)
        }
    }
    return forkedSessionID
}

/**
 * Retry-once wrapper: if the fork vanished (404), re-fork and retry.
 */
export async function spawnSubagentWithRetry(client, parentSessionID, prompt, options = {}) {
    try {
        return await spawnSubagent(client, parentSessionID, prompt, options)
    } catch (err) {
        if (!isSessionNotFound(err)) throw err
        return await spawnSubagent(client, parentSessionID, prompt, options)
    }
}

// --- Completion (session.idle observer) -----------------------------------

/**
 * Return true when the idle event belongs to a tracked subagent fork.
 * ES2025 Set.isSubsetOf: the event's session id must be a member of the
 * tracked fork set.
 */
export async function isTrackedIdle(event, projectDir) {
    if (event?.type !== "session.idle") return false
    const sessionID = event.properties?.sessionID
    if (!sessionID) return false
    const tracked = await trackedForkIds(projectDir)
    if (!tracked.size) return false
    return new Set([sessionID]).isSubsetOf(tracked)
}

/**
 * Compose a session.idle handler for a plugin's `event` hook.
 */
export function makeIdleHandler(client, projectDir, onComplete) {
    return async (input) => {
        const event = input?.event
        if (!(await isTrackedIdle(event, projectDir))) return
        const sessionID = event.properties.sessionID
        try {
            const sessionResult = await client.session.get({ path: { id: sessionID } })
            const title = sessionResult?.data?.title || sessionResult?.title || ""
            const label = title.startsWith(SUBAGENT_TITLE_PREFIX)
                ? title.slice(SUBAGENT_TITLE_PREFIX.length)
                : title
            if (onComplete) await onComplete({ sessionID, title: label })
        } catch (err) {
            console.error(`[rtr-subagent] idle handler failed: ${err?.message ?? err}`)
        }
    }
}

export default {
    STALE_AFTER_MS,
    SUBAGENT_TITLE_PREFIX,
    SUBAGENT_VERSION,
    isTrackedIdle,
    loadMappings,
    makeIdleHandler,
    pruneStaleMappings,
    recordFork,
    saveMappings,
    spawnSubagent,
    spawnSubagentWithRetry,
    storagePaths,
    trackedForkIds,
}
