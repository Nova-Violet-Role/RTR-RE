<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Tessersect media tech spec (generated sources, not staged video)

Four distinct 480p collages, each 135 s (>2 min), 5 fps, h264, 854x480.
Preset: torch (Intersect 1-bit, 5 fps, 480p ladder). Subtitles are baked
into the frames (high-contrast PIL captions + SUB: footer on every frame),
so they survive the 1-bit threshold by construction — plus sidecar
WebVTT-style `.srt` files (26 cues each, 5 s windows) ship next to every
mp4 for players that prefer text tracks.

| File | POV | Frames | s/image | Duration | Bytes out | Source bytes |
|---|---|---:|---:|---:|---:|---:|
| media/tessersect-a-480p.mp4 | A binary Versus | 26 | 5 | 135.0 s | 121582 | 342125 |
| media/tessersect-b-480p.mp4 | B graded gold-v2 | 26 | 5 | 135.0 s | 118339 | 337867 |
| media/tessersect-c-480p.mp4 | C live loop | 26 | 5 | 135.0 s | 117546 | 326891 |
| media/tessersect-d-480p.mp4 | D dummy5 live instances | 26 | 5 | 135.0 s | 123855 | 340657 |

Reproduction (from a clean checkout):

```bash
uv run --with pillow --no-project python media/make_frames.py
# A
python - <<'EOF'
# via MCP moviola_slideshow_from_images or equivalent ffmpeg concat:
# preset torch, height 480, fps 5, seconds_per_image 5, 26 frames -> 130 s+
EOF
```

Probe: `moviola_probe_media` (ffprobe) reports width/height/fps/duration/codec.
All numbers visible in frames come from frozen artifacts:
`eval/results/versus-final-off.json`, `eval/results/graded.json`,
`eval/results/calibration-320k-to-128k.md`, dummy3/dummy4 and dummy5 surveys (D feeds off dummy5).
