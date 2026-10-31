#!/usr/bin/env python3
"""Print MSG and ARM events of a log with raw TimeUS seconds.
usage: events.py <log> [regex]
"""
import re
import sys
from pymavlink import mavutil

pat = re.compile(sys.argv[2], re.I) if len(sys.argv) > 2 else None
m = mavutil.mavlink_connection(sys.argv[1], robust_parsing=True)
while True:
    msg = m.recv_match(type=['MSG', 'ARM'])
    if msg is None:
        break
    t = msg.TimeUS * 1e-6
    if msg.get_type() == 'ARM':
        print("%10.3f  ARM state %d method %d" % (t, msg.ArmState, msg.Method))
    elif pat is None or pat.search(msg.Message):
        print("%10.3f  MSG %s  [TimeUS %d]" % (t, msg.Message, msg.TimeUS))
