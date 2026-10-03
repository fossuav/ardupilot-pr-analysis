# Explainer video and interactive page (2026-10-03)

A 127 s narrated explainer (uploaded to YouTube) and an interactive page
(private claude.ai artifact: https://claude.ai/artifact/9uDpwTP21r4GbRvDR8i4qF).
Neither is committed: the video is rebuilt from the sources here, and the
page inlines real-flight data, which this repo does not hold.

The master-vs-PR outcomes follow the arming code at `9bb371d054`. Two points
the PR body states loosely and these state exactly: with home locked neither
build resets (`AP_Arming_Copter::arm()`), and the vertical-speed refusal is
at `LAND_DETECTOR_VEL_Z_MAX`, 1 m/s; the 1.5 m/s in the PR table is the test's
lift speed.

Data:

- `data/log12_baro.csv` - real MatekH743 5-inch bench session, log12 (never
  armed, 206 s, -1.17 m, 41.8 -> 61.8 C). Real flight data: gitignored.
- `data/sitl_*.csv` - from `../data/arm-only/barodrift_arm.BIN` (Plot A).

Rebuild:

    ./make_data.sh /path/to/log12.bin   # CSVs, via log-analyze's log_extract.py
    ./make_page.py                       # explainer.html
    ./make_video.sh [voice]              # script.md -> audio -> scenes -> mp4

`make_video.sh` needs a venv with `manim` and `kokoro` (default
`~/venv-video`, override with `VENV`). The narration is `script.md`; scene
lengths follow the generated audio, so editing a paragraph re-times its
scene. The voice used was `bm_george`.
