#!/usr/bin/env python3
"""RTR-RE installer — arcade remix production (pure ffmpeg).

Transforms the source track (See-Saw — Obsession) into three high-energy
arcade remix variants using only ffmpeg native filters — no WAV
intermediates, no external synthesis.

Each variant:
  1. `asetrate` + `aresample` — the natural arcade lift: tempo AND pitch
     rise together (the classic fast-forward character).
  2. Gentle EQ shaping — chiptune presence without destroying dynamics.
  3. `aecho` — the arcade space.
  4. A beat synthesized natively with `aevalsrc` (kick + hi-hat at the
     variant's BPM), mixed under the song.
  5. `loudnorm` — consistent, audible loudness (fixes the inaudible
     crush from the earlier bit-crusher approach).
"""

import argparse
import subprocess
from pathlib import Path

SOURCE = Path(r"C:/Music-Custom-Installer/See-Saw-Obsession.mp3")
OUT_DIR = Path(__file__).resolve().parent.parent / "shell" / "assets" / "audio"
FFMPEG = Path(r"C:/Hybrid/64bit/ffmpeg.exe")
FFPROBE = Path(r"C:/Hybrid/64bit/ffprobe.exe")

VARIANTS = {
    # rate = asetrate multiplier (tempo + pitch together)
    "quick": {"rate": 1.06, "bpm": 106, "beat_gain": 0.45},
    "custom": {"rate": 1.14, "bpm": 114, "beat_gain": 0.55},
    "hardcore": {"rate": 1.26, "bpm": 126, "beat_gain": 0.65},
}


def source_duration():
    out = subprocess.run(
        [
            str(FFPROBE),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(SOURCE),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def make_variant(name, cfg):
    rate = cfg["rate"]
    bpm = cfg["bpm"]
    beat_gain = cfg["beat_gain"]

    dur = source_duration() / rate
    beat_interval = 60.0 / bpm

    # kick + hat expression at the variant BPM
    beat_expr = (
        f"0.9*exp(-18*mod(t,{beat_interval}))*"
        f"sin(2*PI*(90+40*exp(-12*mod(t,{beat_interval})))*mod(t,{beat_interval}))"
        f"+0.25*(2*random(0)-1)*exp(-45*mod(t+{beat_interval / 2},{beat_interval}))"
    )

    out = OUT_DIR / f"obsession-{name}.mp3"
    subprocess.run(
        [
            str(FFMPEG),
            "-y",
            "-v",
            "error",
            "-i",
            str(SOURCE),
            "-f",
            "lavfi",
            "-i",
            f"aevalsrc=exprs='{beat_expr}':s=44100:d={dur:.2f}",
            "-filter_complex",
            (
                f"[0:a]asetrate=44100*{rate},aresample=44100,"
                f"highpass=f=90,lowpass=f=12500,"
                f"equalizer=f=2500:t=q:w=1:g=+2.5,"
                f"equalizer=f=7500:t=q:w=1:g=+2,"
                f"aecho=0.7:0.8:45|65:0.22|0.15,"
                f"loudnorm=I=-14:LRA=11:TP=-1.5[song];"
                f"[1:a]volume={beat_gain},"
                f"loudnorm=I=-18:LRA=9:TP=-2[beat];"
                f"[song][beat]amix=inputs=2:duration=first:dropout_transition=0,"
                f"alimiter=limit=0.95,"
                f"loudnorm=I=-14:LRA=11:TP=-1.5[out]"
            ),
            "-map",
            "[out]",
            "-b:a",
            "192k",
            str(out),
        ],
        check=True,
    )
    print(f"remix {name}: {out.name} ({out.stat().st_size} bytes)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=list(VARIANTS), default=None)
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    variants = [args.variant] if args.variant else list(VARIANTS)
    for name in variants:
        make_variant(name, VARIANTS[name])


if __name__ == "__main__":
    main()
