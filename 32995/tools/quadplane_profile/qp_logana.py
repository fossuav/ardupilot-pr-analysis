#!/usr/bin/env python3
"""Loop timing of a QuadPlane bench log by flight mode: PM rows and the rate thread's RTDT.

Usage: qp_logana.py LOG
"""
import collections
import sys

from pymavlink import DFReader

log = DFReader.DFReader_binary(sys.argv[1], zero_time_base=True)
modes, pm, rtdt, parm, msgs = [], [], [], {}, []
while True:
    m = log.recv_match(type=["PM", "RTDT", "MODE", "PARM", "MSG", "DSF"])
    if m is None:
        break
    t = m.get_type()
    ts = m.TimeUS * 1e-6
    if t == "PM":
        pm.append((ts, m))
    elif t == "RTDT":
        rtdt.append((ts, m))
    elif t == "MODE":
        modes.append((ts, m.Mode))
    elif t == "PARM":
        parm[m.Name] = m.Value
    elif t == "MSG" and ("Rate" in m.Message or "Q_" in m.Message or "thread" in m.Message):
        msgs.append((round(ts, 1), m.Message))
    elif t == "DSF":
        parm["_dsf_dp"] = m.Dp


def mode_at(ts):
    cur = None
    for a, b in modes:
        if a <= ts:
            cur = b
    return cur


print({k: parm.get(k) for k in ("SCHED_LOOP_RATE", "Q_FSTRATE_ENABLE", "Q_FSTRATE_DIV", "INS_GYRO_RATE", "_dsf_dp")})
print("modes:", [(round(a, 1), b) for a, b in modes])
print("rate texts:", msgs)
by = collections.defaultdict(list)
for ts, m in pm:
    by[mode_at(ts)].append(m)
for mode, rows in by.items():
    # drop the first row in each mode, which holds the change
    rows = rows[1:] if len(rows) > 2 else rows
    print(f"PM mode {mode}: rows {len(rows)}, long loops {sum(r.NLon for r in rows)}, "
          f"MaxT {min(r.MaxT for r in rows)}-{max(r.MaxT for r in rows)} us, "
          f"load {min(r.Load for r in rows) / 10:.1f}-{max(r.Load for r in rows) / 10:.1f}%, "
          f"Ex>0 rows {sum(1 for r in rows if getattr(r, 'Ex', 0) > 0)}")
byr = collections.defaultdict(list)
for ts, m in rtdt:
    byr[mode_at(ts)].append(m)
for mode, rows in byr.items():
    rows = rows[2:] if len(rows) > 4 else rows
    dtav = sum(r.dtAvg for r in rows) / len(rows)
    print(f"RTDT mode {mode}: n {len(rows)}, sample dt {dtav * 1e6:.0f} us ({1 / dtav:.0f} Hz), "
          f"dtMax max {max(r.dtMax for r in rows) * 1e6:.0f} us, "
          f"dtMax p50 {sorted(r.dtMax for r in rows)[len(rows) // 2] * 1e6:.0f} us, "
          f"dtMin min {min(r.dtMin for r in rows) * 1e6:.0f} us")
