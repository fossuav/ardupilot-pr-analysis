#!/usr/bin/env python3
"""Drive Plane's elevon outputs on the RPI_UAVFC bench, disarmed, and check them.

Usage: servo_test.py OUTDIR   (through bridge.py on 127.0.0.1:5770, OpenOCD TCL on 50001)

RC overrides (sysid 255) move roll and pitch, hold throttle at RC3_MIN (zero throttle:
without a valid throttle channel Plane's radio failsafe resets roll and pitch to
trim) and send every other channel as UINT16_MAX, which the autopilot ignores. Steps run in MANUAL, then FBWA,
holding 3 s each. Per step: the median of SERVO_OUTPUT_RAW over the last second, the
elevon mix predicted from the board's own parameters (MANUAL only), and PWM slice 3
over SWD (GPIO7 = S3 on channel B, GPIO6 = S4 on channel A). Aborts, releasing the
overrides and force-disarming, if the board reports armed or S1 rises above
SERVO1_MIN. Always finishes in RTL with the overrides released.
"""
import csv
import json
import os
import socket
import statistics
import sys
import time

from pymavlink import mavutil

MAV = mavutil.mavlink
IGN = 65535
MANUAL, FBWA, RTL = 0, 5, 11
SLICE3 = 0x400A803C           # PWM CH3_CSR; DIV, CTR, CC, TOP follow
CLK_SYS_HZ = 200e6
HOLD = 3.0
STEPS = [(MANUAL, 1500, 1500), (MANUAL, 1800, 1500), (MANUAL, 1200, 1500), (MANUAL, 1500, 1800),
         (MANUAL, 1500, 1200), (MANUAL, 1800, 1800), (MANUAL, 1500, 1500),
         (FBWA, 1500, 1500), (FBWA, 1800, 1500), (FBWA, 1200, 1500), (FBWA, 1500, 1800),
         (FBWA, 1500, 1200), (FBWA, 1500, 1500)]
PARAMS = ["RC1_MIN", "RC1_MAX", "RC1_TRIM", "RC1_REVERSED", "RC2_MIN", "RC2_MAX", "RC2_TRIM", "RC2_REVERSED",
          "RC3_MIN", "SERVO1_MIN", "SERVO3_MIN", "SERVO3_MAX", "SERVO3_TRIM", "SERVO3_REVERSED", "SERVO3_FUNCTION",
          "SERVO4_MIN", "SERVO4_MAX", "SERVO4_TRIM", "SERVO4_REVERSED", "SERVO4_FUNCTION",
          "MIXING_GAIN", "MIXING_OFFSET", "MAN_EXPO_ROLL", "MAN_EXPO_PITCH", "RCMAP_ROLL", "RCMAP_PITCH",
          "RCMAP_THROTTLE"]


class Abort(Exception):
    pass


def connect():
    m = mavutil.mavlink_connection("tcpin:0.0.0.0:5770", source_system=255, source_component=190)
    t0 = time.time()
    while time.time() - t0 < 30:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb and hb.type != MAV.MAV_TYPE_GCS and hb.autopilot == MAV.MAV_AUTOPILOT_ARDUPILOTMEGA:
            m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
            return m
    sys.exit("no heartbeat from the board")


def get_params(m, names):
    out = {}
    for n in names:
        for _ in range(3):
            m.mav.param_request_read_send(m.target_system, m.target_component, n.encode(), -1)
            t0 = time.time()
            while time.time() - t0 < 1.5 and n not in out:
                p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.3)
                if p and p.param_id == n:
                    out[n] = p.param_value
            if n in out:
                break
        if n not in out:
            sys.exit(f"could not read {n}")
    return out


def rc_angle(pwm, mn, mx, trim, rev):
    """RC_Channel::get_control_in_zero_dz() for an angle channel"""
    r = min(max(pwm, mn), mx)
    s = -1 if rev else 1
    if r > trim:
        return s * 4500.0 * (r - trim) / (mx - trim)
    if r < trim:
        return s * 4500.0 * (r - trim) / (trim - mn)
    return 0.0


def pwm_from_angle(v, mn, mx, trim, rev):
    """SRV_Channel::pwm_from_angle()"""
    if rev:
        v = -v
    v = max(-4500.0, min(4500.0, v))
    if v > 0:
        return trim + int(v * (mx - trim) / 4500.0)
    return trim - int(-v * (trim - mn) / 4500.0)


def predict(p, ch1, ch2):
    """MANUAL with no expo and no MIXING_OFFSET: (S3 elevon left, S4 elevon right)"""
    if p["MAN_EXPO_ROLL"] or p["MAN_EXPO_PITCH"] or p["MIXING_OFFSET"]:
        return None
    ail = rc_angle(ch1, p["RC1_MIN"], p["RC1_MAX"], p["RC1_TRIM"], p["RC1_REVERSED"])
    elev = rc_angle(ch2, p["RC2_MIN"], p["RC2_MAX"], p["RC2_TRIM"], p["RC2_REVERSED"])
    g = p["MIXING_GAIN"]
    left = max(-4500.0, min(4500.0, (elev - ail) * g))
    right = max(-4500.0, min(4500.0, (elev + ail) * g))
    return (pwm_from_angle(left, p["SERVO3_MIN"], p["SERVO3_MAX"], p["SERVO3_TRIM"], p["SERVO3_REVERSED"]),
            pwm_from_angle(right, p["SERVO4_MIN"], p["SERVO4_MAX"], p["SERVO4_TRIM"], p["SERVO4_REVERSED"]))


class Tcl:
    def __init__(self):
        try:
            self.s = socket.create_connection(("127.0.0.1", 50001), timeout=5)
        except OSError:
            self.s = None

    def read(self, addr, n):
        if self.s is None:
            return None
        self.s.sendall(f"read_memory {addr:#x} 32 {n}".encode() + b"\x1a")
        buf = b""
        while not buf.endswith(b"\x1a"):
            buf += self.s.recv(4096)
        return [int(w, 16) for w in buf[:-1].decode().split()]

    def slice3(self):
        r = self.read(SLICE3, 5)
        if r is None:
            return None
        csr, div, _, cc, top = r
        tick_us = ((div >> 4) + (div & 0xF) / 16.0) / CLK_SYS_HZ * 1e6
        period_us = (top + 1) * tick_us * (2 if csr & 2 else 1)
        return {"csr": csr, "div": div, "top": top, "cc": cc, "s3_us": (cc >> 16) * tick_us,
                "s4_us": (cc & 0xFFFF) * tick_us, "frame_hz": 1e6 / period_us}


class Bench:
    def __init__(self, m, p, out):
        self.m, self.p = m, p
        self.ch1 = self.ch2 = self.ch3 = IGN
        self.last_ovr = 0.0
        self.mode = self.armed = None
        self.rc = self.att = None
        self.rows = []
        self.csv = csv.writer(out)
        self.csv.writerow(["t", "mode", "ovr1", "ovr2", "rc1", "rc2", "rc3", "s1", "s3", "s4", "roll", "pitch"])
        self.t0 = time.time()

    def override(self):
        self.m.mav.rc_channels_override_send(self.m.target_system, self.m.target_component,
                                             self.ch1, self.ch2, self.ch3, IGN, IGN, IGN, IGN, IGN)
        self.last_ovr = time.time()

    def pump(self, secs):
        until = time.time() + secs
        while time.time() < until:
            if self.ch1 != IGN and time.time() - self.last_ovr >= 0.1:
                self.override()
            msg = self.m.recv_match(blocking=True, timeout=0.02)
            if msg is None:
                continue
            t = msg.get_type()
            if t == "HEARTBEAT" and msg.get_srcSystem() == self.m.target_system and msg.type != MAV.MAV_TYPE_GCS:
                self.mode = msg.custom_mode
                self.armed = bool(msg.base_mode & MAV.MAV_MODE_FLAG_SAFETY_ARMED)
                if self.armed:
                    raise Abort("board reports armed")
            elif t == "RC_CHANNELS":
                self.rc = (msg.chan1_raw, msg.chan2_raw, msg.chan3_raw)
            elif t == "ATTITUDE":
                self.att = (round(msg.roll * 57.2958, 1), round(msg.pitch * 57.2958, 1))
            elif t == "STATUSTEXT":
                print(f"  STATUSTEXT {msg.text}")
            elif t == "SERVO_OUTPUT_RAW" and msg.port == 0:
                if msg.servo1_raw > self.p["SERVO1_MIN"]:
                    raise Abort(f"S1 at {msg.servo1_raw}")
                row = (time.time() - self.t0, self.mode, self.ch1, self.ch2) + (self.rc or (0, 0, 0)) + \
                    (msg.servo1_raw, msg.servo3_raw, msg.servo4_raw) + (self.att or (0, 0))
                self.rows.append(row)
                self.csv.writerow([f"{row[0]:.3f}"] + list(row[1:]))

    def set_mode(self, mode):
        for _ in range(5):
            self.m.mav.command_long_send(self.m.target_system, self.m.target_component, MAV.MAV_CMD_DO_SET_MODE, 0,
                                         MAV.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode, 0, 0, 0, 0, 0)
            self.pump(1.2)
            if self.mode == mode:
                return
        raise Abort(f"mode {mode} not taken (board in {self.mode})")

    def release(self):
        self.ch1 = self.ch2 = self.ch3 = 0
        for _ in range(5):
            self.override()
            self.pump(0.1)
        self.ch1 = self.ch2 = self.ch3 = IGN


def main():
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    m = connect()
    for msg_id, hz in ((MAV.MAVLINK_MSG_ID_SERVO_OUTPUT_RAW, 20), (MAV.MAVLINK_MSG_ID_RC_CHANNELS, 10),
                       (MAV.MAVLINK_MSG_ID_ATTITUDE, 10)):
        m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                                msg_id, 1e6 / hz, 0, 0, 0, 0, 0)
    p = get_params(m, PARAMS)
    if (p["RCMAP_ROLL"], p["RCMAP_PITCH"]) != (1, 2) or p["RCMAP_THROTTLE"] in (1, 2):
        sys.exit("roll/pitch are not RC1/RC2, or throttle is on one of them: refusing to override")
    thr = int(p["RC3_MIN"])
    if thr > 1100:
        sys.exit(f"RC3_MIN {thr}: refusing to hold throttle above 1100")
    if (p["SERVO3_FUNCTION"], p["SERVO4_FUNCTION"]) != (77, 78):
        sys.exit("S3/S4 are not elevon left/right")
    tcl = Tcl()
    b = Bench(m, p, open(f"{outdir}/servo.csv", "w", newline=""))
    b.pump(2.0)
    if b.armed is not False:
        sys.exit(f"armed state {b.armed}: refusing to start")
    start_mode = b.mode
    print(f"start: mode {start_mode}, disarmed, RC {b.rc}, SWD {'yes' if tcl.s else 'no'}")
    results = []
    try:
        b.ch1, b.ch2, b.ch3 = 1500, 1500, thr
        b.override()
        b.pump(4.0)
        if b.rc != (1500, 1500, thr):
            raise Abort(f"overrides not taken: RC {b.rc}")
        print(f"overrides taken: RC {b.rc}, mode {b.mode}")
        for mode, c1, c2 in STEPS:
            if b.mode != mode:
                b.set_mode(mode)
            b.ch1, b.ch2 = c1, c2
            b.override()
            t_start = time.time() - b.t0
            b.pump(HOLD)
            last = [r for r in b.rows if r[0] >= t_start + HOLD - 1.0]
            s3 = statistics.median(r[8] for r in last)
            s4 = statistics.median(r[9] for r in last)
            s1 = max(r[7] for r in last)
            rc = (last[-1][4], last[-1][5], last[-1][6])
            hw = tcl.slice3()
            exp = predict(p, c1, c2) if mode == MANUAL else None
            res = {"mode": mode, "ovr": [c1, c2], "rc": rc, "s1_max": s1, "s3": s3, "s4": s4,
                   "s3_range": [min(r[8] for r in last), max(r[8] for r in last)],
                   "s4_range": [min(r[9] for r in last), max(r[9] for r in last)],
                   "expected": exp, "att": b.att, "hw": hw}
            results.append(res)
            ok = "" if exp is None else ("  ok" if (s3, s4) == exp else f"  MISMATCH want {exp}")
            hws = "" if hw is None else f"  pin S3 {hw['s3_us']:.0f} us S4 {hw['s4_us']:.0f} us at {hw['frame_hz']:.2f} Hz"
            print(f"{'MANUAL' if mode == MANUAL else 'FBWA':6s} ovr roll {c1} pitch {c2}: rc {rc[0]}/{rc[1]} thr {rc[2]}, "
                  f"S1 {s1}, S3 {s3:.0f} S4 {s4:.0f}{ok}{hws}  att {b.att}")
    except Abort as e:
        print(f"ABORT: {e}")
        b.ch1 = b.ch2 = b.ch3 = 0
        b.override()
        m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                                0, 21196, 0, 0, 0, 0, 0)
    finally:
        b.release()
        try:
            b.set_mode(RTL)
        except Abort as e:
            print(f"could not return to RTL: {e}")
        b.pump(2.0)
        print(f"end: mode {b.mode}, armed {b.armed}, RC {b.rc}, S3/S4 {b.rows[-1][8]}/{b.rows[-1][9]}")
        json.dump({"params": p, "steps": results}, open(f"{outdir}/servo.json", "w"), indent=1)


if __name__ == "__main__":
    main()
