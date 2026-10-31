#!/usr/bin/env python3
"""Per disarm, what #34942's rest check saw on Replay (instrument_stale.py records).

For each disarm in the source log and each replayed core: the age of the last
measured velD fusion at the disarm and whether the AGL KF was what fused it
(inFlight just before), how long measuredVertVelAgrees() stayed true after the
disarm, each rest check before the next arm (time after the disarm, agreement,
|VD|, reset or not), and VD at the next arm.
usage: stale_probe.py <source log> <replay output BIN>
"""
import sys
from pymavlink import mavutil

src, rep = sys.argv[1], sys.argv[2]
m = mavutil.mavlink_connection(src, robust_parsing=True)
arms = []
while True:
    msg = m.recv_match(type=['ARM'])
    if msg is None:
        break
    arms.append((msg.TimeUS * 1e-6, msg.ArmState))

m = mavutil.mavlink_connection(rep, robust_parsing=True)
rec = {}
while True:
    msg = m.recv_match(type=['XKFM'])
    if msg is None:
        break
    if msg.C < 150:
        continue
    cnt = int(round(msg.ADR))
    rec.setdefault(msg.C - 150, []).append(
        (msg.TimeUS * 1e-6, msg.OGNM, msg.GLR, msg.ALR, msg.GDR, cnt % 1000, cnt // 1000))

for i, (t, s) in enumerate(arms):
    if s != 0:
        continue
    nxt = next((a for a, st in arms[i + 1:] if st != 0), None)
    end = nxt if nxt is not None else t + 8.0
    print("disarm %.2f, next arm %s" % (t, ("%.2f (+%.2f s)" % (nxt, nxt - t)) if nxt else "none"))
    for core, rows in sorted(rec.items()):
        before = [r for r in rows if r[0] <= t]
        after = [r for r in rows if t < r[0] <= end]
        if not before or not after:
            continue
        b = before[-1]
        agree_end = None
        for r in after:
            if not (r[1] & 1):
                agree_end = r[0] - t
                break
        line = "  core %d: at disarm velD fused %.2f s ago, innov %.2f, inFlight %d, agrees %d; agreement held to +%s" % (
            core, b[2], b[3], (b[1] >> 6) & 1, b[1] & 1, ("%.2f s" % agree_end) if agree_end is not None else "end")
        print(line)
        prev = b
        for r in after:
            if r[6] > prev[6]:
                print("    rest check at +%.2f s: agrees %d (nav %d, body %d), VD %.2f, velD fused %.2f s ago, %s" % (
                    r[0] - t, r[1] & 1, (r[1] >> 1) & 1, (r[1] >> 2) & 1, prev[4], r[2],
                    "RESET" if r[5] > prev[5] else "no reset"))
            prev = r
        if nxt is not None:
            print("    at the arm: VD %.2f, still %d, hgt error %d" % (after[-1][4], (after[-1][1] >> 4) & 1, (after[-1][1] >> 7) & 1))
