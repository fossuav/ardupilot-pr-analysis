#!/usr/bin/env python3
"""RTDT summary per armed/disarmed span: rtdt.py LOG.BIN"""
import sys
from pymavlink import DFReader

log = DFReader.DFReader_binary(sys.argv[1], zero_time_base=True)
armed = None
rows = {True: [], False: [], None: []}
while True:
    m = log.recv_match(type=["RTDT", "ARM"])
    if m is None:
        break
    if m.get_type() == "ARM":
        armed = bool(m.ArmState)
        print(f"ARM at {m.TimeUS/1e6:.2f} s: {armed}")
        continue
    rows[armed].append(m)
for k, v in rows.items():
    if not v:
        continue
    span = (v[-1].TimeUS - v[0].TimeUS) / 1e6
    def q(vals, p):
        s = sorted(vals)
        return s[min(len(s) - 1, int(p * len(s)))] * 1e6
    print(f"armed={k}: {len(v)} RTDT over {span:.1f} s; dt median {q([x.dt for x in v], .5):.0f} us; "
          f"dtAvg median {q([x.dtAvg for x in v], .5):.0f}; dtMax median {q([x.dtMax for x in v], .5):.0f} "
          f"max {q([x.dtMax for x in v], 1):.0f}; dtMin median {q([x.dtMin for x in v], .5):.0f}")
