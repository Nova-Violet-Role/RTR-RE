#!/usr/bin/env node
// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// SessionStart — a new session always starts with rtr-re on, so clear
// any "off" left by a previous one, then inject the ruleset.

const { activate, getInstructions, writeHookOutput } = require('./rtr-core');

activate();
writeHookOutput('SessionStart', getInstructions());
