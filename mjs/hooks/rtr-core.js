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
    'first draft. Keep verbatim until 400000 tokens, then evict to a ' +
    '200000-token tail of at most 200 messages; evicted is never deleted.';
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

// Measured axis guidance (thread-scaling-1.1.0.md, TODO-69): scores are
// flat T4-T16, T8 is the speed sweet spot, T32 hurts, parking is
// quality-neutral and caps threads, P20/P40 are the low-end mitigation.
const DID_YOU_KNOW = [
  'Did you know: retrieval scores are flat from T4 to T16 — threads buy speed, not quality.',
  'Did you know: on small-RAM machines, P20 lets the SSD act as the memory mitigation.',
  'Did you know: MUGEN (400k/200k/200) is the infinite-memory preset.',
];

function recommendProfile(profile, processors) {
  const cores = Number(processors) || 0;
  if (cores >= 24) {
    return {
      line: 'Recommended from Saimonokuma: T8 + P40 (measured speed sweet spot, balanced headroom).',
      tip: DID_YOU_KNOW[0],
    };
  }
  if (cores >= 8) {
    return {
      line: 'Recommended for this machine: T4 + P40 (quality is flat; threads buy speed only).',
      tip: DID_YOU_KNOW[0],
    };
  }
  return {
    line: 'Recommended for this machine: T2 + P20 (low-end mode — the SSD mitigates RAM; same retrieval quality).',
    tip: DID_YOU_KNOW[1],
  };
}

// Data-rich note: when the optimizer has a context provider (the resolved
// registry profile), the note carries the real numbers so the pass is
// grounded in the actual configuration and retrieval learnings.
function buildOptimizeNote(ctx) {
  const head =
    'AUTO-OPTIMIZE: before writing, run one unasked pass on the draft — ' +
    'reuse what you just read, delete what earns nothing, simplify to ' +
    'fewer elements, and name one concrete way it beats the obvious first ' +
    'version. Optimize this change only; name adjacent chances in one line.';
  if (!ctx || !ctx.preset) return head;
  const parts = [
    head,
    `Context: ${ctx.presetDisplay} (${ctx.triggerTokens}/${ctx.targetTokens}/${ctx.maxKeepMessages}) · ` +
      `${ctx.modality.toUpperCase()} · T${ctx.threadsPerModel}/P${ctx.parkingPercent} · ` +
      `hybrid=${ctx.hybrid} expansion=${ctx.expansion}.`,
  ];
  if (ctx.expansion) {
    parts.push('Lexikon expansion is on: attribute queries expand through seeded terms.');
  } else {
    parts.push('This modality has no lexikon expansion: match terms verbatim.');
  }
  const rec = recommendProfile(ctx, ctx.logicalProcessors);
  parts.push(rec.line, rec.tip);
  return parts.join(' ');
}

const READ_TOOLS = new Set(['read']);
const WRITE_TOOLS = new Set(['write', 'edit']);

function createAutoOptimizer(provider) {
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
        let ctx = null;
        if (provider && typeof provider.getContext === 'function') {
          try {
            ctx = provider.getContext();
          } catch (e) {
            ctx = null;
          }
        }
        return buildOptimizeNote(ctx);
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
// The defaults come from the shared preset registry (rtr_presets.json)
// when it is reachable, so the non-MCP center agrees with the Python
// planner; PLAN_DEFAULTS is the standalone fallback only.
const REGISTRY_PATH = path.join(__dirname, '..', '..', 'execution', 'rtr_presets.json');

const PLAN_DEFAULTS = {
  triggerTokens: 400000,
  targetTokens: 200000,
  maxKeepMessages: 200,
  maxSummaryChars: 20000,
  maxRestoreChars: 4000,
};

let _registryCache = null;

function loadRegistry() {
  if (_registryCache !== null) return _registryCache;
  try {
    const data = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));
    if (data && data.defaultKeeperPreset && data.keeperPresets &&
        data.keeperPresets[data.defaultKeeperPreset]) {
      _registryCache = data;
    } else {
      _registryCache = {};
    }
  } catch (e) {
    _registryCache = {};
  }
  return _registryCache;
}

function registryContextProfile() {
  const reg = loadRegistry();
  if (!reg || !reg.cpuProfiles || !reg.defaultCpuProfile) return null;
  const profile = reg.cpuProfiles[reg.defaultCpuProfile];
  if (!profile || !profile.modality) return null;
  const preset = reg.keeperPresets[reg.defaultKeeperPreset];
  const modality = (reg.modalities && reg.modalities[profile.modality]) || {};
  return {
    preset: reg.defaultKeeperPreset,
    presetDisplay: (preset && preset.displayName) || reg.defaultKeeperPreset,
    triggerTokens: Number(preset.triggerTokens),
    targetTokens: Number(preset.targetTokens),
    maxKeepMessages: Number(preset.maxKeepMessages),
    cpuProfile: reg.defaultCpuProfile,
    modality: profile.modality,
    threadsPerModel: Number(profile.threadsPerModel),
    parkingPercent: Number(profile.parkingPercent),
    hybrid: Boolean(modality.hybrid),
    expansion: Boolean(modality.expansion),
    models: Array.isArray(modality.models) ? modality.models : [],
    logicalProcessors: (() => {
      try {
        return require('os').cpus().length;
      } catch {
        return 0;
      }
    })(),
  };
}

function planContext(totalTokens, messageCount, over = {}) {
  const reg = registryContextProfile();
  const base = reg
    ? {
        triggerTokens: reg.triggerTokens,
        targetTokens: reg.targetTokens,
        maxKeepMessages: reg.maxKeepMessages,
        maxSummaryChars: 20000,
        maxRestoreChars: 4000,
      }
    : PLAN_DEFAULTS;
  const cfg = { ...base, ...(over || {}) };
  const total = Number(totalTokens) || 0;
    const decision = total <= cfg.triggerTokens
      ? 'keep verbatim (below trigger)'
      : `evict to ${cfg.targetTokens} tokens (above trigger)`;
  return { ...cfg, totalTokens: total, messageCount: Number(messageCount) || 0, decision };
}

// --- rtr-cli bridge ------------------------------------------------------
// Argument shapes measured from `rtr-cli <cmd> --help` (1.2.0). Unknown
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
      if (o.repair) args.push('--repair');
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
    case 'session-commit': {
      const args = ['session-commit', need('project')];
      if (o.chat !== undefined && o.chat !== null && o.chat !== '') args.push('--chat', String(o.chat));
      return args;
    }
    case 'janitor': {
      const args = ['janitor'];
      if (o.dryRun) args.push('--dry-run');
      return args;
    }
    case 'symbiose-submit': {
      const args = ['symbiose-submit', need('project')];
      if (o.messagesJson !== undefined && o.messagesJson !== null && o.messagesJson !== '') args.push(String(o.messagesJson));
      if (o.messagesFile) args.push('--messages-file', String(o.messagesFile));
      if (o.timeout !== undefined && o.timeout !== null && o.timeout !== '') args.push('--timeout', String(o.timeout));
      return args;
    }
    case 'symbiose-drain': {
      const args = ['symbiose-drain', need('project')];
      if (o.limit !== undefined && o.limit !== null && o.limit !== '') args.push('--limit', String(o.limit));
      return args;
    }
    case 'symbiose-compress': {
      const args = ['symbiose-compress', need('project'), String(need('target'))];
      if (o.messagesJson !== undefined && o.messagesJson !== null && o.messagesJson !== '') args.push(String(o.messagesJson));
      if (o.messagesFile) args.push('--messages-file', String(o.messagesFile));
      if (o.timeout !== undefined && o.timeout !== null && o.timeout !== '') args.push('--timeout', String(o.timeout));
      return args;
    }
    case 'context-plan': {
      return ['context-plan', need('totalTokens'), need('messageCount')];
    }
    case 'keeper-evict-now': {
      const args = ['keeper-evict-now', need('project')];
      if (o.tokens !== undefined && o.tokens !== null && o.tokens !== '') args.push('--tokens', String(o.tokens));
      if (o.messages !== undefined && o.messages !== null && o.messages !== '') args.push('--messages', String(o.messages));
      return args;
    }
    case 'consolidate':
    case 'materialize':
    case 'update-graph':
    case 'lexikon-build':
      return [command, need('project')];
    case 'reflect': {
      const args = ['reflect', need('project')];
      if (o.chat !== undefined && o.chat !== null && o.chat !== '') args.push('--chat', String(o.chat));
      return args;
    }
    case 'lexikon-add': {
      const args = ['lexikon-add', need('project'), need('term')];
      if (o.definition !== undefined && o.definition !== null && o.definition !== '') args.push('--definition', String(o.definition));
      const aliases = Array.isArray(o.alias) ? o.alias : (o.alias ? [o.alias] : []);
      for (const a of aliases) args.push('--alias', String(a));
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
  DID_YOU_KNOW,
  PLAN_DEFAULTS,
  READ_TOOLS,
  REACTIVATE,
  WRITE_TOOLS,
  activate,
  buildCliArgs,
  buildOptimizeNote,
  createAutoOptimizer,
  deactivate,
  getInstructions,
  getReminder,
  isActive,
  loadRegistry,
  planContext,
  recommendProfile,
  registryContextProfile,
  writeHookOutput,
};
