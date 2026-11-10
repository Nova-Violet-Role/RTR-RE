#!/usr/bin/env node
// RTR-RE installer — native terminal launcher (Node core only).
//
// The installer runs entirely in the terminal — no browser, no HTTP, no
// network. Same experience as the Python launcher: three platform
// personalities as truecolor themes declared in the scene DTD module,
// read from the scene XML instances, and rendered by a small ANSI
// engine. Audio plays via the platform's native player.
//
// Usage:
//   node node_launcher.mjs [--theme instrument|network|forge]
//                           [--project DIR] [--tarball PATH]

import { spawn } from "node:child_process"
import fs from "node:fs"
import { promises as fsp } from "node:fs"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import readline from "node:readline"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SHELL_DIR = path.resolve(__dirname, "..", "shell")
const SCENES_DIR = path.join(SHELL_DIR, "dtd", "scenes")
const AUDIO_DIR = path.join(SHELL_DIR, "assets", "audio")

// ---------------------------------------------------------------- ANSI engine

const Term = {
  RESET: "\x1b[0m",
  BOLD: "\x1b[1m",
  DIM: "\x1b[2m",
  CLEAR: "\x1b[2J\x1b[H",
  HIDE: "\x1b[?25l",
  SHOW: "\x1b[?25h",
  rgb: (r, g, b) => `\x1b[38;2;${r};${g};${b}m`,
  move: (y, x) => `\x1b[${y};${x}H`,
  clearLine: () => "\x1b[2K",
}

// ---------------------------------------------------------------- scene / theme

export function readScene(theme, scenesDir = SCENES_DIR) {
  // Parse the scene XML. The scene is a DTD family member declared in
  // rtrre-scene.mod; the XML is ours, simple, and attribute-level — a
  // tiny regex extractor is sufficient and dependency-free.
  // Never throws for scene data: unreadable files fall back to {},
  // missing or garbage fields fall back to defaults.
  const file = path.join(scenesDir, `${theme}.xml`)
  let xml
  try {
    xml = fs.readFileSync(file, "utf8")
  } catch (e) {
    console.error(`warning: scene ${theme} unreadable (${e.message}); using defaults`)
    return {}
  }
  const attr = (elem, name, dflt) => {
    const m = xml.match(new RegExp(`<${elem}[^>]*\\b${name}="([^"]*)"`))
    return m ? m[1] : dflt
  }
  const num = (elem, name, dflt) => {
    const v = parseFloat(attr(elem, name, dflt))
    return Number.isFinite(v) ? v : dflt
  }
  const col = (elem, name, dflt) => {
    const v = attr(elem, name, "")
    if (!v) return dflt
    const xs = v.split(",").map((x) => Math.round(parseFloat(x) * 255))
    return xs.length === 3 && xs.every(Number.isFinite) ? xs : dflt
  }
  return {
    particles: {
      count: num("particles", "count", 900),
      color: col("particles", "color", [0, 229, 255]),
      color2: col("particles", "color2", [30, 111, 255]),
      mix: num("particles", "color-mix", 0.6),
      speed: num("particles", "speed", 0.6),
    },
    core: { glow: col("core", "glow", [128, 128, 255]) },
    floor: { reflect: num("floor", "reflect", 0.35) },
    camera: { drift: num("camera", "drift", 0.0012) },
  }
}

export function animateParams(scene) {
  const particles = scene?.particles ?? {}
  const num = (key, dflt) => {
    const v = Number(particles[key] ?? dflt)
    return Number.isFinite(v) ? v : dflt
  }
  const count = num("count", 900)
  const speed = num("speed", 0.6)
  const mix = num("mix", 0.6)
  return {
    density: Math.min(0.20, Math.max(0.02, 0.06 * (count / 900))),
    sleep: (1 / 12) * (0.6 / Math.max(speed, 0.1)),
    ratio: Math.min(1, Math.max(0, mix)),
  }
}

const THEMES = {
  instrument: { label: "The Instrument", platform: "pip / uvx", accent: [0, 229, 255], accent2: [30, 111, 255] },
  network: { label: "The Network", platform: "npm", accent: [255, 61, 138], accent2: [138, 61, 255] },
  forge: { label: "The Forge", platform: "GitHub", accent: [0, 230, 118], accent2: [0, 176, 255] },
}

// ---------------------------------------------------------------- components / presets

const COMPONENTS = [
  ["keeper", "Keeper", "window edge · eviction · protection", true],
  ["compressor", "Compressor", "verbatim eviction · background tickets", true],
  ["engine", "Engine", "dual-ONNX retrieval core", true],
  ["plugin", "OpenCode plugin", "keeper + ctrl+p palette", false],
  ["optimizer", "Optimizer", "machine-aware recommendations", false],
  ["presets", "Preset registry", "MUGEN · Symbiose-AH! · Fusion-AH!", true],
  ["cli", "CLI", "rtr-cli bridge (no-MCP mode)", false],
  ["memory", "Memory root", ".opencode/memory/ (DTD-shaped)", true],
]

const RECOMMEND = {
  threads: "Recommended from Saimonokuma: 8 threads — T8 is the speed sweet spot on 32-thread hosts.",
  parking: "Recommended from Saimonokuma: P40 — balances headroom on 32-thread hosts.",
}

const TIPS = {
  threads: "Did you know: scores are flat from T4 to T16 — threads buy speed, not quality.",
  parking: "Did you know: P20 on a small-RAM machine lets the SSD act as the memory mitigation.",
  mugen: "Did you know: MUGEN (400k/200k/200) is the infinite-memory preset.",
  modality: "Did you know: rtr-full loads two ONNX models; single-model modalities halve resident RAM.",
}

const EASTER_CITATION =
  "In Blue Submarine No. 6, the sea itself becomes a question: when nature is " +
  "reshaped into new forms of life, what does it mean to be alive — and two " +
  "friends find the way to save a world that has already changed. In Heroes, " +
  "Emma Coolidge hears data as music and sees it as color — perception beyond " +
  "the measurable. MiDi-MoE-Symbiogen-000 asks the same question: what if data " +
  "could be anything, anywhere, at the same time? Not stored, but dwelling — a " +
  "virus, a bacterium, an animal, an intelligence that provides for its own " +
  "sake. Temporalism cannot be measured. But what if it could be felt?" +
  " Symbiogen-003 Automata tends what dwells: patient processes " +
  "that keep the stored world, as lighthouse keepers keep the light. " +
  "Symbiogen-004 Errata keeps what failed: every error indexed, " +
  "every mistake retrievable, nothing repeated. Between them " +
  "runs the IRC bridge, and across it weight-transfer units move " +
  "as MIDI frequency transfer — instruction as music, perception " +
  "as protocol. To cross is personality transposition: arrival " +
  "changes the traveler, and the change is the message."

// ---------------------------------------------------------------- audio

export function whichSync(name) {
  const pathEnv = process.env.PATH || ""
  const dirs = pathEnv.split(path.delimiter).filter(Boolean)
  const exts = process.platform === "win32" ? (process.env.PATHEXT || ".EXE").split(";") : [""]
  for (const dir of dirs) {
    for (const ext of exts) {
      const candidate = path.join(dir, process.platform === "win32" ? name + ext.toLowerCase() : name)
      try {
        if (fs.statSync(candidate).isFile()) return candidate
      } catch { /* next */ }
    }
  }
  return null
}

export function linuxPlayerCmd(variant, which = whichSync) {
  if (which("mpg123")) return ["mpg123", variant]
  if (which("mpv")) return ["mpv", "--no-video", variant]
  if (which("ffplay")) return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", variant]
  return null
}

export function validatedInt(text, dflt, lo, hi) {
  const s = String(text ?? "").trim()
  if (!s) return [true, dflt]
  const v = Number(s)
  if (!Number.isInteger(v)) return [false, null]
  return lo <= v && v <= hi ? [true, v] : [false, null]
}

export function windowsMediaCommand(variant) {
  const url = String(variant).replace(/\\/g, "/")
  return `$wmp = New-Object -ComObject WMPlayer.OCX; $wmp.URL = '${url}'; $wmp.controls.play(); ` +
    `$t = 0; while ($t -lt 600 -and @(1,8) -notcontains $wmp.playState) { Start-Sleep -Seconds 5; $t += 5 }`
}

function playAudio(preset) {
  if (process.env.RTRRE_INSTALL_NO_AUDIO === "1") return
  const variant = path.join(AUDIO_DIR, `obsession-${preset}.mp3`)
  try {
    if (!fs.statSync(variant).isFile()) return
  } catch {
    return
  }
  const platform = process.platform
  let cmd, args
  if (platform === "win32") {
    cmd = "powershell"
    args = ["-NoProfile", "-Command",
      windowsMediaCommand(variant)]
  } else if (platform === "darwin") {
    cmd = "afplay"; args = [variant]
  } else {
    const chain = linuxPlayerCmd(variant)
    if (!chain) return
    ;[cmd, ...args] = chain
  }
  try {
    const p = spawn(cmd, args, { stdio: "ignore", detached: true })
    p.on("error", () => {})
    p.unref()
  } catch {
    // Audio must never break the installer.
  }
}

// ---------------------------------------------------------------- install actions

export function planFor(payload) {
  const preset = payload.preset || "quick"
  if (preset === "manual") {
    return [
      ["preset", "manual (palette guide + your knobs, no automation)"],
      ["threads", `T${payload.threadsPerModel ?? 8} (2/4/6/8/12/16)`],
      ["parking", `P${payload.parkingPercent ?? 60} (20-80)`],
      ["mode", "manual: auto trigger/target/max OFF, one-shots only"],
      ["engine", "rtr-full · dual-ONNX"],
      ["plugin", "keeper + ctrl+p palette"],
      ["memory", ".opencode/memory/ (DTD-shaped)"],
    ]
  }
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
  if (preset === "hardcore") {
    return [
      ["preset", payload.presetName || "re-symbiose-mugen"],
      ["threads", String(payload.threads ?? 8)],
      ["parking", String(payload.parking ?? 40) + "%"],
      ["modality", payload.modality || "rtr-full"],
      ["trigger", String(payload.triggerTokens ?? 400000)],
      ["target", String(payload.targetTokens ?? 200000)],
      ["max", String(payload.maxKeepMessages ?? 200)],
      ["engine", "rtr-full · dual-ONNX"],
      ["plugin", "keeper + ctrl+p palette"],
      ["memory", ".opencode/memory/ (DTD-shaped)"],
    ]
  }
}

export async function executePlan(payload, project, tarball) {
  const preset = payload.preset || "quick"
  const cfgDir = path.join(project, ".opencode")
  await fsp.mkdir(cfgDir, { recursive: true })
  const cfg = {
    preset: preset === "hardcore" ? (payload.presetName || "re-symbiose-mugen") : "re-symbiose-mugen",
    cpuProfile: "local-system",
    enabled: true,
  }
  if (preset === "hardcore") {
    cfg.threadsPerModel = payload.threads ?? 8
    cfg.parkingPercent = payload.parking ?? 40
    cfg.modality = payload.modality || "rtr-full"
    cfg.triggerTokens = payload.triggerTokens ?? 400000
    cfg.targetTokens = payload.targetTokens ?? 200000
    cfg.maxKeepMessages = payload.maxKeepMessages ?? 200
  }
  if (preset === "manual") {
    delete cfg.preset
    cfg.manual = true
    cfg.threadsPerModel = payload.threadsPerModel ?? 8
    cfg.parkingPercent = payload.parkingPercent ?? 60
    try {
      const guide = await fsp.readFile(path.join(SHELL_DIR, "assets", "palette-guide.txt"), "utf8")
      const memDir = path.join(project, ".opencode", "memory")
      await fsp.mkdir(memDir, { recursive: true })
      await fsp.writeFile(path.join(memDir, "rtrre-palette-guide.txt"), guide, "utf8")
    } catch {
      // Guide copy is a courtesy; never block installation.
    }
  }
  await fsp.writeFile(path.join(cfgDir, "rtr-re-keeper.json"), JSON.stringify(cfg, null, 2), "utf8")
  if (tarball && (await fsp.stat(tarball).catch(() => null))) {
    const code = await new Promise((resolve) => {
      const p = spawn("npm", ["install", "--no-save", "--loglevel=error", tarball], { stdio: "inherit" })
      p.on("close", resolve)
      p.on("error", () => resolve(1))
    })
    if (code !== 0) return false
  }
  return true
}

// ---------------------------------------------------------------- terminal UI

class InstallerUI {
  constructor(theme, project, tarball) {
    this.theme = theme
    this.meta = THEMES[theme]
    this.scene = readScene(theme)
    this.project = project
    this.tarball = tarball
    this.accent = this.meta.accent
    this.accent2 = this.meta.accent2
    this.preset = "quick"
    this.audioPlayed = new Set()
    this.components = new Set(COMPONENTS.filter((c) => c[3]).map((c) => c[0]))
    this.hardcore = { threads: 8, parking: 40, presetName: "re-symbiose-mugen", modality: "rtr-full", triggerTokens: 400000, targetTokens: 200000, maxKeepMessages: 200 }
    this.manual = { threadsPerModel: 8, parkingPercent: 60 }
    // async iterator: works both interactively (TTY) and with piped stdin
    this.rl = readline.createInterface({ input: process.stdin, output: process.stdout })
    this.lines = this.rl[Symbol.asyncIterator]()
  }

  async q(prompt) {
    process.stdout.write(prompt)
    const { value } = await this.lines.next()
    return value ?? ""
  }

  paint(text, color, bold = false, dim = false) {
    let out = ""
    if (color) out += Term.rgb(...color)
    if (bold) out += Term.BOLD
    if (dim) out += Term.DIM
    return out + text + Term.RESET
  }

  banner() {
    const lines = [
      "  ╔══════════════════════════════════════════════════════════════╗",
      "  ║   RTR-RE:Symbiose — Installer                               ║",
      `  ║   ${this.meta.label} · ${this.meta.platform.padEnd(28)}║`,
      "  ╚══════════════════════════════════════════════════════════════╝",
    ]
    return lines.map((l) => this.paint(l, this.accent, true)).join("\n")
  }

  header() {
    return this.banner() + "\n\n" + this.paint("  Enter RTR-RE — choose how you want to arrive.\n", this.accent)
  }

  async animate(seconds = 1.2, width = 60, height = 8) {
    const cols = [this.accent, this.accent2]
    const params = animateParams(this.scene)
    for (let frame = 0; frame < Math.round(seconds * 12); frame++) {
      const rows = []
      for (let y = 0; y < height; y++) {
        let row = ""
        for (let x = 0; x < width; x++) {
          row += Math.random() < params.density ? this.paint("·", Math.random() < params.ratio ? cols[0] : cols[1]) : " "
        }
        rows.push(row)
      }
      process.stdout.write(Term.move(2, 1) + rows.join("\n"))
      await new Promise((r) => setTimeout(r, params.sleep * 1000))
    }
  }

  async screenPresets() {
    process.stdout.write(Term.CLEAR + this.header())
    console.log(this.paint("  [1] Quick Install — MUGEN · 400k/200k/200 · one click", this.accent, true))
    console.log(this.paint("  [2] Custom Selection — choose components · balanced", this.accent2))
    console.log(this.paint("  [3] Hardcore — full control · every option · 8 threads/P40", this.accent))
    console.log(this.paint("  [4] Manual — palette guide · roomy 600k/300k/200 · you drive", this.accent2))
    console.log()
    const choice = (await this.q("  Select [1/2/3/4]: ")).trim()
    if (choice === "2") { this.preset = "custom"; await this.screenCustom() }
    else if (choice === "3") { this.preset = "hardcore"; await this.screenHardcore() }
    else if (choice === "4") { this.preset = "manual"; await this.screenManual() }
    else { this.preset = "quick"; await this.screenReview() }
  }

  async screenManual() {
    process.stdout.write(Term.CLEAR + this.header())
    console.log(this.paint("  Manual preset — professional manual context care.\n", this.accent, true))
    try {
      const guide = await fsp.readFile(path.join(SHELL_DIR, "assets", "palette-guide.txt"), "utf8")
      console.log(guide)
    } catch {
      console.log("  (palette guide unavailable in this package)")
    }
    const m = this.manual
    m.threadsPerModel = await this.promptInt(`  Threads per model T-modes 2/4/6/8/12/16 [${m.threadsPerModel}]: `, m.threadsPerModel, 2, 16)
    m.parkingPercent = await this.promptInt(`  Parking percent 20-80 [${m.parkingPercent}]: `, m.parkingPercent, 20, 80)
    console.log("  " + this.paint("Manual has no automatic trigger, target, or max: you evict via palette one-shots.", null, false, true))
    await this.screenReview()
  }

  async screenCustom() {
    process.stdout.write(Term.CLEAR + this.header())
    console.log(this.paint("  Select components (toggle with number, Enter when done):\n", this.accent))
    COMPONENTS.forEach(([cid, name, desc, req], i) => {
      const mark = this.components.has(cid) ? "●" : "○"
      console.log(`  [${i + 1}] ${mark} ${name}${req ? " (required)" : ""} — ${desc}`)
    })
    console.log()
    while (true) {
      const line = (await this.q("  Toggle [1-8], Enter to continue: ")).trim()
      if (!line) break
      for (const tok of line.split(/\s+/)) {
        const n = parseInt(tok, 10)
        if (n >= 1 && n <= 8) {
          const [cid, , , req] = COMPONENTS[n - 1]
          if (!req) {
            if (this.components.has(cid)) this.components.delete(cid)
            else this.components.add(cid)
          }
        }
      }
      process.stdout.write(Term.move(12, 1) + Term.clearLine())
    }
    await this.screenReview()
  }

  async promptInt(prompt, dflt, lo, hi) {
    for (;;) {
      const [ok, value] = validatedInt(await this.q(prompt), dflt, lo, hi)
      if (ok) return value
      console.log(`  Enter a whole number ${lo}-${hi} (empty keeps ${dflt}).`)
    }
  }

  async screenHardcore() {
    process.stdout.write(Term.CLEAR + this.header())
    console.log(this.paint("  Hardcore cockpit — every option.\n", this.accent, true))
    const h = this.hardcore
    h.threads = await this.promptInt(`  Threads [${h.threads}]: `, h.threads, 1, 64)
    console.log("  " + this.paint(RECOMMEND.threads, this.accent))
    h.parking = await this.promptInt(`  Parking % [${h.parking}]: `, h.parking, 0, 100)
    console.log("  " + this.paint(RECOMMEND.parking, this.accent))
    console.log("  " + this.paint(TIPS.threads, null, false, true))
    console.log("  " + this.paint(TIPS.parking, null, false, true))
    console.log()
    h.presetName = (await this.q("  Preset [re-symbiose-mugen]: ")) || "re-symbiose-mugen"
    console.log("  " + this.paint(TIPS.mugen, null, false, true))
    h.modality = (await this.q("  Modality [rtr-full]: ")) || "rtr-full"
    console.log("  " + this.paint(TIPS.modality, null, false, true))
    h.triggerTokens = await this.promptInt(`  Trigger tokens [${h.triggerTokens}]: `, h.triggerTokens, 1000, 100000000)
    h.targetTokens = await this.promptInt(`  Target tokens [${h.targetTokens}]: `, h.targetTokens, 1000, 100000000)
    h.maxKeepMessages = await this.promptInt(`  Max messages [${h.maxKeepMessages}]: `, h.maxKeepMessages, 1, 10000)
    await this.screenReview()
  }

  personality() {
    return this.theme // instrument | network | forge
  }

  renderProgress(i, total, k, v) {
    const pct = Math.round(((i + 1) / total) * 100)
    if (this.personality() === "forge") {
      const done = i < total - 1 ? "✓" : "✓"
      return `  ${this.paint(done, this.accent)}  $ ${k}: ${v}`
    }
    if (this.personality() === "network") {
      let nodes = ""
      for (let n = 0; n < total; n++) nodes += n <= i ? "●" : "○"
      return `  ${this.paint(nodes, this.accent)} ${String(pct).padStart(3)}%  ${k}: ${v}`
    }
    const wave = "▁▂▃▅▆▇█▇▆▅▃▂▁"
    const pos = Math.floor((pct / 100) * (wave.length - 1))
    const w = wave.slice(0, pos + 1) + " ".repeat(wave.length - pos - 1)
    return `  ${this.paint(w, this.accent)} ${String(pct).padStart(3)}%  ${k}: ${v}`
  }

  renderPlan(plan) {
    if (this.personality() === "forge") {
      return plan.map(([k, v]) => `  $ ${this.paint(k, this.accent)} ${v}`).join("\n")
    }
    return plan.map(([k, v]) => `    ${k.padEnd(12)} ${v}`).join("\n")
  }

  async screenReview() {
    if (!this.audioPlayed.has(this.preset)) {
      playAudio(this.preset)
      this.audioPlayed.add(this.preset)
    }
    const payload = { preset: this.preset }
    if (this.preset === "custom") payload.components = [...this.components].sort()
    else if (this.preset === "hardcore") Object.assign(payload, this.hardcore)
    else if (this.preset === "manual") Object.assign(payload, this.manual)
    const plan = planFor(payload)
    process.stdout.write(Term.CLEAR + this.header())
    console.log(this.paint("  Install plan:\n", this.accent, true))
    console.log(this.renderPlan(plan))
    console.log()
    const answer = (await this.q("  Install now? [Y/n]: ")).trim().toLowerCase()
    if (answer === "" || answer === "y" || answer === "yes") await this.screenProgress(payload, plan)
    else await this.screenPresets()
  }

  async screenProgress(payload, plan) {
    process.stdout.write(Term.CLEAR + this.header())
    console.log(this.paint("  Installing — the memory is being entered.\n", this.accent, true))
    const total = plan.length
    for (let i = 0; i < total; i++) {
      const [k, v] = plan[i]
      process.stdout.write(Term.move(6 + i, 1) + Term.clearLine())
      console.log(this.renderProgress(i, total, k, v))
      await new Promise((r) => setTimeout(r, 350))
    }
    const ok = await executePlan(payload, this.project, this.tarball)
    process.stdout.write(Term.move(6 + total, 1) + Term.clearLine())
    if (!ok) {
      console.log(this.paint(`  ✗ package install failed for ${this.tarball} — check the path, then retry.`, this.accent, true))
      await this.q("  Press Enter to return to the plan. ")
      await this.screenReview()
      return
    }
    if (this.personality() === "forge") {
      console.log(`  ${this.paint("✓", this.accent2)} build complete — 100%`)
    } else {
      console.log(`  ${this.paint("█".repeat(25), this.accent2)} 100%  done`)
    }
    await new Promise((r) => setTimeout(r, 600))
    await this.screenDone()
  }

  async screenDone() {
    process.stdout.write(Term.CLEAR + this.header())
    console.log(this.paint("  RTR-RE installed. The memory is in. The world is entered.\n", this.accent, true))
    const answer = (await this.q("  Awaken MiDi-MoE-Symbiogen-000? [y/N]: ")).trim().toLowerCase()
    if (answer === "y" || answer === "yes") {
      console.log()
      console.log(this.paint("  MiDi-MoE-Symbiogen-000", this.accent, true))
      console.log("  " + EASTER_CITATION)
      console.log()
    }
    await this.q("  Press Enter to close. ")
  }

  async run() {
    await this.animate()
    await this.screenPresets()
    this.rl.close()
  }
}

// ---------------------------------------------------------------- main

export function parseArgs(argv = process.argv.slice(2), env = process.env) {
  const argValue = (name) => {
    const i = argv.indexOf(name)
    return i >= 0 ? argv[i + 1] : undefined
  }
  const theme = argValue("--theme") || env.RTRRE_INSTALL_THEME || env.RTRRE_THEME || "network"
  if (!THEMES[theme]) {
    throw new Error(`rtr-re-installer: unknown theme ${theme}; expected instrument|network|forge`)
  }
  return {
    theme,
    project: argValue("--project") || env.RTRRE_INSTALL_PROJECT || process.cwd(),
    tarball: argValue("--tarball") || env.RTRRE_INSTALL_TARBALL,
  }
}

export async function main(argv, env) {
  const { theme, project, tarball } = parseArgs(argv, env)
  process.on("SIGINT", () => {
    process.stdout.write(Term.SHOW)
    process.exit(130)
  })
  process.stdout.write(Term.HIDE)
  const ui = new InstallerUI(theme, project, tarball)
  try {
    await ui.run()
  } catch (e) {
    console.error(e)
  } finally {
    process.stdout.write(Term.SHOW)
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    await main()
  } catch (e) {
    console.error(e?.message ?? e)
    process.exit(2)
  }
}
