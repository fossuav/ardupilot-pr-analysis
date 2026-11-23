#!/usr/bin/env python3
"""Where each flight log's lowest log-buffer free space falls: in flight, armed, or outside."""
import os
import sys

from pymavlink import DFReader

SIZE = {"00000013.BIN": 64 * 1024}
for path in sys.argv[1:]:
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    t0, dsf, ev, arm = None, [], [], []
    while True:
        m = log.recv_match(type=["DSF", "EV", "ARM"])
        if m is None:
            break
        t0 = m.TimeUS * 1e-6 if t0 is None else t0
        t = m.TimeUS * 1e-6 - t0
        k = m.get_type()
        if k == "DSF":
            dsf.append((t, m.FMn))
        elif k == "EV":
            ev.append((t, int(m.Id)))
        else:
            arm.append((t, int(m.ArmState)))
    flying, cur = [], None
    for t, i in ev:
        if i == 28 and cur is None:
            cur = t
        elif i == 18 and cur is not None:
            if t - cur > 5:
                flying.append((cur, t))
            cur = None
    armed, cur = [], None
    for t, s in arm:
        if s and cur is None:
            cur = t
        elif not s and cur is not None:
            armed.append((cur, t))
            cur = None
    inw = lambda t, w: any(a <= t <= b for a, b in w)
    name = os.path.basename(path)
    size = SIZE.get(name, 80 * 1024)
    fl = min(f for t, f in dsf if inw(t, flying))
    ar = min(f for t, f in dsf if inw(t, armed))
    tl, lo = min(dsf, key=lambda d: d[1])
    where = "in flight" if inw(tl, flying) else "armed on the ground" if inw(tl, armed) else "disarmed"
    print(f"{name}: lowest free in flight {fl} B (peak use {(size - fl) / 1024:.1f} KB); armed {ar} B; "
          f"whole log {lo} B at {tl:.1f} s, {where} (peak use {(size - lo) / 1024:.1f} KB of {size // 1024})")
