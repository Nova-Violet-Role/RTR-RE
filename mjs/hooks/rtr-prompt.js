#!/usr/bin/env node
// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// UserPromptSubmit — remind every turn that rtr-re is active, without
// re-sending the full ruleset SessionStart already put in context. Also
// the place where "stop rtr" / "/rtr off" is picked up, and where
// "/rtr on" re-injects the full ruleset after it was off.
//
// The stdin read and its never-hang fallback follow the agile/ponytail
// hook form (MIT), as documented in rtr-core.js.

const {
  DEACTIVATE,
  REACTIVATE,
  activate,
  deactivate,
  getInstructions,
  getReminder,
  isActive,
  writeHookOutput,
} = require('./rtr-core');

let input = '';
let done = false;

function finish() {
  if (done) return;
  done = true;

  let prompt = '';
  let unreadable = false;
  try {
    // Some shells prepend a UTF-8 BOM when piping, which breaks JSON.parse.
    prompt = String(JSON.parse(input.replace(/^\uFEFF/, '')).prompt || '');
  } catch (e) {
    // Unparseable payload — fall through to the full ruleset rather
    // than risk silently dropping it.
    unreadable = true;
  }

  if (DEACTIVATE.test(prompt)) {
    deactivate();
    writeHookOutput('UserPromptSubmit', 'RTR-RE OFF — normal mode. A new session turns it back on.');
    return;
  }

  if (REACTIVATE.test(prompt)) {
    activate();
    writeHookOutput('UserPromptSubmit', getInstructions());
    return;
  }

  if (!isActive()) {
    return;
  }

  writeHookOutput('UserPromptSubmit', unreadable ? getInstructions() : getReminder());
}

process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', finish);

// Never hang the session. On Windows the hook runs through a PowerShell
// wrapper that can swallow the piped JSON, so 'end' may never fire.
process.stdin.on('error', () => { finish(); process.exit(0); });
setTimeout(() => { finish(); process.exit(0); }, 1000).unref();
