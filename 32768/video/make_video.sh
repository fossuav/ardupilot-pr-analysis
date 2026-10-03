#!/bin/sh
# Narrate, render and join the explainer. Needs data/ (make_data.sh) and a
# venv with manim and kokoro (default ~/venv-video). Voice is optional.
set -e
cd "$(dirname "$0")"
V=${VENV:-$HOME/venv-video}
$V/bin/python make_audio.py ${1:-bm_george}
$V/bin/manim -qh scenes.py S1 S2 S3 S4 S5 S6 S7
D=media/videos/scenes/1080p60
for s in 1 2 3 4 5 6 7; do echo "file '$D/S$s.mp4'"; done > concat.txt
ffmpeg -v error -y -f concat -safe 0 -i concat.txt -c:v libx264 -crf 18 -preset slow \
    -pix_fmt yuv420p -af loudnorm=I=-14:TP=-1.5:LRA=11 -c:a aac -b:a 192k -ar 48000 \
    -movflags +faststart pr32768-baro-drift-at-arm.mp4
