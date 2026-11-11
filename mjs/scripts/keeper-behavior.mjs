// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// Keeper behavior freezer + gate (TODO-52 layer 4).
//
// `node keeper-behavior.mjs freeze` writes the frozen behavior manifest from
// the current keeper implementation. `node keeper-behavior.mjs check` re-runs
// the same fixed scenario matrix and exits 0 when every recorded outcome
// matches the manifest, 1 on the first drift (named), 2 when the manifest is
// missing. The scenarios are fixed inputs that exercise the plan contract:
// identity below trigger, bounded tail, recency-aware protection on both
// sides of the cumulative threshold, tool-pair fixpoint, sink-first
// fail-open, and NDATA masking.

import { createHash } from "node:crypto"
import { readFileSync, writeFileSync, existsSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { mkdir } from "node:fs/promises"

import keeper from "../../opencode-plugin/rtr-re-keeper.js"

const { planKeepIndices, applyKeeper, evictedSpans } = keeper._test

const MANIFEST_REL = join("..", "results", "keeper-behavior-manifest.json")
const DEFAULT_MANIFEST = join(dirname(fileURLToPath(import.meta.url)), MANIFEST_REL)
const MANIFEST = process.env.KEEPER_MANIFEST ?? DEFAULT_MANIFEST

function msg(role, text, extra = {}) {
    return {
        info: { id: `m-${text.length}-${role}`, role, sessionID: "s1", ...extra.info },
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

function cfg(over = {}) {
    return {
        enabled: true,
        triggerTokens: 1000,
        targetTokens: 400,
        maxKeepMessages: 40,
        cumulativeMessages: 0,
        protectedTools: new Set(["todowrite"]),
        ...over,
    }
}

function window(n, { protectedOld = -1, protectedRecent = -1, cumulative = 0 } = {}) {
    const messages = []
    for (let i = 0; i < n; i++) {
        messages.push(msg("assistant", "x".repeat(400)))
    }
    if (protectedOld >= 0) {
        messages[protectedOld] = msg("assistant", "x".repeat(400), { tool: "todowrite" })
    }
    if (protectedRecent >= 0) {
        messages[protectedRecent] = msg("assistant", "x".repeat(400), { tool: "todowrite" })
    }
    messages.push(msg("user", "go"))
    return { messages, cfg: cfg({ cumulativeMessages: cumulative }) }
}

function planOutcome(plan) {
    return {
        compress: plan.compress,
        keep: [...plan.keep].sort((a, b) => a - b),
        evict: [...plan.evict].sort((a, b) => a - b),
        total: plan.total,
        keepTokens: plan.keepTokens,
    }
}

async function applyOutcome(messages, c, sink) {
    const result = await applyKeeper(messages, c, sink)
    return {
        changed: result.changed,
        keptCount: result.messages.length,
        sinkPath: result.sinkPath,
        plan: result.plan ? planOutcome(result.plan) : null,
    }
}

function scenarios() {
    const small = window(5)
    const big = window(60, { protectedOld: 5, protectedRecent: 55, cumulative: 1001 })
    const allProtect = window(60, { protectedOld: 5, protectedRecent: 55, cumulative: 999 })
    const chain = {
        messages: [
            msg("assistant", "x".repeat(400)),
            msg("tool", "x".repeat(400)),
            msg("tool", "x".repeat(400)),
        ],
        cfg: cfg({ triggerTokens: 250, targetTokens: 150 }),
    }
    return {
        "below-trigger-identity": {
            scenario: () => planOutcome(planKeepIndices(small.messages, small.cfg)),
        },
        "bounded-tail-above-trigger": {
            scenario: () => planOutcome(planKeepIndices(big.messages, big.cfg)),
        },
        "recency-old-protected-evicted": {
            scenario: () => planOutcome(planKeepIndices(big.messages, big.cfg)),
        },
        "recency-recent-protected-kept": {
            scenario: () => planOutcome(planKeepIndices(big.messages, big.cfg)),
        },
        "all-protect-below-threshold": {
            scenario: () => planOutcome(planKeepIndices(allProtect.messages, allProtect.cfg)),
        },
        "tool-pair-fixpoint": {
            scenario: () => planOutcome(planKeepIndices(chain.messages, chain.cfg)),
        },
        "sink-first-fail-open": {
            scenario: async () => {
                try {
                    await applyOutcome(big.messages, big.cfg, async () => {
                        throw new Error("sink boom")
                    })
                    return { propagated: false }
                } catch (error) {
                    return { propagated: true, message: String(error?.message ?? error) }
                }
            },
        },
        "ndata-masked-spans": {
            scenario: () => {
                const blob = "QUJD".repeat(40)
                const messages = [
                    msg("assistant", `UNIQUE ${blob} ` + "v".repeat(4000)),
                    msg("user", "go"),
                ]
                const plan = planKeepIndices(messages, cfg({ triggerTokens: 100, targetTokens: 40 }))
                const spans = evictedSpans(messages, plan.evict)
                return { dtype: spans[0].dtype, text: spans[0].text }
            },
        },
    }
}

async function runAll() {
    const out = {}
    for (const [name, s] of Object.entries(scenarios())) {
        out[name] = await s.scenario()
    }
    return out
}

function freeze() {
    runAll()
        .then((scenarios) => {
            const data = {
                schema: "rtr.keeper-behavior-manifest/v1",
                keeperVersion: keeper._test.KEEPER_VERSION,
                scenarios,
            }
            return mkdir(dirname(MANIFEST), { recursive: true }).then(() => {
                writeFileSync(MANIFEST, JSON.stringify(data, null, 2) + "\n", "utf8")
                console.log(`keeper behavior manifest frozen: ${MANIFEST}`)
            })
        })
        .catch((error) => {
            console.error(`keeper-behavior: freeze failed: ${error?.message ?? error}`)
            process.exit(2)
        })
}

function check() {
    if (!existsSync(MANIFEST)) {
        console.error("keeper-behavior: manifest missing; run `node keeper-behavior.mjs freeze` first")
        process.exit(2)
    }
    const frozen = JSON.parse(readFileSync(MANIFEST, "utf8"))
    if (frozen.schema !== "rtr.keeper-behavior-manifest/v1") {
        console.error(`keeper-behavior: unsupported manifest schema ${frozen.schema}`)
        process.exit(2)
    }
    if (frozen.keeperVersion !== keeper._test.KEEPER_VERSION) {
        console.error(
            `keeper-behavior: keeper version drift ${frozen.keeperVersion} -> ${keeper._test.KEEPER_VERSION}`,
        )
        process.exit(1)
    }
    runAll().then((current) => {
        if (Object.keys(current).length !== Object.keys(frozen.scenarios).length) {
            console.error(
                `keeper-behavior: scenario count drift ${Object.keys(frozen.scenarios).length} -> ${Object.keys(current).length}`,
            )
            process.exit(1)
        }
        for (const [name, expected] of Object.entries(frozen.scenarios)) {
            if (!(name in current)) {
                console.error(`keeper-behavior: scenario ${name} missing from current run`)
                process.exit(1)
            }
            if (!(name in frozen.scenarios)) {
                console.error(`keeper-behavior: scenario ${name} missing from frozen manifest`)
                process.exit(1)
            }
            const a = JSON.stringify(current[name])
            const b = JSON.stringify(expected)
            if (a !== b) {
                console.error(`keeper-behavior: scenario ${name} drifted`)
                console.error(`  expected: ${b}`)
                console.error(`  actual:   ${a}`)
                process.exit(1)
            }
        }
        console.log(`keeper behavior gate: PASS (${Object.keys(frozen.scenarios).length} scenarios)`)
        process.exit(0)
    })
}

const mode = process.argv[2] ?? "check"
if (mode === "freeze") freeze()
else if (mode === "check") check()
else {
    console.error(`keeper-behavior: unknown mode ${mode}; use freeze|check`)
    process.exit(2)
}
