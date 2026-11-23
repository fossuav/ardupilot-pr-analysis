#!/usr/bin/env python3
"""Check a pilot run reached the notch path: injected RPM, centres above 400 Hz, outputs at idle."""
import statistics as st
import sys

from pymavlink import DFReader

log = DFReader.DFReader_binary(sys.argv[1], zero_time_base=False)
esc, rcou, msgs, arm, t0 = [], [], [], [], None
while True:
    m = log.recv_match(type=["ESC", "RCOU", "MSG", "ARM"])
    if m is None:
        break
    t = m.TimeUS * 1e-6
    t0 = t if t0 is None else t0
    k = m.get_type()
    if k == "ESC":
        esc.append((t - t0, int(m.Instance), m.RPM))
    elif k == "RCOU":
        rcou.append((t - t0, m.C1, m.C2, m.C3, m.C4))
    elif k == "ARM":
        arm.append((t - t0, int(m.ArmState)))
    elif any(w in m.Message for w in ("notch", "Lua", "Takeoff", "rror", "Internal")):
        msgs.append(m.Message)
end = next((t for t, s in arm if not s), esc[-1][0])
print("armed until", round(end, 1), "s; messages:", sorted(set(msgs))[:8])
for inst in sorted({e[1] for e in esc}):
    hz = [e[2] / 60 for e in esc if e[1] == inst and 3 < e[0] <= end]
    print(f" ESC{inst}: {len(hz)} rows, Hz min {min(hz):.0f} median {st.median(hz):.0f} max {max(hz):.0f}, zero rows {sum(h == 0 for h in hz)}")
hz = [e[2] / 60 for e in esc if 3 < e[0] <= end]
print(f" harmonic centres above 400 Hz: {100 * sum(sum(f * h > 400 for h in (1, 2, 3, 4)) for f in hz) / (4 * len(hz)):.0f}% "
      "(log 15: 64%)")
print(" RCOU C1-C4 while armed, max:", [max(r[i] for r in rcou if r[0] <= end) for i in range(1, 5)])
