#!/usr/bin/env python3
"""MAVFTP over the bench bridge.

  ftp.py ls REMOTE_DIR
  ftp.py get REMOTE LOCAL
"""
import logging
import sys
import time

from pymavlink import mavutil
from pymavlink.mavftp import MAVFTP

MAV = mavutil.mavlink
m = mavutil.mavlink_connection("tcpin:0.0.0.0:5770", source_system=255, source_component=190)
t0 = time.time()
while time.time() - t0 < 30:
    hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
    if hb and hb.type != MAV.MAV_TYPE_GCS and hb.autopilot == MAV.MAV_AUTOPILOT_ARDUPILOTMEGA:
        m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
        break
else:
    sys.exit("no heartbeat")
logging.basicConfig(level=logging.WARNING)
f = MAVFTP(m, m.target_system, m.target_component)
op = sys.argv[1]
if op == "ls":
    f.cmd_list([sys.argv[2]])
    f.process_ftp_reply("ListDirectory", timeout=20)
elif op == "get":
    t0 = time.time()
    f.cmd_get([sys.argv[2], sys.argv[3]])
    r = f.process_ftp_reply("OpenFileRO", timeout=600)
    print(f"get done in {time.time() - t0:.1f} s, error {r.error_code}")
else:
    sys.exit(__doc__)
