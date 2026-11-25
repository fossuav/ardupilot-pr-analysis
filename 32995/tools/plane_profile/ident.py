#!/usr/bin/env python3
"""Identify the board on the bridge: heartbeat, version, all parameters, a few seconds of status.

Usage: ident.py OUTDIR
Writes OUTDIR/params.txt (NAME VALUE, sorted) and prints a summary. Read-only: sets nothing
but message intervals.
"""
import os
import sys
import time

from pymavlink import mavutil

MAV = mavutil.mavlink
out = sys.argv[1]
os.makedirs(out, exist_ok=True)

m = mavutil.mavlink_connection("tcpin:0.0.0.0:5770", source_system=255, source_component=190)
t0 = time.time()
hb = None
while time.time() - t0 < 30:
    hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
    if hb and hb.type != MAV.MAV_TYPE_GCS and hb.autopilot == MAV.MAV_AUTOPILOT_ARDUPILOTMEGA:
        m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
        break
else:
    sys.exit("no heartbeat")
print(f"HEARTBEAT type={hb.type} custom_mode={hb.custom_mode} armed={bool(hb.base_mode & 128)} "
      f"sys={m.target_system} comp={m.target_component}")

m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_REQUEST_MESSAGE, 0,
                        MAV.MAVLINK_MSG_ID_AUTOPILOT_VERSION, 0, 0, 0, 0, 0, 0)
av = m.recv_match(type="AUTOPILOT_VERSION", blocking=True, timeout=5)
if av:
    v = av.flight_sw_version
    githash = bytes(av.flight_custom_version).rstrip(b"\0").decode(errors="replace")
    print(f"version {v >> 24}.{(v >> 16) & 255}.{(v >> 8) & 255} type {v & 255} git {githash} "
          f"board_version {av.board_version:#x}")

params = {}
m.mav.param_request_list_send(m.target_system, m.target_component)
total, last = None, time.time()
texts = []
while time.time() - last < 4:
    p = m.recv_match(type=["PARAM_VALUE", "STATUSTEXT"], blocking=True, timeout=1)
    if p is None:
        continue
    if p.get_type() == "STATUSTEXT":
        texts.append(p.text)
        continue
    params[p.param_id] = p.param_value
    total = p.param_count
    last = time.time()
    if total and len(params) >= total:
        break
print(f"params {len(params)} of {total}")
with open(os.path.join(out, "params.txt"), "w") as fh:
    for k in sorted(params):
        fh.write(f"{k} {params[k]:.9g}\n")

for msg_id in (MAV.MAVLINK_MSG_ID_SYS_STATUS, MAV.MAVLINK_MSG_ID_MEMINFO):
    m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                            msg_id, 500000, 0, 0, 0, 0, 0)
loads, free = [], []
t0 = time.time()
while time.time() - t0 < 8:
    msg = m.recv_match(type=["SYS_STATUS", "MEMINFO", "STATUSTEXT"], blocking=True, timeout=1)
    if msg is None:
        continue
    if msg.get_type() == "SYS_STATUS":
        loads.append(msg.load / 10.0)
    elif msg.get_type() == "MEMINFO":
        free.append(getattr(msg, "freemem32", 0) or msg.freemem)
    else:
        texts.append(msg.text)
print("SYS_STATUS load %", loads)
print("MEMINFO free", free[:4])
for t in texts:
    print("  text:", t)
