#!/usr/bin/env python3
"""Loop timing and logging health of a bench log, split by flight mode.

Usage: logana.py LOG
PM rows (loop rate, long loops, max loop time, load, log drops), the period between ATT
records (one per main loop with ATTITUDE_FAST), DSF, MODE and MSG.
"""
import collections
import sys

from pymavlink import DFReader

log = DFReader.DFReader_binary(sys.argv[1], zero_time_base=True)
modes = []
pm = []
att_t = []
dsf = []
msgs = []
parm = {}
while True:
    m = log.recv_match(type=["PM", "ATT", "DSF", "MODE", "MSG", "PARM", "EV", "ERR"])
    if m is None:
        break
    t = m.get_type()
    ts = m.TimeUS * 1e-6
    if t == "ATT":
        att_t.append(m.TimeUS)
    elif t == "PM":
        pm.append((ts, m.to_dict()))
    elif t == "MODE":
        modes.append((ts, m.Mode))
    elif t == "DSF":
        dsf.append((ts, m.to_dict()))
    elif t == "PARM":
        parm[m.Name] = m.Value
    else:
        msgs.append((ts, t, {k: v for k, v in m.to_dict().items() if k not in ("mavpackettype", "TimeUS")}))

print("SCHED_LOOP_RATE", parm.get("SCHED_LOOP_RATE"), " LOG_BITMASK", parm.get("LOG_BITMASK"))
print("modes:", [(round(a, 1), b) for a, b in modes])
for ts, t, d in msgs:
    print(f"  {ts:8.2f} {t} {d}")


def mode_at(ts):
    cur = None
    for a, b in modes:
        if a <= ts:
            cur = b
    return cur


if pm:
    keys = [k for k in pm[0][1] if k not in ("mavpackettype", "TimeUS")]
    print("PM fields:", keys)
    for ts, d in pm:
        print(f"  {ts:8.2f} mode {mode_at(ts)} " + " ".join(f"{k}={d[k]}" for k in keys))

by_mode = collections.defaultdict(list)
for a, b in zip(att_t, att_t[1:]):
    by_mode[mode_at(a * 1e-6)].append(b - a)
for mode, dts in by_mode.items():
    dts.sort()
    n = len(dts)
    mean = sum(dts) / n
    hist = collections.Counter(min(d // 500 * 500, 20000) for d in dts)
    print(f"ATT period, mode {mode}: n {n}, mean {mean:.0f} us ({1e6 / mean:.1f} Hz), "
          f"p50 {dts[n // 2]}, p99 {dts[int(n * 0.99)]}, p99.9 {dts[int(n * 0.999)]}, max {dts[-1]}")
    print("    histogram (us bucket: count):", dict(sorted(hist.items())))
if dsf:
    first, last = dsf[0][1], dsf[-1][1]
    print("DSF first", {k: v for k, v in first.items() if k != "mavpackettype"})
    print("DSF last ", {k: v for k, v in last.items() if k != "mavpackettype"})
