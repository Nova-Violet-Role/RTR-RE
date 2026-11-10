// RTR-RE installer — presets, components, tips.

const COMPONENTS = [
  { id: "keeper", name: "Keeper", desc: "window edge · eviction · protection", required: true },
  { id: "compressor", name: "Compressor", desc: "verbatim eviction · background tickets", required: true },
  { id: "engine", name: "Engine", desc: "dual-ONNX retrieval core", required: true },
  { id: "plugin", name: "OpenCode plugin", desc: "keeper + ctrl+p palette", required: false },
  { id: "optimizer", name: "Optimizer", desc: "machine-aware recommendations", required: false },
  { id: "presets", name: "Preset registry", desc: "MUGEN · Symbiose-AH! · Fusion-AH!", required: true },
  { id: "cli", name: "CLI", desc: "rtr-cli bridge (no-MCP mode)", required: false },
  { id: "memory", name: "Memory root", desc: ".opencode/memory/ (DTD-shaped)", required: true },
]

const TIPS = {
  threads: "Did you know: scores are flat from T4 to T16 — threads buy speed, not quality.",
  parking: "Did you know: P20 on a small-RAM machine lets the SSD act as the memory mitigation.",
  mugen: "Did you know: MUGEN (400k/200k/200) is the infinite-memory preset.",
  modality: "Did you know: rtr-full loads two ONNX models; single-model modalities halve resident RAM.",
}

const RECOMMEND = {
  threads: "Recommended from Saimonokuma: 8 threads — T8 is the speed sweet spot on 32-thread hosts.",
  parking: "Recommended from Saimonokuma: P40 — balances headroom on 32-thread hosts.",
}

const EASTER_CITATION =
  "In Blue Submarine No. 6, the sea itself becomes a question: when nature is " +
  "reshaped into new forms of life, what does it mean to be alive — and two " +
  "friends find the way to save a world that has already changed. In Heroes, " +
  "Emma Coolidge hears data as music and sees it as color — perception beyond " +
  "the measurable. MiDi-MoE-Symbiogen-000 asks the same question: what if data " +
  "could be anything, anywhere, at the same time? Not stored, but dwelling — a " +
  "virus, a bacterium, an animal, an intelligence that provides for its own " +
  "sake. Temporalism cannot be measured. But what if it could be felt?" +
  " Symbiogen-003 Automata tends what dwells: patient processes " +
  "that keep the stored world, as lighthouse keepers keep the light. " +
  "Symbiogen-004 Errata keeps what failed: every error indexed, " +
  "every mistake retrievable, nothing repeated. Between them " +
  "runs the IRC bridge, and across it weight-transfer units move " +
  "as MIDI frequency transfer — instruction as music, perception " +
  "as protocol. To cross is personality transposition: arrival " +
  "changes the traveler, and the change is the message."
