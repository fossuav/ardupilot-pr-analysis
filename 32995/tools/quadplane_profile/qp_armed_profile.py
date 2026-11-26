#!/usr/bin/env python3
"""Profile both cores armed in MANUAL at zero throttle, without relying on timely MAVLink replies.

Usage: [RAWLOG=FILE] qp_armed_profile.py OUTDIR SAMPLES
OpenOCD must be running (TCL 50001) and the bridge connected. Force-arms, holds throttle at
RC3_MIN by override, samples both cores with pcs2.py, then force-disarms until the heartbeat
shows it disarmed. Force-disarms and stops if servo 1 ever goes above 1000.
"""
import os
import subprocess
import sys
import threading
import time

from pymavlink import mavutil

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plane_profile")
MAV = mavutil.mavlink
out, nsamp = sys.argv[1], int(sys.argv[2])
os.makedirs(out, exist_ok=True)
m = mavutil.mavlink_connection("tcpin:0.0.0.0:5770", source_system=255, source_component=190)
if os.environ.get("RAWLOG"):
    # every byte from the board, MAVLink or not, e.g. hal.console text on the same USB port
    m.logfile_raw = open(os.environ["RAWLOG"], "wb")
hb = None
while hb is None or hb.type == MAV.MAV_TYPE_GCS:
    hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=30)
m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
lock = threading.Lock()
state = {"run": True, "armed": False, "servo1": 0}


def send(fn, *a):
    with lock:
        fn(*a)


def override_loop():
    while state["run"]:
        send(m.mav.rc_channels_override_send, m.target_system, m.target_component,
             1500, 1500, 1100, 1500, 65535, 65535, 65535, 65535)
        time.sleep(0.1)


def arm(want):
    send(m.mav.command_long_send, m.target_system, m.target_component, MAV.MAV_CMD_COMPONENT_ARM_DISARM, 0,
         1 if want else 0, 21196, 0, 0, 0, 0, 0)


def reader():
    while state["run"]:
        msg = m.recv_match(type=["HEARTBEAT", "SERVO_OUTPUT_RAW", "STATUSTEXT"], blocking=True, timeout=0.5)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "HEARTBEAT" and msg.get_srcSystem() == m.target_system and msg.type != MAV.MAV_TYPE_GCS:
            state["armed"] = bool(msg.base_mode & MAV.MAV_MODE_FLAG_SAFETY_ARMED)
        elif t == "SERVO_OUTPUT_RAW":
            state["servo1"] = max(state["servo1"], msg.servo1_raw)
            if state["armed"] and msg.servo1_raw > 1000:
                for _ in range(5):
                    arm(False)
                print("SERVO 1 ABOVE 1000: disarmed", flush=True)
        elif t == "STATUSTEXT" and "Rate CPU" not in msg.text:
            print("  text:", msg.text, flush=True)


threading.Thread(target=override_loop, daemon=True).start()
threading.Thread(target=reader, daemon=True).start()
send(m.mav.command_long_send, m.target_system, m.target_component, MAV.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
     MAV.MAVLINK_MSG_ID_SERVO_OUTPUT_RAW, 100000, 0, 0, 0, 0, 0)
try:
    t_end = time.time() + 20
    while time.time() < t_end and not state["armed"]:
        arm(True)
        time.sleep(2)
    print(f"armed {state['armed']}", flush=True)
    time.sleep(10)
    if nsamp:
        r = subprocess.run([sys.executable, os.path.join(TOOLS, "pcs2.py"), str(nsamp), os.path.join(out, "arm_man")],
                           capture_output=True, text=True)
        print(r.stdout.strip(), flush=True)
    else:
        time.sleep(30)
finally:
    t_end = time.time() + 30
    while time.time() < t_end:
        arm(False)
        time.sleep(2)
        if not state["armed"]:
            break
    print(f"final armed {state['armed']}, servo1 peak {state['servo1']}", flush=True)
    state["run"] = False
    time.sleep(0.6)
    send(m.mav.rc_channels_override_send, m.target_system, m.target_component, 0, 0, 0, 0,
         65535, 65535, 65535, 65535)
