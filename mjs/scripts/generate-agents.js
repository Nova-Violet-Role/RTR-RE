// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// AGENTS.md is generated from the skill body: one source of truth, the
// generated file is the standalone fallback getInstructions() reads
// when the skill is missing. Run after every SKILL.md edit:
//   node scripts/generate-agents.js
// The test suite asserts the two files agree, so drift fails loudly.

const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const skill = fs.readFileSync(path.join(root, 'skills', 'rtr', 'SKILL.md'), 'utf8');
const body = skill.replace(/^---[\s\S]*?\n---\s*/, '').trim() + '\n';
fs.writeFileSync(path.join(root, 'AGENTS.md'), body, 'utf8');
console.log(`AGENTS.md regenerated (${Buffer.byteLength(body)} bytes)`);
