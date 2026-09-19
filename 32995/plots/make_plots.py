#!/usr/bin/env python3
"""Regenerate the OSD video plots from ../data/osd-video-2026-09-17.csv.

The CSV is per 10 s of each capture: usable fields, the text blocks the OSD
had on screen over those fields, how many of them were missing, and the
frame-to-frame motion (the flight/ground proxy).  It is produced by
../tools/osd_video_blocks.py from the tester's videos, which are not in this
repo.
"""
import csv
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, '..', 'data', 'osd-video-2026-09-17.csv')
LABEL = {'CRSF': ('CRSF', 'tab:red'), 'MAVLINK2': ('RC over MAVLink', 'tab:blue')}

rows = list(csv.DictReader(open(CSV)))
fig, ax = plt.subplots(figsize=(8, 4))
for sess, (name, col) in LABEL.items():
    r = [x for x in rows if x['session'] == sess]
    ax.plot([int(x['t_start_s']) + 5 for x in r], [float(x['missing_pct']) for x in r],
            'o-', color=col, label=name)
ax.axvspan(0, 35, color='0.88', zorder=0)
ax.text(17, 2, 'MAVLink session:\nstill on the ground', ha='center', fontsize=8, color='0.3')
ax.set_xlabel('time into the recording (s)')
ax.set_ylabel('% of the OSD text blocks missing, per field')
ax.set_title('RPI_UAVFC analog OSD, firmware 4f982aea88, 2026-09-17')
ax.set_ylim(bottom=0)
ax.legend(fontsize=8)
ax.grid(alpha=0.3)
fig.tight_layout()
out = os.path.join(HERE, 'osd-video-2026-09-17.png')
fig.savefig(out, dpi=110)
print('wrote', out)
