#!/usr/bin/env python3
"""Bench mission for profiling AUTO, through the bridge on 127.0.0.1:5770.

  mission.py upload LAT LON     home plus two waypoints 400-600 m away at 100 m, no takeoff item
  mission.py clear              MISSION_CLEAR_ALL (refused while armed and running)
  mission.py count              the number of items the board holds
"""
import math
import sys
import time

from pymavlink import mavutil

MAV = mavutil.mavlink


def connect():
    m = mavutil.mavlink_connection("tcpin:0.0.0.0:5770", source_system=255, source_component=190)
    t0 = time.time()
    while time.time() - t0 < 30:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb and hb.type != MAV.MAV_TYPE_GCS and hb.autopilot == MAV.MAV_AUTOPILOT_ARDUPILOTMEGA:
            m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
            return m
    sys.exit("no heartbeat")


def offset(lat, lon, north_m, east_m):
    return lat + north_m / 111319.5, lon + east_m / (111319.5 * math.cos(math.radians(lat)))


def item(m, seq, lat, lon, alt, frame):
    return m.mav.mission_item_int_encode(m.target_system, m.target_component, seq, frame,
                                         MAV.MAV_CMD_NAV_WAYPOINT, 0, 1, 0, 0, 0, 0,
                                         int(lat * 1e7), int(lon * 1e7), alt, MAV.MAV_MISSION_TYPE_MISSION)


def upload(m, lat, lon):
    items = [item(m, 0, lat, lon, 0, MAV.MAV_FRAME_GLOBAL)]
    for i, (n, e) in enumerate(((500, 300), (-200, 550)), start=1):
        la, lo = offset(lat, lon, n, e)
        items.append(item(m, i, la, lo, 100, MAV.MAV_FRAME_GLOBAL_RELATIVE_ALT))
    m.mav.mission_count_send(m.target_system, m.target_component, len(items), MAV.MAV_MISSION_TYPE_MISSION)
    t_end = time.time() + 20
    while time.time() < t_end:
        msg = m.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"], blocking=True, timeout=1)
        if msg is None:
            continue
        if msg.get_type() == "MISSION_ACK":
            print("upload ack", msg.type, "(0 = accepted)")
            return msg.type == 0
        m.mav.send(items[msg.seq])
    print("upload timed out")
    return False


def count(m):
    m.mav.mission_request_list_send(m.target_system, m.target_component, MAV.MAV_MISSION_TYPE_MISSION)
    msg = m.recv_match(type="MISSION_COUNT", blocking=True, timeout=5)
    return msg.count if msg else None


def main():
    m = connect()
    op = sys.argv[1]
    if op == "upload":
        ok = upload(m, float(sys.argv[2]), float(sys.argv[3]))
        print("items now", count(m))
        sys.exit(0 if ok else 1)
    elif op == "clear":
        m.mav.mission_clear_all_send(m.target_system, m.target_component, MAV.MAV_MISSION_TYPE_MISSION)
        a = m.recv_match(type="MISSION_ACK", blocking=True, timeout=5)
        print("clear ack", a.type if a else None, "items now", count(m))
    elif op == "count":
        print("items", count(m))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
