#!/usr/bin/env python3
"""Set parameters on the bench board through bridge.py (tcpin 5770), read each back, optionally reboot.

Usage: qp_params.py [--reboot] NAME=VALUE ...
       qp_params.py --get NAME ...
Refuses to reboot an armed board. After a reboot, waits for the heartbeat and prints the
version and boot STATUSTEXTs.
"""
import sys
import time

from pymavlink import mavutil

MAV = mavutil.mavlink
args = sys.argv[1:]
reboot = "--reboot" in args
get_only = "--get" in args
args = [a for a in args if not a.startswith("--")]

m = mavutil.mavlink_connection("tcpin:0.0.0.0:5770", source_system=255, source_component=190)


def wait_hb(timeout):
    t_end = time.time() + timeout
    while time.time() < t_end:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb and hb.type != MAV.MAV_TYPE_GCS and hb.autopilot == MAV.MAV_AUTOPILOT_ARDUPILOTMEGA:
            m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
            return hb
    return None


hb = wait_hb(30)
if hb is None:
    sys.exit("no heartbeat")


def get(name):
    for _ in range(5):
        m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
        t_end = time.time() + 2
        while time.time() < t_end:
            p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
            if p and p.param_id == name:
                return p.param_value
    return None


if get_only:
    for n in args:
        print(n, get(n))
    sys.exit(0)

bad = False
for a in args:
    name, val = a.split("=")
    val = float(val)
    ok = False
    for _ in range(5):
        m.mav.param_set_send(m.target_system, m.target_component, name.encode(), val,
                             MAV.MAV_PARAM_TYPE_REAL32)
        t_end = time.time() + 2
        while time.time() < t_end:
            p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
            if p and p.param_id == name:
                ok = abs(p.param_value - val) < 1e-4 * max(1.0, abs(val))
                break
        if ok:
            break
    print(f"{name} = {val:g}: {'ok' if ok else 'NOT SET (now ' + str(get(name)) + ')'}", flush=True)
    bad |= not ok

if reboot:
    if hb.base_mode & MAV.MAV_MODE_FLAG_SAFETY_ARMED:
        sys.exit("armed: not rebooting")
    time.sleep(1)   # let the parameter writes reach storage
    m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
                            0, 1, 0, 0, 0, 0, 0, 0)
    time.sleep(3)
    hb = None
    t_end = time.time() + 60
    while time.time() < t_end and hb is None:
        hb = wait_hb(2)
    if hb is None:
        sys.exit("no heartbeat after reboot")
    t_end = time.time() + 8
    while time.time() < t_end:
        msg = m.recv_match(type="STATUSTEXT", blocking=True, timeout=0.5)
        if msg:
            print("  text:", msg.text, flush=True)
sys.exit(1 if bad else 0)
