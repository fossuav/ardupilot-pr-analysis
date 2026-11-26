#!/usr/bin/env python3
"""Fetch every parameter over MAVLink (bridge on 127.0.0.1:5771) and write OUT.parm and OUT.json.

Usage: param_dump.py OUT
Requests the list, then re-requests any index still missing until PARAM_COUNT are held.
"""
import json
import sys
import time

from pymavlink import mavutil

MAV = mavutil.mavlink
out = sys.argv[1]
m = mavutil.mavlink_connection("tcpin:0.0.0.0:5771", source_system=255, source_component=190)
t0 = time.time()
while time.time() - t0 < 30:
    hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
    if hb and hb.type != MAV.MAV_TYPE_GCS and hb.autopilot == MAV.MAV_AUTOPILOT_ARDUPILOTMEGA:
        break
else:
    sys.exit("no heartbeat")
m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
params, count = {}, None
m.mav.param_request_list_send(m.target_system, m.target_component)
last = time.time()
for attempt in range(20):
    while time.time() - last < 2.0:
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if p is None:
            continue
        last = time.time()
        count = p.param_count
        if p.param_index < 65535:
            params[p.param_index] = (p.param_id, p.param_value, p.param_type)
    if count is not None and len(params) >= count:
        break
    missing = [i for i in range(count or 0) if i not in params]
    print(f"pass {attempt}: {len(params)}/{count}, re-requesting {len(missing)}")
    for i in missing[:100]:
        m.mav.param_request_read_send(m.target_system, m.target_component, b"", i)
    last = time.time()
if count is None or len(params) != count:
    sys.exit(f"incomplete: {len(params)} of {count}")
rows = sorted(params.values())
with open(out + ".parm", "w") as f:
    for name, value, ptype in rows:
        f.write(f"{name} {int(value) if ptype <= 6 else repr(value)}\n")
json.dump({"count": count, "params": {n: {"value": v, "type": t} for n, v, t in rows}}, open(out + ".json", "w"), indent=0)
print(f"{count} parameters -> {out}.parm")
