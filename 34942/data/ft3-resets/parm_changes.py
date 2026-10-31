#!/usr/bin/env python3
"""List parameter values that change after boot (PARM messages after the first
set of each name), with raw TimeUS seconds.
usage: parm_changes.py <log> [after s]
"""
import sys
from pymavlink import mavutil

after = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
m = mavutil.mavlink_connection(sys.argv[1], robust_parsing=True)
seen = {}
while True:
    msg = m.recv_match(type=['PARM'])
    if msg is None:
        break
    t = msg.TimeUS * 1e-6
    old = seen.get(msg.Name)
    if old is not None and old != msg.Value and t > after:
        print("%10.3f  %-16s %g -> %g" % (t, msg.Name, old, msg.Value))
    seen[msg.Name] = msg.Value
