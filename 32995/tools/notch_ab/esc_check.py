#!/usr/bin/env python3
"""Is anything real answering on the DShot outputs? ESC telemetry by motor, armed and disarmed."""
import statistics as st
import sys

from pymavlink import DFReader

for path in sys.argv[1:]:
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    esc, arm, rcou, t0 = [], [], [], None
    while True:
        m = log.recv_match(type=["ESC", "ARM", "RCOU"])
        if m is None:
            break
        t = m.TimeUS * 1e-6
        t0 = t if t0 is None else t0
        k = m.get_type()
        if k == "ESC":
            esc.append((t - t0, int(m.Instance), m.RPM, m.Err, m.Volt, m.Curr, m.Temp))
        elif k == "ARM":
            arm.append((t - t0, int(m.ArmState)))
        else:
            rcou.append((t - t0, m.C1, m.C2, m.C3, m.C4))
    disarm = next((t for t, s in arm if not s), None)
    print(f"{path}: {len(esc)} ESC rows, disarm at {disarm}")
    for inst in sorted({e[1] for e in esc}):
        for label, sel in (("armed", lambda t: disarm is None or t <= disarm), ("disarmed", lambda t: disarm is not None and t > disarm + 1)):
            rows = [e for e in esc if e[1] == inst and sel(e[0])]
            if not rows:
                continue
            rpm = [e[2] for e in rows]
            nz = [r for r in rpm if r > 0]
            print(f"  ESC{inst} {label:8s} rows {len(rows):6d}, non-zero RPM {100 * len(nz) / len(rpm):5.1f}%, "
                  f"RPM median {st.median(rpm):7.1f} p95 {sorted(rpm)[int(len(rpm) * 0.95)]:7.1f} max {max(rpm):7.1f}, "
                  f"Err mean {st.mean(e[3] for e in rows):6.2f}, V max {max(e[4] for e in rows):.1f}, "
                  f"A max {max(e[5] for e in rows):.1f}, temp max {max(e[6] for e in rows)}")
    armed_out = [r for r in rcou if disarm is None or r[0] <= disarm]
    if armed_out:
        print("  RCOU while armed, C1-C4 median:", [st.median(r[i] for r in armed_out) for i in range(1, 5)],
              "max:", [max(r[i] for r in armed_out) for i in range(1, 5)])
