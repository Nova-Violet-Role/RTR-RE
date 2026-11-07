#!/usr/bin/env node
// RTR-RE installer — npm bin entry.
// Locates the terminal launcher bundled with this package and runs it.
// The launcher is the Node terminal installer (node_launcher.mjs); the
// shell assets (scene DTD family, audio remixes) ship alongside it.

import { spawn } from "node:child_process"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// The installer lives in the package under installer/ (copied at pack
// time from the repo). Fall back to the repo layout when running from
// the source tree.
const candidates = [
  path.join(__dirname, "installer", "launchers", "node_launcher.mjs"),
  path.join(__dirname, "..", "installer", "launchers", "node_launcher.mjs"),
  path.join(__dirname, "..", "..", "installer", "launchers", "node_launcher.mjs"),
]
const launcher = candidates.find((c) => {
  try { return fs.statSync(c).isFile() } catch { return false }
})

if (!launcher) {
  console.error("rtr-re-installer: launcher not found in this package")
  process.exit(1)
}

const child = spawn(process.execPath, [launcher, ...process.argv.slice(2)], {
  stdio: "inherit",
})
child.on("exit", (code) => process.exit(code ?? 0))
