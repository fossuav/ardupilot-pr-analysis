#!/usr/bin/env python3
"""Generate one narration WAV per scene from script.md with Kokoro TTS.

Writes audio/sN.wav and audio/durations.json, which scenes.py reads so each
scene runs exactly as long as its narration.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

HERE = Path(__file__).parent
VOICE = sys.argv[1] if len(sys.argv) > 1 else "bm_george"
RATE = 24000

text = (HERE / "script.md").read_text()
scenes = dict(re.findall(r"^## (s\d+)\n(.+?)(?=\n## |\Z)", text, re.S | re.M))

out = HERE / "audio"
out.mkdir(exist_ok=True)
pipe = KPipeline(lang_code=VOICE[0])
durations = {}
for name, para in scenes.items():
    chunks = [a for _, _, a in pipe(para.strip(), voice=VOICE, speed=1.0)]
    audio = np.concatenate(chunks)
    sf.write(out / f"{name}.wav", audio, RATE)
    durations[name] = round(len(audio) / RATE, 2)
    print(name, durations[name])
(out / "durations.json").write_text(json.dumps(durations, indent=1))
