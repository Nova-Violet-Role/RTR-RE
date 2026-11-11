// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// RTR-RE installer — theme registry.
// Each platform injects its personality: the shell reads the theme from
// the launcher (data-theme on <body>) and this module exposes the scene
// parameters (particle colors, camera behavior, core object).

const THEMES = {
  instrument: {
    id: "instrument",
    label: "The Instrument",
    platform: "pip / uvx",
    // WebGL scene parameters
    scene: {
      bg: [0.02, 0.04, 0.08],
      particleColor: [0.0, 0.9, 1.0],
      particleColor2: [0.12, 0.44, 1.0],
      floorReflect: 0.35,
      coreGlow: [0.0, 0.9, 1.0],
      cameraDrift: 0.0012,
      particleSpeed: 0.6,
    },
    // UI metaphors
    ui: {
      progressWaveform: true,   // oscilloscope trace style progress
      dials: true,              // vernier-style readouts
      crosshairHover: true,
    },
  },
  network: {
    id: "network",
    label: "The Network",
    platform: "npm",
    scene: {
      bg: [0.07, 0.02, 0.06],
      particleColor: [1.0, 0.24, 0.54],
      particleColor2: [0.54, 0.24, 1.0],
      floorReflect: 0.28,
      coreGlow: [1.0, 0.24, 0.54],
      cameraDrift: 0.0018,
      particleSpeed: 0.75,
    },
    ui: {
      progressWaveform: false,
      dials: false,
      crosshairHover: false,
      nodeGraph: true,          // component selection as node graph
    },
  },
  forge: {
    id: "forge",
    label: "The Forge",
    platform: "GitHub",
    scene: {
      bg: [0.04, 0.05, 0.07],
      particleColor: [0.0, 0.9, 0.46],
      particleColor2: [0.0, 0.69, 1.0],
      floorReflect: 0.42,
      coreGlow: [0.0, 0.9, 0.46],
      cameraDrift: 0.0009,
      particleSpeed: 0.5,
    },
    ui: {
      progressWaveform: false,
      dials: false,
      crosshairHover: false,
      terminalLog: true,        // terminal-style log panels
      scanlines: true,
    },
  },
}

function currentTheme() {
  const el = document.body
  const id = el.getAttribute("data-theme") || "instrument"
  return THEMES[id] || THEMES.instrument
}
