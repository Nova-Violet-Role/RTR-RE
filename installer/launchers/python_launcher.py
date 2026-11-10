#!/usr/bin/env python3
"""RTR-RE installer — native terminal launcher (Python stdlib only).

The installer runs entirely in the terminal — no browser, no HTTP, no
network. People launch it from uvx / npm / GitHub, all terminal contexts,
so the whole experience is terminal-native.

Architecture:
  - The three platform personalities are terminal color palettes declared
    in the scene DTD module (dtd/rtrre-scene.mod) and read from the scene
    XML instances. The renderer is a small ANSI/truecolor engine.
  - Audio: the arcade remix variants are played via the platform's
    native player (PowerShell on Windows, afplay on macOS, aplay on
    Linux) as a background process, so the UI never blocks.
  - The install plan and execution are direct function calls — there is
    no bridge at all.

Usage:
    python python_launcher.py [--theme instrument|network|forge]
                              [--project DIR] [--wheel PATH]
"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

SHELL_DIR = Path(__file__).resolve().parent.parent / "shell"
SCENES_DIR = SHELL_DIR / "dtd" / "scenes"
AUDIO_DIR = SHELL_DIR / "assets" / "audio"

# ---------------------------------------------------------------- ANSI engine


class Term:
    """Minimal ANSI/truecolor terminal renderer."""

    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    DIM = "\x1b[2m"
    CLEAR = "\x1b[2J\x1b[H"
    HIDE = "\x1b[?25l"
    SHOW = "\x1b[?25h"

    @staticmethod
    def rgb(r, g, b):
        return f"\x1b[38;2;{r};{g};{b}m"

    @staticmethod
    def bg(r, g, b):
        return f"\x1b[48;2;{r};{g};{b}m"

    @staticmethod
    def move(y, x):
        return f"\x1b[{y};{x}H"

    @staticmethod
    def clear_line():
        return "\x1b[2K"


# ---------------------------------------------------------------- scene / theme


def read_scene(theme, scenes_dir=None):
    """Parse the scene XML for a theme. The scene is a DTD family member:
    declared in rtrre-scene.mod, instantiated under dtd/scenes/.
    Never raises for scene data: unreadable files fall back to {},
    missing or garbage fields fall back to defaults. Cosmetics must
    never block installation."""
    base = Path(scenes_dir) if scenes_dir is not None else SCENES_DIR
    try:
        root = ET.parse(base / f"{theme}.xml").getroot()
    except (OSError, ET.ParseError) as exc:
        print(
            f"warning: scene {theme} unreadable ({exc}); using defaults",
            file=sys.stderr,
        )
        return {}

    def find(tag):
        found = root.find(tag)
        return found if found is not None else ET.Element(tag)

    def num(elem, attr, dflt):
        try:
            v = elem.get(attr)
            return float(v) if v is not None else dflt
        except (TypeError, ValueError):
            return dflt

    def col(elem, attr, dflt):
        try:
            parts = [int(float(x) * 255) for x in (elem.get(attr) or "").split(",")]
        except (TypeError, ValueError):
            return dflt
        return parts if len(parts) == 3 else dflt

    camera = find("camera")
    core = find("core")
    floor = find("floor")
    particles = find("particles")
    return {
        "camera": {
            "drift": num(camera, "drift", 0.0012),
            "pitch": num(camera, "pitch", -0.16),
        },
        "core": {
            "glow": col(core, "glow", [128, 128, 255]),
        },
        "floor": {
            "reflect": num(floor, "reflect", 0.35),
        },
        "particles": {
            "count": num(particles, "count", 900),
            "color": col(particles, "color", [0, 229, 255]),
            "color2": col(particles, "color2", [30, 111, 255]),
            "mix": num(particles, "color-mix", 0.6),
            "speed": num(particles, "speed", 0.6),
        },
    }


def animate_params(scene):
    """Derive terminal animation timing/density from the declared scene,
    so the graphics are inferred from the DTD family member (rtrre-scene.mod)
    instead of hardcoded pixels. Degenerate input falls back to defaults."""

    def num(key, dflt):
        try:
            value = float(particles.get(key, dflt))
        except (TypeError, ValueError):
            return dflt
        return value if math.isfinite(value) else dflt

    particles = {}
    if isinstance(scene, dict):
        particles = scene.get("particles", {}) or {}
    count = num("count", 900.0)
    speed = num("speed", 0.6)
    mix = num("mix", 0.6)
    return {
        "density": min(0.20, max(0.02, 0.06 * (count / 900.0))),
        "sleep": (1.0 / 12.0) * (0.6 / max(speed, 0.1)),
        "ratio": min(1.0, max(0.0, mix)),
    }


THEMES = {
    "instrument": {
        "label": "The Instrument",
        "platform": "pip / uvx",
        "accent": (0, 229, 255),
        "accent2": (30, 111, 255),
    },
    "network": {
        "label": "The Network",
        "platform": "npm",
        "accent": (255, 61, 138),
        "accent2": (138, 61, 255),
    },
    "forge": {
        "label": "The Forge",
        "platform": "GitHub",
        "accent": (0, 230, 118),
        "accent2": (0, 176, 255),
    },
}

# ---------------------------------------------------------------- components / presets

COMPONENTS = [
    ("keeper", "Keeper", "window edge · eviction · protection", True),
    ("compressor", "Compressor", "verbatim eviction · background tickets", True),
    ("engine", "Engine", "dual-ONNX retrieval core", True),
    ("plugin", "OpenCode plugin", "keeper + ctrl+p palette", False),
    ("optimizer", "Optimizer", "machine-aware recommendations", False),
    ("presets", "Preset registry", "MUGEN · Symbiose-AH! · Fusion-AH!", True),
    ("cli", "CLI", "rtr-cli bridge (no-MCP mode)", False),
    ("memory", "Memory root", ".opencode/memory/ (DTD-shaped)", True),
]

TIPS = {
    "threads": "Did you know: scores are flat from T4 to T16 — threads buy speed, not quality.",
    "parking": "Did you know: P20 on a small-RAM machine lets the SSD act as the memory mitigation.",
    "mugen": "Did you know: MUGEN (400k/200k/200) is the infinite-memory preset.",
    "modality": "Did you know: rtr-full loads two ONNX models; single-model modalities halve resident RAM.",
}

RECOMMEND = {
    "threads": "Recommended from Saimonokuma: 8 threads — T8 is the speed sweet spot on 32-thread hosts.",
    "parking": "Recommended from Saimonokuma: P40 — balances headroom on 32-thread hosts.",
}

EASTER_CITATION = (
    "In Blue Submarine No. 6, the sea itself becomes a question: when nature is "
    "reshaped into new forms of life, what does it mean to be alive — and two "
    "friends find the way to save a world that has already changed. In Heroes, "
    "Emma Coolidge hears data as music and sees it as color — perception beyond "
    "the measurable. MiDi-MoE-Symbiogen-000 asks the same question: what if data "
    "could be anything, anywhere, at the same time? Not stored, but dwelling — a "
    "virus, a bacterium, an animal, an intelligence that provides for its own "
    "sake. Temporalism cannot be measured. But what if it could be felt?"
    " Symbiogen-003 Automata tends what dwells: patient processes "
    "that keep the stored world, as lighthouse keepers keep the light. "
    "Symbiogen-004 Errata keeps what failed: every error indexed, "
    "every mistake retrievable, nothing repeated. Between them "
    "runs the IRC bridge, and across it weight-transfer units move "
    "as MIDI frequency transfer — instruction as music, perception "
    "as protocol. To cross is personality transposition: arrival "
    "changes the traveler, and the change is the message."
)

# ---------------------------------------------------------------- audio


def linux_player_cmd(variant):
    """First available MP3-capable Linux player (aplay cannot decode MP3)."""
    if shutil.which("mpg123"):
        return ["mpg123", str(variant)]
    if shutil.which("mpv"):
        return ["mpv", "--no-video", str(variant)]
    if shutil.which("ffplay"):
        return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", str(variant)]
    return None


def windows_media_command(variant):
    """PowerShell that plays MP3 via WMP-COM and stays alive for the track.
    WMPlayer.OCX is in-proc (proven: playing with zero wmplayer.exe), so
    exiting the host stops the music — the loop polls playState until the
    track ends (states 1/8) or a 10-minute cap, then exits."""
    return (
        "$wmp = New-Object -ComObject WMPlayer.OCX; "
        f"$wmp.URL = '{Path(variant).as_posix()}'; "
        "$wmp.controls.play(); "
        "$t = 0; while ($t -lt 600 "
        "-and @(1,8) -notcontains $wmp.playState) "
        "{ Start-Sleep -Seconds 5; $t += 5 }"
    )


def play_audio(preset):
    """Play the remix variant via the platform's native player, detached."""
    if os.environ.get("RTRRE_INSTALL_NO_AUDIO") == "1":
        return
    variant = AUDIO_DIR / f"obsession-{preset}.mp3"
    if not variant.exists():
        return
    try:
        if sys.platform == "win32":
            # Windows Media Player COM plays MP3 natively — no extra files.
            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    windows_media_command(variant),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif sys.platform == "darwin":
            subprocess.Popen(
                ["afplay", str(variant)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            cmd = linux_player_cmd(variant)
            if not cmd:
                return
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


# ---------------------------------------------------------------- install actions


def plan_for(payload):
    preset = payload.get("preset", "quick")
    if preset == "manual":
        return [
            ("preset", "manual (palette guide + your knobs, no automation)"),
            ("threads", f"T{payload.get('threadsPerModel', 8)} (2/4/6/8/12/16)"),
            ("parking", f"P{payload.get('parkingPercent', 60)} (20-80)"),
            ("mode", "manual: auto trigger/target/max OFF, one-shots only"),
            ("engine", "rtr-full · dual-ONNX"),
            ("plugin", "keeper + ctrl+p palette"),
            ("memory", ".opencode/memory/ (DTD-shaped)"),
        ]
    if preset == "quick":
        return [
            ("preset", "re-symbiose-mugen (400k/200k/200)"),
            ("engine", "rtr-full · dual-ONNX"),
            ("profile", "local-system · T8/P80"),
            ("plugin", "keeper + ctrl+p palette"),
            ("memory", ".opencode/memory/ (DTD-shaped)"),
        ]
    if preset == "custom":
        comps = payload.get("components") or []
        return [
            ("components", ", ".join(comps)),
            ("engine", "rtr-full · dual-ONNX"),
            ("profile", "local-system · T8/P80"),
            ("plugin", "keeper + ctrl+p palette"),
            ("memory", ".opencode/memory/ (DTD-shaped)"),
        ]
    return [
        ("preset", payload.get("presetName", "re-symbiose-mugen")),
        ("threads", str(payload.get("threads", 8))),
        ("parking", str(payload.get("parking", 40)) + "%"),
        ("modality", payload.get("modality", "rtr-full")),
        ("trigger", str(payload.get("triggerTokens", 400000))),
        ("target", str(payload.get("targetTokens", 200000))),
        ("max", str(payload.get("maxKeepMessages", 200))),
        ("engine", "rtr-full · dual-ONNX"),
        ("plugin", "keeper + ctrl+p palette"),
        ("memory", ".opencode/memory/ (DTD-shaped)"),
    ]


def execute_plan(payload, project, wheel):
    preset = payload.get("preset", "quick")
    cfg_dir = Path(project) / ".opencode"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "preset": payload.get("presetName", "re-symbiose-mugen")
        if preset == "hardcore"
        else "re-symbiose-mugen",
        "cpuProfile": "local-system",
        "enabled": True,
    }
    if preset == "hardcore":
        cfg["threadsPerModel"] = payload.get("threads", 8)
        cfg["parkingPercent"] = payload.get("parking", 40)
        cfg["modality"] = payload.get("modality", "rtr-full")
        cfg["triggerTokens"] = payload.get("triggerTokens", 400000)
        cfg["targetTokens"] = payload.get("targetTokens", 200000)
        cfg["maxKeepMessages"] = payload.get("maxKeepMessages", 200)
    if preset == "manual":
        del cfg["preset"]
        cfg["manual"] = True
        cfg["threadsPerModel"] = payload.get("threadsPerModel", 8)
        cfg["parkingPercent"] = payload.get("parkingPercent", 60)
        try:
            guide = (SHELL_DIR / "assets" / "palette-guide.txt").read_text(
                encoding="utf-8"
            )
            mem_dir = Path(project) / ".opencode" / "memory"
            mem_dir.mkdir(parents=True, exist_ok=True)
            (mem_dir / "rtrre-palette-guide.txt").write_text(guide, encoding="utf-8")
        except Exception:
            pass
    (cfg_dir / "rtr-re-keeper.json").write_text(
        json.dumps(cfg, indent=2), encoding="utf-8"
    )
    if wheel and Path(wheel).exists():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", wheel],
            check=False,
        )
        if result.returncode != 0:
            return False
    return True


def validated_int(text, default, lo, hi):
    """Hardcore input validation: empty takes the default, in-range ints
    pass, anything else signals retry. Returns (ok, value).
    Registry membership stays keeper-owned (single validator)."""
    s = str(text).strip() if text is not None else ""
    if not s:
        return True, default
    try:
        v = int(s)
    except ValueError:
        return False, None
    return (True, v) if lo <= v <= hi else (False, None)


# ---------------------------------------------------------------- terminal UI


class InstallerUI:
    def __init__(self, theme, project, wheel):
        self.theme = theme
        self.meta = THEMES[theme]
        self.scene = read_scene(theme) or {}
        self.project = project
        self.wheel = wheel
        self.accent = self.meta["accent"]
        self.accent2 = self.meta["accent2"]
        self.preset = "quick"
        self.audio_played = set()
        self.components = {cid for cid, _, _, req in COMPONENTS if req}
        self.hardcore = {
            "threads": 8,
            "parking": 40,
            "presetName": "re-symbiose-mugen",
            "modality": "rtr-full",
            "triggerTokens": 400000,
            "targetTokens": 200000,
            "maxKeepMessages": 200,
        }
        self.manual = {
            "threadsPerModel": 8,
            "parkingPercent": 60,
        }

    # ---- primitives ----
    def paint(self, text, color=None, bold=False, dim=False):
        out = ""
        if color:
            out += Term.rgb(*color)
        if bold:
            out += Term.BOLD
        if dim:
            out += Term.DIM
        return out + text + Term.RESET

    def banner(self):
        lines = [
            "  ╔══════════════════════════════════════════════════════════════╗",
            "  ║   RTR-RE:Symbiose — Installer                               ║",
            f"  ║   {self.meta['label']} · {self.meta['platform']:<28}║",
            "  ╚══════════════════════════════════════════════════════════════╝",
        ]
        return "\n".join(self.paint(l, self.accent, bold=True) for l in lines)

    def header(self):
        return (
            self.banner()
            + "\n\n"
            + self.paint(
                "  Enter RTR-RE — choose how you want to arrive.\n", self.accent
            )
        )

    # ---- particle field animation ----
    def animate(self, seconds=1.2, width=60, height=8):
        """A lightweight memory-stream particle animation in the terminal."""
        import random

        rng = random.Random()
        cols = [self.accent, self.accent2]
        params = animate_params(self.scene)
        for frame in range(int(seconds * 12)):
            rows = []
            for y in range(height):
                row = []
                for x in range(width):
                    if rng.random() < params["density"]:
                        c = cols[0] if rng.random() < params["ratio"] else cols[1]
                        row.append(self.paint("·", c))
                    else:
                        row.append(" ")
                rows.append("".join(row))
            sys.stdout.write(Term.move(2, 1) + "\n".join(rows))
            sys.stdout.flush()
            time.sleep(params["sleep"])

    # ---- personality renderers ----
    def personality(self):
        return self.theme  # instrument | network | forge

    def render_progress(self, index, total, k, v):
        """Draw one progress step in the theme's interface personality."""
        pct = int((index + 1) / total * 100)
        if self.personality() == "forge":
            # Raw terminal: commands stream like a build log.
            line = f"  $ {k}: {v}"
            done = "✓" if index < total - 1 else "✓"
            return f"  {self.paint(done, self.accent)} {line}"
        if self.personality() == "network":
            # Node graph: nodes light up and connect to the core.
            nodes = "".join("●" if i <= index else "○" for i in range(total))
            return f"  {self.paint(nodes, self.accent)} {pct:3d}%  {k}: {v}"
        # instrument: oscilloscope waveform + measurement readout
        wave = "▁▂▃▅▆▇█▇▆▅▃▂▁"
        pos = int(pct / 100 * (len(wave) - 1))
        w = wave[: pos + 1] + " " * (len(wave) - pos - 1)
        return f"  {self.paint(w, self.accent)} {pct:3d}%  {k}: {v}"

    def render_plan(self, plan):
        if self.personality() == "forge":
            return "\n".join(f"  $ {self.paint(k, self.accent)} {v}" for k, v in plan)
        return "\n".join(f"    {k:<12} {v}" for k, v in plan)

    # ---- screens ----
    def screen_presets(self):
        sys.stdout.write(Term.CLEAR + self.header())
        print(
            self.paint(
                "  [1] Quick Install — MUGEN · 400k/200k/200 · one click",
                self.accent,
                bold=True,
            )
        )
        print(
            self.paint(
                "  [2] Custom Selection — choose components · balanced", self.accent2
            )
        )
        print(
            self.paint(
                "  [3] Hardcore — full control · every option · 8 threads/P40",
                self.accent,
            )
        )
        print(
            self.paint(
                "  [4] Manual — palette guide · roomy 600k/300k/200 · you drive",
                self.accent2,
            )
        )
        print()
        choice = input("  Select [1/2/3/4]: ").strip()
        if choice == "2":
            self.preset = "custom"
            self.screen_custom()
        elif choice == "3":
            self.preset = "hardcore"
            self.screen_hardcore()
        elif choice == "4":
            self.preset = "manual"
            self.screen_manual()
        else:
            self.preset = "quick"
            self.screen_review()

    def screen_manual(self):
        sys.stdout.write(Term.CLEAR + self.header())
        print(
            self.paint(
                "  Manual preset — professional manual context care.\n",
                self.accent,
                bold=True,
            )
        )
        try:
            print(
                (SHELL_DIR / "assets" / "palette-guide.txt").read_text(encoding="utf-8")
            )
        except Exception:
            print("  (palette guide unavailable in this package)")
        m = self.manual
        m["threadsPerModel"] = self._prompt_int(
            f"  Threads per model T-modes 2/4/6/8/12/16 [{m['threadsPerModel']}]: ",
            m["threadsPerModel"],
            2,
            16,
        )
        m["parkingPercent"] = self._prompt_int(
            f"  Parking percent 20-80 [{m['parkingPercent']}]: ",
            m["parkingPercent"],
            20,
            80,
        )
        print(
            "  "
            + self.paint(
                "Manual has no automatic trigger, target, or max:"
                " you evict via palette one-shots.",
                dim=True,
            )
        )
        self.screen_review()

    def screen_custom(self):
        sys.stdout.write(Term.CLEAR + self.header())
        print(
            self.paint(
                "  Select components (toggle with number, Enter when done):\n",
                self.accent,
            )
        )
        for i, (cid, name, desc, req) in enumerate(COMPONENTS, 1):
            mark = "●" if cid in self.components else "○"
            req_note = " (required)" if req else ""
            print(f"  [{i}] {mark} {name}{req_note} — {desc}")
        print()
        while True:
            line = input("  Toggle [1-8], Enter to continue: ").strip()
            if not line:
                break
            for tok in line.split():
                if tok.isdigit() and 1 <= int(tok) <= 8:
                    cid = COMPONENTS[int(tok) - 1][0]
                    if not COMPONENTS[int(tok) - 1][3]:
                        if cid in self.components:
                            self.components.discard(cid)
                        else:
                            self.components.add(cid)
            sys.stdout.write(Term.move(12, 1) + Term.clear_line())
            sys.stdout.flush()
        self.screen_review()

    @staticmethod
    def _prompt_int(prompt, default, lo, hi):
        while True:
            ok, value = validated_int(input(prompt), default, lo, hi)
            if ok:
                return value
            print(f"  Enter a whole number {lo}-{hi} (empty keeps {default}).")

    def screen_hardcore(self):
        sys.stdout.write(Term.CLEAR + self.header())
        print(
            self.paint("  Hardcore cockpit — every option.\n", self.accent, bold=True)
        )
        h = self.hardcore
        h["threads"] = self._prompt_int(
            f"  Threads [{h['threads']}]: ", h["threads"], 1, 64
        )
        print("  " + self.paint(RECOMMEND["threads"], self.accent))
        h["parking"] = self._prompt_int(
            f"  Parking % [{h['parking']}]: ", h["parking"], 0, 100
        )
        print("  " + self.paint(RECOMMEND["parking"], self.accent))
        print("  " + self.paint(TIPS["threads"], dim=True))
        print("  " + self.paint(TIPS["parking"], dim=True))
        print()
        h["presetName"] = input("  Preset [re-symbiose-mugen]: ") or "re-symbiose-mugen"
        print("  " + self.paint(TIPS["mugen"], dim=True))
        h["modality"] = input("  Modality [rtr-full]: ") or "rtr-full"
        print("  " + self.paint(TIPS["modality"], dim=True))
        h["triggerTokens"] = self._prompt_int(
            f"  Trigger tokens [{h['triggerTokens']}]: ",
            h["triggerTokens"],
            1000,
            100000000,
        )
        h["targetTokens"] = self._prompt_int(
            f"  Target tokens [{h['targetTokens']}]: ",
            h["targetTokens"],
            1000,
            100000000,
        )
        h["maxKeepMessages"] = self._prompt_int(
            f"  Max messages [{h['maxKeepMessages']}]: ",
            h["maxKeepMessages"],
            1,
            10000,
        )
        self.screen_review()

    def screen_review(self):
        if self.preset not in self.audio_played:
            play_audio(self.preset)
            self.audio_played.add(self.preset)
        payload = {"preset": self.preset}
        if self.preset == "custom":
            payload = {"preset": self.preset, "components": sorted(self.components)}
        elif self.preset == "hardcore":
            payload = {"preset": self.preset, **self.hardcore}
        elif self.preset == "manual":
            payload = {"preset": self.preset, **self.manual}
        plan = plan_for(payload)
        sys.stdout.write(Term.CLEAR + self.header())
        print(self.paint("  Install plan:\n", self.accent, bold=True))
        print(self.render_plan(plan))
        print()
        if input("  Install now? [Y/n]: ").strip().lower() in ("", "y", "yes"):
            self.screen_progress(payload, plan)
        else:
            self.screen_presets()

    def screen_progress(self, payload, plan):
        sys.stdout.write(Term.CLEAR + self.header())
        print(
            self.paint(
                "  Installing — the memory is being entered.\n", self.accent, bold=True
            )
        )
        total = len(plan)
        for i, (k, v) in enumerate(plan):
            sys.stdout.write(Term.move(6 + i, 1) + Term.clear_line())
            print(self.render_progress(i, total, k, v))
            sys.stdout.flush()
            time.sleep(0.35)
        ok = execute_plan(payload, self.project, self.wheel)
        sys.stdout.write(Term.move(6 + total, 1) + Term.clear_line())
        if not ok:
            print(
                self.paint(
                    f"  ✗ package install failed for {self.wheel} — check the path, then retry.",
                    self.accent,
                    bold=True,
                )
            )
            input("  Press Enter to return to the plan. ")
            self.screen_review()
            return
        if self.personality() == "forge":
            print(f"  {self.paint('✓', self.accent2)} build complete — 100%")
        else:
            print(f"  {self.paint('█' * 25, self.accent2)} 100%  done")
        time.sleep(0.6)
        self.screen_done()

    def screen_done(self):
        sys.stdout.write(Term.CLEAR + self.header())
        print(
            self.paint(
                "  RTR-RE installed. The memory is in. The world is entered.\n",
                self.accent,
                bold=True,
            )
        )
        if input("  Awaken MiDi-MoE-Symbiogen-000? [y/N]: ").strip().lower() in (
            "y",
            "yes",
        ):
            print()
            print(self.paint("  MiDi-MoE-Symbiogen-000", self.accent, bold=True))
            print("  " + EASTER_CITATION)
            print()
        input("  Press Enter to close. ")

    def run(self):
        self.animate()
        self.screen_presets()


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description="RTR-RE installer (terminal)")
    ap.add_argument("--theme", default="instrument", choices=list(THEMES))
    ap.add_argument("--project", default=None)
    ap.add_argument("--wheel", default=None)
    args = ap.parse_args()

    project = args.project or os.environ.get("RTRRE_INSTALL_PROJECT") or os.getcwd()
    wheel = args.wheel or os.environ.get("RTRRE_INSTALL_WHEEL")

    ui = InstallerUI(args.theme, project, wheel)
    try:
        ui.run()
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    finally:
        sys.stdout.write(Term.SHOW)


if __name__ == "__main__":
    main()
