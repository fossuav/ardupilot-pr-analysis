#!/usr/bin/env python3
"""When did the A/B runs drop log data or stretch a rate-loop cycle, relative to arming and disarming?"""
import glob
import os
import re
import sys

from pymavlink import DFReader

BASE = sys.argv[1]
for d in sorted(glob.glob(f"{BASE}/run*"), key=lambda x: int(re.search(r"run(\d+)", x).group(1))):
    log = DFReader.DFReader_binary(f"{d}/bench.BIN", zero_time_base=False)
    t0, dsf, rt, arm, pm = None, [], [], [], []
    while True:
        m = log.recv_match(type=["DSF", "RTDT", "ARM", "PM"])
        if m is None:
            break
        t = m.TimeUS * 1e-6
        t0 = t if t0 is None else t0
        k = m.get_type()
        if k == "DSF":
            dsf.append((t - t0, m.Dp, m.FMn))
        elif k == "RTDT":
            rt.append((t - t0, m.dtMax))
        elif k == "ARM":
            arm.append((t - t0, int(m.ArmState)))
        else:
            pm.append((t - t0, m.NLon, m.MaxT))
    disarm = next((t for t, s in arm if not s), None)
    rises = [(round(b[0], 1), b[1] - a[1]) for a, b in zip(dsf, dsf[1:]) if b[1] > a[1]]
    late = [(round(t, 1), round(x * 1e3, 2)) for t, x in rt if x > 1e-3]
    armed_late = [v for v in late if disarm is None or v[0] <= disarm]
    long_loops = [(round(t, 1), n, round(mx * 1e-3, 2)) for t, n, mx in pm if n]
    print(f"{os.path.basename(d)}: log {rt[-1][0]:.0f} s, disarm {disarm:.1f}; log drops at (s, msgs) {rises[:5]}; "
          f"lowest buffer free {min(x[2] for x in dsf)} B")
    print(f"    rate gaps over 1 ms: {late[:6]}; of which while armed {len(armed_late)}; long loops {long_loops}")
