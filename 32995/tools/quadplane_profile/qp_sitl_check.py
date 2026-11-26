#!/usr/bin/env python3
"""QuadPlane SITL check of AP_Vehicle's rate thread: hover in QHOVER and QLOITER, back to QLAND.

Usage: qp_sitl_check.py REPO OUTDIR EXTRA_DEFAULTS
Starts build/sitl/bin/arduplane (quadplane model) in OUTDIR with the quadplane defaults plus
EXTRA_DEFAULTS, flies, and prints the rate thread's messages, the climb and the RTDT count.
"""
import os
import subprocess
import sys
import time

from pymavlink import mavutil

repo, out, extra = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
MAV = mavutil.mavlink
defaults = f"{repo}/Tools/autotest/default_params/quadplane.parm,{extra}"
sitl = subprocess.Popen([f"{repo}/build/sitl/bin/arduplane", "-w", "--model", "quadplane",
                         "--home", "-35.363261,149.165230,584,353", "--speedup", "1",
                         "--defaults", defaults],
                        cwd=out, stdout=open(f"{out}/sitl.log", "w"), stderr=subprocess.STDOUT)
texts = []


def pump(m, secs, want=None):
    t_end = time.time() + secs
    last = None
    while time.time() < t_end:
        msg = m.recv_match(blocking=True, timeout=0.5)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "STATUSTEXT":
            texts.append(msg.text)
            print("  text:", msg.text, flush=True)
        if want and t == want:
            last = msg
    return last


try:
    time.sleep(2)
    m = mavutil.mavlink_connection("tcp:127.0.0.1:5760", source_system=255, retries=20)
    m.wait_heartbeat(timeout=30)
    m.mav.request_data_stream_send(m.target_system, m.target_component, MAV.MAV_DATA_STREAM_ALL, 10, 1)
    # wait for the EKF and GPS, as the autotests do
    t_end = time.time() + 90
    while time.time() < t_end:
        msg = m.recv_match(type=["EKF_STATUS_REPORT", "STATUSTEXT"], blocking=True, timeout=1)
        if msg is None:
            continue
        if msg.get_type() == "STATUSTEXT":
            texts.append(msg.text)
            print("  text:", msg.text, flush=True)
        elif msg.flags & MAV.EKF_POS_HORIZ_ABS and msg.flags & MAV.EKF_PRED_POS_HORIZ_ABS:
            break
    pump(m, 5)

    def rc(thr):
        m.mav.rc_channels_override_send(m.target_system, m.target_component, 1500, 1500, thr, 1500,
                                        65535, 65535, 65535, 65535)

    def mode(n):
        for _ in range(3):
            m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_DO_SET_MODE, 0,
                                    MAV.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, n, 0, 0, 0, 0, 0)
            rc(thr_now[0])
            hb = pump(m, 1, "HEARTBEAT")
            if hb and hb.custom_mode == n:
                return True
        return False

    thr_now = [1000]
    rc(1000)
    # motor test, disarmed: motor 1 at 10% for 2 s; the main loop owns the motors meanwhile
    m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_DO_MOTOR_TEST, 0,
                            1, 0, 10, 2, 1, 0, 0)
    peak = 0
    t_end = time.time() + 4
    while time.time() < t_end:
        rc(1000)
        msg = pump(m, 0.2, "SERVO_OUTPUT_RAW")
        if msg:
            peak = max(peak, msg.servo1_raw)
    print(f"motor test: servo1 peak {peak}", flush=True)
    print("QHOVER:", mode(18), flush=True)
    m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                            1, 21196, 0, 0, 0, 0, 0)
    for thr, secs in ((1000, 3), (1750, 8), (1500, 15)):
        thr_now[0] = thr
        t_end = time.time() + secs
        while time.time() < t_end:
            rc(thr)
            pump(m, 0.2)
    gpi = pump(m, 1, "GLOBAL_POSITION_INT")
    print(f"QHOVER height {gpi.relative_alt / 1000.0:.1f} m" if gpi else "no position", flush=True)
    print("QLOITER:", mode(19), flush=True)
    t_end = time.time() + 15
    while time.time() < t_end:
        rc(1500)
        pump(m, 0.2)
    gpi = pump(m, 1, "GLOBAL_POSITION_INT")
    print(f"QLOITER height {gpi.relative_alt / 1000.0:.1f} m" if gpi else "no position", flush=True)
    print("FBWA:", mode(5), flush=True)
    t_end = time.time() + 25
    while time.time() < t_end:
        rc(1800)
        msg = pump(m, 0.2, "VFR_HUD")
    print(f"FBWA airspeed {msg.airspeed:.1f} m/s, alt {msg.alt:.1f} m" if msg else "no VFR_HUD", flush=True)
    print("QHOVER again:", mode(18), flush=True)
    t_end = time.time() + 20
    while time.time() < t_end:
        rc(1500)
        msg = pump(m, 0.2, "VFR_HUD")
    print(f"QHOVER airspeed {msg.airspeed:.1f} m/s" if msg else "no VFR_HUD", flush=True)
    print("QLAND:", mode(20), flush=True)
    t_end = time.time() + 90
    while time.time() < t_end:
        rc(1500)
        hb = pump(m, 0.5, "HEARTBEAT")
        if hb and not hb.base_mode & MAV.MAV_MODE_FLAG_SAFETY_ARMED:
            print("landed and disarmed", flush=True)
            break
finally:
    sitl.terminate()
    sitl.wait(timeout=10)

logs = sorted(f for f in os.listdir(f"{out}/logs") if f.endswith(".BIN"))
log = mavutil.mavlink_connection(f"{out}/logs/{logs[-1]}")
n_rtdt, dts, parm = 0, [], {}
while True:
    msg = log.recv_match(type=["RTDT", "PARM", "QTUN"], blocking=False)
    if msg is None:
        break
    if msg.get_type() == "QTUN":
        parm["Trn"] = sorted(set(parm.get("Trn", [])) | {msg.Trn})
        continue
    if msg.get_type() == "RTDT":
        n_rtdt += 1
        dts.append(msg.dtMax)
    elif msg.Name in ("Q_FSTRATE_ENABLE", "Q_FSTRATE_DIV", "SCHED_LOOP_RATE", "INS_GYRO_RATE"):
        parm[msg.Name] = msg.Value
print("params", parm)
print(f"RTDT {n_rtdt}, worst dtMax {max(dts) * 1e3:.2f} ms" if dts else "RTDT 0")
print("rate texts", [t for t in texts if "Rate CPU" in t])
