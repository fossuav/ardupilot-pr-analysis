#!/usr/bin/env python3
"""Plane CPU measurement session on the RPI_UAVFC bench, through bridge.py on 127.0.0.1:5770.

Usage: session.py OUTDIR COND [COND...]
  COND = TAG:STATE:MODE:SAMPLES[:THR]
    STATE    armed | disarmed
    MODE     Plane custom mode number (0 MANUAL, 5 FBWA)
    SAMPLES  PCSR samples per core (0 = no SWD; then the window is 20 s)
    THR      throttle PWM override, default 1100 (RC3_MIN, zero throttle); capped at THR_CAP

For each condition: mode, arm state, 10 s settle, read threads.txt (zeroes the per-core
peak), PC samples of both cores, XIP counters 3 x 1 s, then threads.txt, tasks.txt,
SYS_STATUS load, MEMINFO and STATUSTEXT over the window. RC overrides (sysid 255) run
at 10 Hz throughout: ch1/2/4 at 1500, ch3 at THR, ch5-8 untouched. Always force-disarms
on exit.
"""
import json
import logging
import os
import subprocess
import sys
import threading
import time

from pymavlink import mavutil
from pymavlink.mavftp import MAVFTP

MAV = mavutil.mavlink
FORCE = 21196
THR_MIN = 1100
THR_CAP = 1180          # 10% of the 1100-1900 range: the most this script will ever send
# armed with the throttle output (servo 1) above this PWM: force-disarm and stop
SERVO1_LIMIT = int(os.environ.get("SERVO1_LIMIT", "1000"))
TOOLS = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(TOOLS, "..", "scripting_profile")
IGN = 65535

out = sys.argv[1]
conds = sys.argv[2:]
os.makedirs(out, exist_ok=True)

m = mavutil.mavlink_connection("tcpin:0.0.0.0:5770", source_system=255, source_component=190)
lock = threading.Lock()
_raw_write = m.write


def locked_write(buf):
    with lock:
        return _raw_write(buf)


m.write = locked_write

t0 = time.time()
while time.time() - t0 < 30:
    hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
    if hb and hb.type != MAV.MAV_TYPE_GCS and hb.autopilot == MAV.MAV_AUTOPILOT_ARDUPILOTMEGA:
        m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
        break
else:
    sys.exit("no heartbeat")

state = {"thr": THR_MIN, "run": True, "armed": None, "mode": None}


def override_loop():
    while state["run"]:
        thr = min(int(state["thr"]), THR_CAP)
        m.mav.rc_channels_override_send(m.target_system, m.target_component,
                                        1500, 1500, thr, 1500, IGN, IGN, IGN, IGN)
        time.sleep(0.1)


FAKE_GPS = os.environ.get("FAKE_GPS") == "1"
GPS_EPOCH = 315964800      # 1980-01-06 in Unix time
GPS_LEAP_S = 18


def gps_loop():
    # a stationary 3D fix at SITL's default home, zero velocity, for GPS1_TYPE 14
    while state["run"]:
        now = time.time()
        gps_s = now - GPS_EPOCH + GPS_LEAP_S
        week = int(gps_s // 604800)
        week_ms = int((gps_s - week * 604800) * 1000)
        m.mav.gps_input_send(int(now * 1e6), 0, 0, week_ms, week, 3,
                             -353632621, 1491652374, 584.0, 0.8, 1.2, 0.0, 0.0, 0.0,
                             0.3, 1.0, 1.5, 16)
        time.sleep(0.1)


def release_overrides():
    # 0 on ch1-8 hands the channels back to the (absent) receiver
    m.mav.rc_channels_override_send(m.target_system, m.target_component, 0, 0, 0, 0, IGN, IGN, IGN, IGN)


def pump(secs, rec=None):
    """Read messages for secs, keeping the armed state and mode current."""
    t_end = time.time() + secs
    while time.time() < t_end:
        msg = m.recv_match(type=["HEARTBEAT", "SYS_STATUS", "MEMINFO", "STATUSTEXT", "SERVO_OUTPUT_RAW"],
                           blocking=True, timeout=0.5)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "SERVO_OUTPUT_RAW":
            if state["armed"] and msg.servo1_raw > SERVO1_LIMIT:
                print(f"  THROTTLE OUTPUT {msg.servo1_raw} above {SERVO1_LIMIT}: force-disarming", flush=True)
                for _ in range(5):
                    m.mav.command_long_send(m.target_system, m.target_component,
                                            MAV.MAV_CMD_COMPONENT_ARM_DISARM, 0, 0, FORCE, 0, 0, 0, 0, 0)
                    time.sleep(0.05)
                raise SystemExit("throttle watchdog")
            continue
        if t == "HEARTBEAT":
            if msg.get_srcSystem() == m.target_system and msg.type != MAV.MAV_TYPE_GCS:
                state["armed"] = bool(msg.base_mode & MAV.MAV_MODE_FLAG_SAFETY_ARMED)
                state["mode"] = msg.custom_mode
        elif t == "STATUSTEXT":
            print(f"  text: {msg.text}", flush=True)
            if rec is not None:
                rec["texts"].append(msg.text)
        elif rec is not None and t == "SYS_STATUS":
            rec["load"].append(msg.load / 10.0)
        elif rec is not None and t == "MEMINFO":
            rec["free"].append(getattr(msg, "freemem32", 0) or msg.freemem)


def command(cmd, *params):
    p = list(params) + [0] * (7 - len(params))
    for _ in range(3):
        m.mav.command_long_send(m.target_system, m.target_component, cmd, 0, *p)
        t_end = time.time() + 3
        while time.time() < t_end:
            a = m.recv_match(type=["COMMAND_ACK", "HEARTBEAT"], blocking=True, timeout=0.5)
            if a is None:
                continue
            if a.get_type() == "HEARTBEAT":
                if a.get_srcSystem() == m.target_system and a.type != MAV.MAV_TYPE_GCS:
                    state["armed"] = bool(a.base_mode & MAV.MAV_MODE_FLAG_SAFETY_ARMED)
                    state["mode"] = a.custom_mode
                continue
            if a.command == cmd:
                return a.result
    return None


def set_mode(n):
    r = command(MAV.MAV_CMD_DO_SET_MODE, MAV.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, n)
    pump(2)
    print(f"  mode {n}: result {r}, now {state['mode']}", flush=True)
    return state["mode"] == n


def set_armed(want):
    r = command(MAV.MAV_CMD_COMPONENT_ARM_DISARM, 1 if want else 0, FORCE)
    pump(2)
    print(f"  {'arm' if want else 'disarm'}: result {r}, armed {state['armed']}", flush=True)
    return state["armed"] == want


def ftp_get(remote, local):
    logging.basicConfig(level=logging.WARNING)
    f = MAVFTP(m, m.target_system, m.target_component)
    f.cmd_get([remote, local])
    ret = f.process_ftp_reply("OpenFileRO", timeout=20)
    return os.path.exists(local) and os.path.getsize(local) > 0, ret


for msg_id in (MAV.MAVLINK_MSG_ID_SYS_STATUS, MAV.MAVLINK_MSG_ID_MEMINFO):
    command(MAV.MAV_CMD_SET_MESSAGE_INTERVAL, msg_id, 500000)
command(MAV.MAV_CMD_SET_MESSAGE_INTERVAL, MAV.MAVLINK_MSG_ID_SERVO_OUTPUT_RAW, 100000)

ovr = threading.Thread(target=override_loop, daemon=True)
ovr.start()
if FAKE_GPS:
    threading.Thread(target=gps_loop, daemon=True).start()
results = []
try:
    pump(3)
    if FAKE_GPS:
        # EKF3 on a plane initialises only with a 3D fix; wait for it to be in use
        command(MAV.MAV_CMD_SET_MESSAGE_INTERVAL, MAV.MAVLINK_MSG_ID_EKF_STATUS_REPORT, 500000)
        t_end = time.time() + float(os.environ.get("EKF_WAIT", "60"))
        while time.time() < t_end:
            msg = m.recv_match(type=["EKF_STATUS_REPORT", "STATUSTEXT", "GPS_RAW_INT"], blocking=True, timeout=1)
            if msg is None:
                continue
            if msg.get_type() == "STATUSTEXT":
                print(f"  text: {msg.text}", flush=True)
            elif msg.get_type() == "EKF_STATUS_REPORT" and msg.flags & MAV.EKF_POS_HORIZ_ABS:
                print(f"  EKF horizontal position valid, flags {msg.flags:#x}", flush=True)
                break
        else:
            print("  EKF never reported a horizontal position", flush=True)
    for cond in conds:
        parts = cond.split(":")
        tag, want_state, mode, nsamp = parts[0], parts[1], int(parts[2]), int(parts[3])
        thr = int(parts[4]) if len(parts) > 4 else THR_MIN
        if thr > THR_CAP:
            sys.exit(f"{tag}: throttle {thr} above the cap {THR_CAP}")
        print(f"=== {tag}: {want_state}, mode {mode}, throttle {thr}", flush=True)
        state["thr"] = THR_MIN
        if want_state == "armed" and not state["armed"]:
            if not set_mode(0) or not set_armed(True):
                sys.exit(f"{tag}: could not arm in MANUAL")
        if want_state == "disarmed" and state["armed"]:
            if not set_armed(False):
                sys.exit(f"{tag}: could not disarm")
        if state["mode"] != mode and not set_mode(mode):
            sys.exit(f"{tag}: could not set mode {mode}")
        state["thr"] = thr
        pump(10)
        ftp_get("@SYS/threads.txt", os.path.join(out, f"{tag}_prime.txt"))
        rec = {"load": [], "free": [], "texts": []}
        start = time.strftime("%H:%M:%S")
        procs = []
        if nsamp:
            procs.append(subprocess.Popen([sys.executable, os.path.join(TOOLS, "pcs2.py"), str(nsamp),
                                           os.path.join(out, tag)],
                                          stdout=open(os.path.join(out, f"{tag}_pcs.out"), "w"),
                                          stderr=subprocess.STDOUT))
            while procs[0].poll() is None:
                pump(1, rec)
            xip = subprocess.Popen([sys.executable, os.path.join(PROFILE, "xipctr.py"), "3", "1", tag],
                                   stdout=open(os.path.join(out, f"{tag}_xip.txt"), "w"), stderr=subprocess.STDOUT)
            while xip.poll() is None:
                pump(1, rec)
        else:
            pump(20, rec)
        ok_t, _ = ftp_get("@SYS/threads.txt", os.path.join(out, f"{tag}_threads.txt"))
        ok_k, _ = ftp_get("@SYS/tasks.txt", os.path.join(out, f"{tag}_tasks.txt"))
        res = {"tag": tag, "start": start, "end": time.strftime("%H:%M:%S"), "armed": state["armed"],
               "mode": state["mode"], "thr": thr, "threads": ok_t, "tasks": ok_k,
               "load_mean": sum(rec["load"]) / len(rec["load"]) if rec["load"] else None,
               "load_max": max(rec["load"]) if rec["load"] else None, "load_n": len(rec["load"]),
               "free_min": min(rec["free"]) if rec["free"] else None, "texts": rec["texts"]}
        results.append(res)
        with open(os.path.join(out, f"{tag}_snap.json"), "w") as fh:
            json.dump(res, fh, indent=1)
        print(json.dumps({k: v for k, v in res.items() if k != "texts"}), flush=True)
finally:
    state["thr"] = THR_MIN
    time.sleep(0.3)
    for _ in range(3):
        if set_armed(False):
            break
    state["run"] = False
    ovr.join(timeout=1)
    release_overrides()
    print(f"final: armed {state['armed']}, mode {state['mode']}", flush=True)
