#!/usr/bin/env python3
"""Feed the stationary fake fix and report EKF_STATUS_REPORT flags and STATUSTEXT for up to SECS."""
import sys
import threading
import time

from pymavlink import mavutil

MAV = mavutil.mavlink
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 90
m = mavutil.mavlink_connection("tcpin:0.0.0.0:5771", source_system=255, source_component=190)
hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=30)
m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
run = True


def gps():
    while run:
        now = time.time()
        gps_s = now - 315964800 + 18
        week = int(gps_s // 604800)
        m.mav.gps_input_send(int(now * 1e6), 0, 0, int((gps_s - week * 604800) * 1000), week, 3,
                             -353632621, 1491652374, 584.0, 0.8, 1.2, 0.0, 0.0, 0.0, 0.3, 1.0, 1.5, 16)
        time.sleep(0.1)


threading.Thread(target=gps, daemon=True).start()
m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                        MAV.MAVLINK_MSG_ID_EKF_STATUS_REPORT, 1000000, 0, 0, 0, 0, 0)
t0, last = time.time(), None
while time.time() - t0 < secs:
    msg = m.recv_match(type=["EKF_STATUS_REPORT", "STATUSTEXT"], blocking=True, timeout=1)
    if msg is None:
        continue
    if msg.get_type() == "STATUSTEXT":
        print(f"{time.time() - t0:5.1f} text: {msg.text}", flush=True)
    elif msg.flags != last:
        last = msg.flags
        print(f"{time.time() - t0:5.1f} EKF flags {msg.flags:#06x} horiz_abs {bool(msg.flags & MAV.EKF_POS_HORIZ_ABS)} "
              f"compass_var {msg.compass_variance:.2f}", flush=True)
        if msg.flags & MAV.EKF_POS_HORIZ_ABS:
            break
run = False
