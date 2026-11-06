#!/usr/bin/env node
// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// SubagentStart — SessionStart context never reaches subagents, so
// delegated work would run memory-unaware without this.

const { getInstructions, isActive, writeHookOutput } = require('./rtr-core');

if (isActive()) {
  writeHookOutput('SubagentStart', getInstructions());
}
