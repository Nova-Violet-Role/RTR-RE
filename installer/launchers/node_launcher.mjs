#!/usr/bin/env node
// RTR-RE installer — native launcher (Node core only).
// The shell loads from disk (file://) — no http:// in the address bar.
// A loopback API server (127.0.0.1, random port, token, permissive CORS)
// serves only the hidden bridge calls.

import http from "node:http"
import { spawn } from "node:child_process"
import { randomBytes } from "node:crypto"
import { promises as fs } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SHELL_DIR = path.resolve(__dirname, "..", "shell")
const THEME = process.env.RTRRE_INSTALL_THEME || "network"

function planFor(payload) {
  const preset = payload.preset || "quick"
  if (preset === "quick") {
    return [
      ["preset", "re-symbiose-mugen (400k/200k/200)"],
      ["engine", "rtr-full · dual-ONNX"],
      ["profile", "local-system · T8/P80"],
      ["plugin", "keeper + ctrl+p palette"],
      ["memory", ".opencode/memory/ (DTD-shaped)"],
    ]
  }
  if (preset === "custom") {
    const comps = payload.components || []
    return [
      ["components", comps.join(", ")],
      ["engine", "rtr-full · dual-ONNX"],
      ["profile", "local-system · T8/P80"],
      ["plugin", "keeper + ctrl+p palette"],
      ["memory", ".opencode/memory/ (DTD-shaped)"],
    ]
  }
  return [
    ["preset", payload.presetName || "re-symbiose-mugen"],
    ["threads", String(payload.threads ?? 8)],
    ["parking", String(payload.parking ?? 40) + "%"],
    ["modality", payload.modality || "rtr-full"],
    ["engine", "rtr-full · dual-ONNX"],
    ["plugin", "keeper + ctrl+p palette"],
    ["memory", ".opencode/memory/ (DTD-shaped)"],
  ]
}

async function executePlan(payload, log) {
  const preset = payload.preset || "quick"
  log(`preset=${preset}`)
  const project = process.env.RTRRE_INSTALL_PROJECT || process.cwd()
  const cfgDir = path.join(project, ".opencode")
  await fs.mkdir(cfgDir, { recursive: true })
  const cfg = {
    preset: preset === "hardcore" ? (payload.presetName || "re-symbiose-mugen") : "re-symbiose-mugen",
    cpuProfile: "local-system",
    enabled: true,
  }
  if (preset === "hardcore") {
    cfg.threadsPerModel = payload.threads ?? 8
    cfg.parkingPercent = payload.parking ?? 40
    cfg.modality = payload.modality || "rtr-full"
  }
  await fs.writeFile(path.join(cfgDir, "rtr-re-keeper.json"), JSON.stringify(cfg, null, 2), "utf8")
  log("config .opencode/rtr-re-keeper.json written")
  const tarball = process.env.RTRRE_INSTALL_TARBALL
  if (tarball && (await fs.stat(tarball).catch(() => null))) {
    log(`installing ${path.basename(tarball)}`)
    await new Promise((resolve) => {
      const p = spawn("npm", ["install", "--no-save", tarball], { stdio: "ignore" })
      p.on("close", resolve)
    })
  }
  log("done")
  return { ok: true }
}

function serve() {
  const token = randomBytes(16).toString("hex")

  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, "http://127.0.0.1")
    res.setHeader("Access-Control-Allow-Origin", "*")
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-RTR-Token")
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return }
    if (req.headers["x-rtr-token"] !== token) {
      res.writeHead(401, { "Content-Type": "application/json" })
      res.end(JSON.stringify({ error: "unauthorized" }))
      return
    }
    const send = (obj, code = 200) => {
      const body = JSON.stringify(obj)
      res.writeHead(code, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) })
      res.end(body)
    }
    if (req.method === "GET" && u.pathname === "/api/status") {
      return send({ ok: true, theme: THEME })
    }
    if (req.method === "POST") {
      let payload = {}
      try { payload = JSON.parse(await readBody(req)) } catch {}
      if (u.pathname === "/api/plan") return send({ steps: planFor(payload) })
      if (u.pathname === "/api/execute") return send(await executePlan(payload, () => {}))
      if (u.pathname === "/api/easter-egg") return send({ ok: true })
      return send({ error: "not found" }, 404)
    }
    send({ error: "not found" }, 404)
  })

  server.listen(0, "127.0.0.1", () => {
    const port = server.address().port
    const index = path.resolve(SHELL_DIR, "index.html")
    const url = `file:///${index.replace(/\\/g, "/")}?bridge=http://127.0.0.1:${port}&token=${token}&theme=${THEME}`
    console.log(`RTR-RE installer: shell file://${index.replace(/\\/g, "/")} api :${port}`)
    open(url)
  })
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = ""
    req.on("data", (c) => (data += c))
    req.on("end", () => resolve(data))
    req.on("error", reject)
  })
}

function open(url) {
  const platform = process.platform
  if (platform === "win32") {
    spawn("cmd", ["/c", "start", "", url], { stdio: "ignore", detached: true }).unref()
  } else {
    const cmd = platform === "darwin" ? "open" : "xdg-open"
    spawn(cmd, [url], { stdio: "ignore", detached: true }).unref()
  }
}

serve()
