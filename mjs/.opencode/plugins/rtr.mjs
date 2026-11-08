// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
//
// rtr-re — OpenCode plugin (the no-MCP edition).
//
// Injects the RTR-RE ruleset into every chat's system prompt, persists
// /rtr off (and turns it back on), registers the /rtr command, and runs
// AUTO-OPTIMIZE between file reads and code writes: the first read of a
// cycle appends one instigation line to the tool output the model is
// about to reason over; the next write re-arms it. Reuses the shared
// core so Claude Code, Codex, and OpenCode read one source of truth.
// Memory itself runs through the rtr-cli bridge named in the ruleset —
// this plugin never starts a server.
//
// Form after the agile OpenCode plugin (MIT, Hubert Lepicki).
//
// OpenCode loads this as a server plugin — add it to your opencode.json:
//   { "plugin": ["@nova-violet-role/rtr-re-mjs"] }
// or drop the .opencode directory into your project/config as-is.

import { createRequire } from 'module';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const require = createRequire(import.meta.url);
const {
  DEACTIVATE,
  REACTIVATE,
  createAutoOptimizer,
  getInstructions,
  registryContextProfile,
} = require('../../hooks/rtr-core');
const { parseCommandFile } = require('./rtr-frontmatter.cjs');

const flagPath = path.join(
  process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config'),
  'opencode',
  '.rtr-off',
);

function isActive() {
  return !fs.existsSync(flagPath);
}

function deactivate() {
  try {
    fs.mkdirSync(path.dirname(flagPath), { recursive: true });
    fs.writeFileSync(flagPath, '');
  } catch (e) {}
}

function activate() {
  try { fs.unlinkSync(flagPath); } catch (e) {}
}

export default async () => {
  // A new OpenCode process is a new session: start on, like SessionStart.
  activate();
  // The optimizer's note carries the resolved registry profile when it is
  // reachable (preset, modality, threads, parking, hybrid/expansion), so
  // the unasked pass is grounded in the real configuration.
  const optimizer = createAutoOptimizer({
    getContext: () => registryContextProfile(),
  });

  return {
    config: async (config) => {
      if (!config.command) config.command = {};
      const commandDir = path.join(__dirname, '..', 'command');
      try {
        for (const file of fs.readdirSync(commandDir).filter((f) => f.endsWith('.md'))) {
          const name = path.basename(file, '.md');
          const parsed = parseCommandFile(path.join(commandDir, file));
          if (parsed) config.command[name] = parsed;
        }
      } catch (e) {}
    },

    'experimental.chat.system.transform': async (_input, output) => {
      if (!isActive()) return;
      const instructions = getInstructions();
      if (output.system.length > 0) {
        output.system[output.system.length - 1] += '\n\n' + instructions;
      } else {
        output.system.push(instructions);
      }
    },

    'command.execute.before': async (input) => {
      if (!input || input.command !== 'rtr') return;
      const args = String(input.arguments || '').trim();
      const slash = '/rtr' + (args ? ' ' + args : '');
      if (DEACTIVATE.test(slash) || DEACTIVATE.test(args)) {
        deactivate();
        return;
      }
      if (REACTIVATE.test(slash) || REACTIVATE.test(args)) {
        activate();
      }
    },

    // AUTO-OPTIMIZE: one instigation per read-write cycle, appended to
    // the read output the model reasons over next. Defensive about the
    // output shape and never throws into the tool loop.
    'tool.execute.after': async (input, output) => {
      try {
        if (!isActive()) return;
        const note = optimizer.noteForToolAfter(input?.tool);
        if (!note || !output) return;
        if (typeof output.output === 'string') {
          output.output += '\n\n' + note;
        } else if (Array.isArray(output.content)) {
          output.content.push({ type: 'text', text: note });
        }
      } catch (e) {}
    },
  };
};
