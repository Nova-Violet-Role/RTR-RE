// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
//
// Shared state, ruleset loading, AUTO-OPTIMIZE state machine, context-plan
// arithmetic, rtr-cli bridge argument building, and hook output for the
// rtr-re lifecycle hooks and the OpenCode plugin. One always-on mode; the
// flag file marks the exception: present = the user turned rtr off for
// this session. Absent = active, the default.
//
// Form mirrors the agile plugin core (MIT, Hubert Lepicki,
// https://github.com/hubertlepicki/agile), whose host detection and hook
// output shapes derive from ponytail (MIT, DietrichGebert). The rules,
// memory loop, and optimizer are this project's own.

const fs = require('fs');
const os = require('os');
const path = require('path');

const OFF_FLAG = '.rtr-off';
const SKILL_PATH = path.join(__dirname, '..', 'skills', 'rtr', 'SKILL.md');
const AGENTS_PATH = path.join(__dirname, '..', 'AGENTS.md');

// Codex exports PLUGIN_DATA as its per-plugin state directory; Claude Code
// does not. That is the only host difference the hooks care about.
const isCodex = Boolean(process.env.PLUGIN_DATA);

const stateDir = isCodex
  ? process.env.PLUGIN_DATA
  : (process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude'));

const flagPath = path.join(stateDir, OFF_FLAG);

const DEACTIVATE = /^\s*(?:[/@$]rtr\s+off|stop\s+rtr|rtr\s+off|normal\s+mode)\s*$/i;
const REACTIVATE = /^\s*(?:[/@$]rtr(?:\s+on)?|start\s+rtr|rtr\s+on|resume\s+rtr)\s*$/i;

function isActive() {
  return !fs.existsSync(flagPath);
}

function deactivate() {
  try {
    fs.mkdirSync(stateDir, { recursive: true });
    fs.writeFileSync(flagPath, '');
  } catch (e) {
    // Best-effort: a state write must never block the session.
  }
}

function activate() {
  try { fs.unlinkSync(flagPath); } catch (e) {}
}

// AGENTS.md mirrors the skill body and remains a standalone fallback.
function getInstructions() {
  for (const file of [SKILL_PATH, AGENTS_PATH]) {
    try {
      const body = fs.readFileSync(file, 'utf8').replace(/^---[\s\S]*?\n---\s*/, '');
      return 'RTR-RE MODE ACTIVE\n\n' + body.trim();
    } catch (e) {
      continue;
    }
  }
  return 'RTR-RE MODE ACTIVE\n\n' +
    'Persistent project memory without an MCP server. Session start: ' +
    'rtr-cli session-start <project>. Before repeating past work: ' +
    'rtr-cli search "<query>" --k 3. Durable learning: rtr-cli write ' +
    '<project> <filename> "<markdown>". After outside edits: rtr-cli ' +
    'index. Session end: rtr-cli session-commit <project>. If rtr-cli ' +
    'is absent, say so in one line and work from the files in front of ' +
    'you; never invent a memory result. AUTO-OPTIMIZE: between every ' +
    'file read and the next code write, run one unasked optimize pass — ' +
    'reuse what you read, delete what earns nothing, simplify to fewer ' +
    'elements, and name one concrete way the code beats the obvious ' +
    'first draft. Keep verbatim until 320000 tokens, then evict to a ' +
    '128000-token tail of at most 40 messages; evicted is never deleted.';
}

// Every-turn reminder. The full ruleset already lives in session context
// from SessionStart; re-sending it on every prompt was pure waste.
const REMINDER = 'RTR-RE MODE ACTIVE — memory loop via rtr-cli, AUTO-OPTIMIZE between reads and writes. Off only via stop rtr / normal mode / /rtr off.';

function getReminder() {
  return REMINDER;
}

// --- AUTO-OPTIMIZE -------------------------------------------------------
// One instigation per read-write cycle: the first file read while armed
// earns the note (the model is about to draft code from what it read),
// further reads stay silent so a long investigation is not spammed, and
// the next write re-arms. A write with no read before it earns nothing.
const AUTO_OPTIMIZE_NOTE =
  'AUTO-OPTIMIZE: before writing, run one unasked pass on the draft — ' +
  'reuse what you just read, delete what earns nothing, simplify to ' +
  'fewer elements, and name one concrete way it beats the obvious first ' +
  'version. Optimize this change only; name adjacent chances in one line.';

const READ_TOOLS = new Set(['read']);
const WRITE_TOOLS = new Set(['write', 'edit']);

function createAutoOptimizer() {
  let armed = true;
  return {
    noteForToolAfter(tool) {
      const name = String(tool || '').toLowerCase();
      if (WRITE_TOOLS.has(name)) {
        armed = true;
        return null;
      }
      if (READ_TOOLS.has(name) && armed) {
        armed = false;
        return AUTO_OPTIMIZE_NOTE;
      }
      return null;
    },
    armed() {
      return armed;
    },
  };
}

// --- Context plan --------------------------------------------------------
// The RE:Symbiose budget arithmetic, same defaults the Python engine
// reports (memory_context_plan): verbatim until the trigger, then evict
// to the preserved tail. Pure arithmetic; loads and mutates nothing.
const PLAN_DEFAULTS = {
  triggerTokens: 320000,
  targetTokens: 128000,
  maxKeepMessages: 40,
  maxSummaryChars: 20000,
  maxRestoreChars: 4000,
};

function planContext(totalTokens, messageCount, over = {}) {
  const cfg = { ...PLAN_DEFAULTS, ...(over || {}) };
  const total = Number(totalTokens) || 0;
  const decision = total < cfg.triggerTokens
    ? 'keep verbatim (below trigger)'
    : `evict to ${cfg.targetTokens} tokens (above trigger)`;
  return { ...cfg, totalTokens: total, messageCount: Number(messageCount) || 0, decision };
}

// --- rtr-cli bridge ------------------------------------------------------
// Argument shapes measured from `rtr-cli <cmd> --help` (0.4.1). Unknown
// commands and missing required fields are refused by name, never
// guessed: a bridge that invents flags is worse than no bridge.
function buildCliArgs(command, opts = {}) {
  const o = opts || {};
  const need = (field) => {
    if (o[field] === undefined || o[field] === null || o[field] === '') {
      throw new Error(`rtr-cli ${command}: missing required ${field}`);
    }
    return String(o[field]);
  };
  switch (command) {
    case 'search':
    case 'explain': {
      const args = [command, need('query')];
      if (o.k !== undefined && o.k !== null && o.k !== '') args.push('--k', String(o.k));
      if (o.project) args.push('--project', String(o.project));
      if (command === 'search' && o.denseOnly) args.push('--dense-only');
      return args;
    }
    case 'write':
      return ['write', need('project'), need('filename'), need('content')];
    case 'index': {
      const args = ['index'];
      if (o.force) args.push('--force');
      const projects = Array.isArray(o.project) ? o.project : (o.project ? [o.project] : []);
      for (const p of projects) args.push('--project', String(p));
      return args;
    }
    case 'stats':
      return ['stats'];
    case 'init': {
      const args = ['init', need('project')];
      if (o.variant) args.push('--variant', String(o.variant));
      return args;
    }
    case 'session-start':
    case 'lexikon-show':
      return [command, need('project')];
    case 'janitor': {
      const args = ['janitor'];
      if (o.dryRun) args.push('--dry-run');
      return args;
    }
    default:
      throw new Error(`rtr-cli bridge: unknown command ${command}`);
  }
}

function writeHookOutput(event, context) {
  try {
    if (isCodex) {
      const output = { systemMessage: 'RTR-RE' };
      if (context) {
        output.hookSpecificOutput = { hookEventName: event, additionalContext: context };
      }
      process.stdout.write(JSON.stringify(output));
      return;
    }
    // Claude Code takes raw stdout as context for SessionStart and
    // UserPromptSubmit, but drops SubagentStart context unless wrapped.
    if (event === 'SubagentStart') {
      process.stdout.write(JSON.stringify(
        { hookSpecificOutput: { hookEventName: event, additionalContext: context } }));
      return;
    }
    process.stdout.write(context);
  } catch (e) {
    // A closed stdout at hook exit must not surface as a hook failure.
  }
}

module.exports = {
  AUTO_OPTIMIZE_NOTE,
  DEACTIVATE,
  PLAN_DEFAULTS,
  READ_TOOLS,
  REACTIVATE,
  WRITE_TOOLS,
  activate,
  buildCliArgs,
  createAutoOptimizer,
  deactivate,
  getInstructions,
  getReminder,
  isActive,
  planContext,
  writeHookOutput,
};
