#!/usr/bin/env python3
"""Dump selected messages in a time window (seconds of log time) in order."""
import sys

from pymavlink import mavutil

path, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
types = sys.argv[4].split(',') if len(sys.argv) > 4 else [
    'SIM2', 'XKF1', 'XKF5', 'PRFL', 'RFND', 'ATT', 'PSCN', 'PSCE', 'EV', 'MODE', 'OF']
fields = {
    'SIM2': ['PN', 'PE', 'PD', 'VN', 'VE'],
    'XKF1': ['C', 'PN', 'PE', 'VN', 'VE'],
    'XKF5': ['C', 'FIX', 'FIY', 'HAGL', 'RI'],
    'PRFL': ['C', 'F', 'FIX', 'FIY', 'FTR', 'PN', 'PE', 'HAGL', 'RNG'],
    'RFND': ['Dist', 'Stat'],
    'ATT': ['DesRoll', 'DesPitch', 'Roll', 'Pitch'],
    'PSCN': ['TPN', 'PN', 'TAN'],
    'PSCE': ['TPE', 'PE', 'TAE'],
    'EV': ['Id'],
    'MODE': ['Mode'],
    'OF': ['Qual', 'flowX', 'flowY', 'bodyX', 'bodyY'],
}
mlog = mavutil.mavlink_connection(path)
while True:
    m = mlog.recv_match(type=types)
    if m is None:
        break
    t = m.TimeUS * 1e-6
    if t < t0:
        continue
    if t > t1:
        break
    tp = m.get_type()
    if tp in ('XKF1', 'XKF5', 'PRFL') and getattr(m, 'C', 0) != 0:
        continue
    vals = []
    for f in fields.get(tp, []):
        v = getattr(m, f, None)
        vals.append("%s=%s" % (f, ("%.3f" % v) if isinstance(v, float) else v))
    print("%8.3f %-5s %s" % (t, tp, " ".join(vals)))
