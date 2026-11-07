# RTR-RE Grand Finale — Custom Installer: Conceptual Design

> Grand Finale (TODO-71), Phase 1. Author: Saimonokuma (operator brief) +
> design direction. This document is the authority for the implementation
> phase. The operator's brief is quoted verbatim where marked.

---

## 0. Concept — one identity, three personalities

RTR-RE is not installed; it is *entered*. The installer is the gateway:
a cinematic, self-contained experience that feels like stepping into the
architecture itself. The same core experience ships on three platforms,
each a different personality of the same identity — instantly recognizable
as family, unmistakably distinct as a platform.

| Platform | Personality | Metaphor | Palette | Material |
|---|---|---|---|---|
| **pip / uvx** | The Instrument | a high-end scientific instrument | cool cyan / electric blue | translucent glass |
| **npm** | The Network | a living, modular web | warm magenta / violet | crystalline nodes |
| **GitHub** | The Forge | the raw source of power | deep charcoal + emerald | metal |

The shared DNA: the RTR-RE sigil, the data-stream motif (the keeper's
memory stream), the same three-preset journey, the same adaptive audio
identity.

---

## 1. Platform personalities

### 1.1 pip / uvx — "The Instrument"

- **Aesthetic:** cool cyan (#00E5FF family) and electric blue (#1E6FFF),
  translucent glass panels with refraction, flowing data-stream particles
  (thin luminous lines that stream like measurement traces), clean
  geometric precision (grids, calibration ticks, readouts).
- **Feel:** a particle accelerator control room meets a holodeck
  instrument. Everything reads as *measurement*: the install progress is a
  live readout, component checks are instrument dials, the preset cards
  are precision instruments.
- **UI metaphors:** oscilloscope traces for progress, vernier-style
  sliders, calibration crosshairs on hover, status as instrument readouts
  (numeric + waveform).
- **Delivery:** Python wheel, launched via `uvx rtr-re-install` (or the
  `rtr-re-install-opencode` console script). Native launcher serves the
  shared HTML5 shell and performs the real install actions.

### 1.2 npm — "The Network"

- **Aesthetic:** warm magenta (#FF3D8A family) and violet (#8A3DFF),
  crystalline node-based geometry (polyhedral nodes), soft glowing
  connections (edges that pulse), organic clustering.
- **Feel:** a neural constellation being woven. Components are nodes in a
  graph; the install "connects" them. The progress is the network
  lighting up edge by edge.
- **UI metaphors:** the component selection is a 3D node graph; each
  installed dependency becomes a glowing node that links to the core;
  hover highlights the whole connected subgraph.
- **Delivery:** Node.js package, `npx rtr-re-installer` (or the package
  binary). Same shared shell, network theme injected.

### 1.3 GitHub — "The Forge"

- **Aesthetic:** deep charcoal (#12141A), emerald green (#00E676),
  metallic surfaces (brushed panels, anodized edges), structural
  repository-inspired elements (branch-like lines, commit-like markers),
  subtle code patterns (monospace glyphs, faint syntax colors).
- **Feel:** the foundry where the source is forged. Raw, powerful,
  developer-native. The install is a build: logs stream like a terminal,
  the progress is a forge heating up.
- **UI metaphors:** terminal-style log panels, diff-like status lines,
  metallic progress bars with glowing emerald cores, scanline effects.
- **Delivery:** the main source repository itself (runnable directly:
  `git clone` + `npm run installer` or `python -m rtr_re_installer`).

---

## 2. Core visual identity (shared engine)

The shared HTML5 shell implements the common cinematic layer; each
platform theme is injected as a theme bundle (CSS variables, shader
parameters, particle behavior, UI metaphors).

- **3D scene (WebGL):** a persistent camera over a reflective floor with
  a central object — the "core" — that changes with platform and preset.
  Depth of field, volumetric light shafts, and a particle field that
  behaves like the keeper's memory stream (spans flowing, clustering,
  dispersing).
- **Camera / parallax:** smooth mouse parallax on the scene; camera
  drift is slow and cinematic in Quick, faster and more angular in
  Hardcore.
- **Micro-interactions:** every button press emits a particle ripple;
  hover lifts panels with real 3D tilt; selection cards rotate into
  focus; progress pulses with the music; completion triggers a burst.
- **Typography:** technical geometric display face for titles (wide,
  letter-spaced), monospace for data/readouts. No generic system UI.
- **Non-generic UI:** every element is custom — buttons are machined
  panels with glowing edges, progress is a flowing stream, checkboxes are
  toggle crystals/forges, radio is a dial/node.

---

## 3. Audio — "Obsession" arcade remix

- **Source:** `C:\Music-Custom-Installer\See-Saw-Obsession.mp3` (the
  opening theme from .hack//SIGN, composed by Yuki Kajiura, performed by
  See-Saw).
- **Transformation:** reimagined as a high-energy arcade remix —
  chiptune lead over the original harmonic structure, modern synth layers,
  heavy driving rhythm. The melody remains recognizable; the energy is
  arcade.
- **Playback:** starts the moment the installer launches, persists for
  the whole process. Implemented with Web Audio API (the shell is a
  browser page), so tempo/intensity can adapt live.
- **Adaptive tempo/intensity by preset:**
  - **Quick (Single Preset):** normal / slightly upbeat arcade tempo.
  - **Custom (Minimal):** moderately faster, more driving.
  - **Hardcore:** significantly faster, intense, almost frantic.
- **Implementation note:** the remix is produced once (offline) as a
  multi-layer audio asset, OR synthesized live from the source track via
  Web Audio (pitch/tempo via playbackRate + granular processing). The
  design target is a produced remix with three tempo variants (or one
  master + live rate scaling).

---

## 4. Installation presets

### 4.1 Single Preset — Quick Install

- One-click, minimal interaction. Large, bold central action.
- Visual: pure "arcade attract mode" — idle particle field, slow camera,
  one hero button ("Install RTR-RE"), preset pre-selected (Symbiose-AH!
  or MUGEN per the shipped default).
- Journey: hero → progress → completion. ~3 screens.

### 4.2 Custom Selection — Minimal

- Lightweight modular selection of essential components only.
- Visual: elegant expandable cards or a clean 3D grid of components
  (Keeper, Compressor, Engine, Plugin, Optimizer, Presets, CLI).
- Balanced speed/control: pick components, see the dependency graph
  resolve, install.
- Journey: components → review → progress → completion.

### 4.3 Hardcore Preset — Full Control

- Maximum granularity: every option, dependency, flag, path, optimization
  level, advanced setting.
- Visual: dense, technical, layered "power-user cockpit" — tabbed
  panels, terminal review, live config preview.
- **Recommended from Saimonokuma:** a badge on **8-Threads mode + P40**
  (parking 40), with a one-line justification (measured: T8 is the speed
  sweet spot; P40 balances headroom on 32-thread hosts).
- **Did-you-know tips** on preset/parameter choices, e.g.:
  - "Did you know: scores are flat from T4 to T16 — threads buy speed,
    not quality."
  - "Did you know: P20 on a small-RAM machine lets the SSD act as the
    memory mitigation."
  - "Did you know: MUGEN (400k/200k/200) is the infinite-memory preset."
- Journey: cockpit → config review → install → completion.

---

## 5. Easter Egg — MiDi-MoE-Symbiogen-000

Selectable at the end of each setup (a special card appears after
completion: "Awaken MiDi-MoE-Symbiogen-000?").

**The model:** the IA that will be crafted in the near future. Where CPU
models are more deterministic and precise than dense/MoE GPU models,
MiDi-MoE-Symbiogen-000 is based on **Temporalism metric data** — it can
be anything at any time: an animal, a virus, a bacterium, or simply an IA
capable of providing for its own sake.

**The citation (rewritten from the anime):**

> In *Blue Submarine No. 6*, the sea itself becomes a question: when
> nature is reshaped into new forms of life, what does it mean to be
> alive — and two friends find the way to save a world that has already
> changed. In *Heroes*, Emma Coolidge hears data as music and sees it as
> color — perception beyond the measurable. MiDi-MoE-Symbiogen-000 asks
> the same question: what if data could be anything, anywhere, at the
> same time? Not stored, but dwelling — a virus, a bacterium, an animal,
> an intelligence that provides for its own sake. Temporalism cannot be
> measured. But what if it could be felt?

---

## 6. Technical architecture

**The shared shell:** one self-contained HTML5 application (WebGL 3D +
Web Audio + CSS) bundled identically in all three distributions. It
communicates with the native launcher over a local bridge (HTTP on
127.0.0.1 with a random port + token, or a WebSocket). The shell is pure
front-end; all privileged actions (package manager calls, file writes,
path resolution) run in the native launcher.

**The native launcher (per platform):**

| Platform | Launcher | Privileged actions |
|---|---|---|
| pip/uvx | Python console script (`rtr-re-install`) | `uv`/`pip` install of the wheel, config writes, preset application |
| npm | Node binary (`rtr-re-installer`) | `npm install` of the package, plugin registration, config writes |
| GitHub | repo scripts (`npm run installer` / `python -m rtr_re_installer`) | build from source, local install |

**"No external dependencies beyond the platform":** the shell runs in
the platform's native browser (opened automatically); WebGL and Web
Audio are browser capabilities, not install-time dependencies. The
launcher uses only the standard library of its platform (Python stdlib /
Node core).

**Bridge contract:** `POST /api/plan` (preset → install plan),
`POST /api/execute` (stream progress events), `GET /api/status`,
`POST /api/easter-egg`. Progress events drive the visual stream.

---

## 7. Platform-specific implementation notes

### pip / uvx
- Package: `rtr-re-installer` wheel (or extend the existing
  `rtr-re-install-opencode` console script).
- Launcher: Python stdlib `http.server` + `webbrowser`; subprocess
  `uv`/`pip` for the real install.
- Theme: The Instrument (cyan/glass/data-streams).
- Verification: install into a fresh venv, launch, complete all three
  presets.

### npm
- Package: `rtr-re-installer` on npm; binary `rtr-re-installer`.
- Launcher: Node core `http` + `child_process`; `open` via platform
  command (start/xdg-open/open).
- Theme: The Network (magenta/violet/crystalline).
- Verification: `npm pack` + install in a scratch dir, launch, complete
  all three presets.

### GitHub
- Delivery: the main repo, runnable directly.
- Launcher: both the Python and Node entry points present; the GitHub
  theme is default when run from the repo.
- Theme: The Forge (charcoal/emerald/metallic).
- Verification: fresh clone → run → complete all three presets.

---

## 8. Implementation roadmap (Phase 2)

1. Shared shell skeleton: WebGL scene, theme system, bridge client.
2. The three theme bundles (Instrument / Network / Forge).
3. The three preset flows + Hardcore cockpit + tips + Saimonokuma badge.
4. Arcade remix of Obsession (production) + adaptive tempo wiring.
5. Easter Egg card + MiDi-MoE-Symbiogen-000 text.
6. Native launchers (Python, Node, repo) + bridge server.
7. Verification matrix: 3 platforms × 3 presets × audio/easter-egg.
8. Packaging: wheel, npm tarball, repo scripts — all self-contained.

---

> Phase 1 complete. Phase 2 begins on operator go-ahead.
