"""MAVLink side of the #35358 A/B on a motorless TBS_LUCID_H7 bench (run with Windows Python).

  h7_session.py backup           record the firmware identity and every parameter, before anything changes
  h7_session.py setup            save the settings it changes, install the RPM script, set the quad's notches, reboot
  h7_session.py run TAG HASH     check the firmware, force-arm, hold until the SWD sampler is done, disarm, pull the log
  h7_session.py restore          put the saved settings back, remove the RPM script, reboot

Paths come from H7_BENCH_DIR (Windows path) and H7_TOOLS (the analysis repo's scripting_profile folder).
"""
import json
import logging
import os
import sys
import time

from pymavlink import mavutil
from pymavlink.mavftp import MAVFTP

sys.path.insert(0, os.environ["H7_TOOLS"])
import mav  # noqa: E402

PORT = "COM29"
BASE = os.environ["H7_BENCH_DIR"]
SAVED = os.path.join(BASE, "original_params.json")
LOCAL_SCRIPT = os.path.join(BASE, "notch_ab_rpm.lua")
REMOTE_SCRIPT = "APM/scripts/notch_ab_rpm.lua"
SENTINEL = os.path.join(BASE, "sampling_done")
MAX_ARMED_S = 240
MAVC = mavutil.mavlink

# The RP2350 quad's notch set and rate thread, from its logs 12-15. Motors armed at zero output, as a precaution
# against anything wired to the outputs: the ESC-telemetry notch takes its frequencies from telemetry, not throttle.
TEST = {"SCR_ENABLE": 1, "FRAME_CLASS": 1, "FRAME_TYPE": 18, "MOT_SPIN_ARM": 0, "MOT_PWM_TYPE": 6,
        "SERVO_BLH_BDMASK": 0, "FSTRATE_ENABLE": 2, "FSTRATE_DIV": 2, "INS_GYRO_RATE": 2, "INS_FAST_SAMPLE": 1,
        "INS_HNTCH_ENABLE": 1, "INS_HNTCH_MODE": 3, "INS_HNTCH_FREQ": 40, "INS_HNTCH_BW": 10, "INS_HNTCH_ATT": 40,
        "INS_HNTCH_HMNCS": 15, "INS_HNTCH_OPTS": 22, "INS_HNTCH_REF": 1, "INS_HNTCH_FM_RAT": 1,
        "INS_HNTC2_ENABLE": 1, "INS_HNTC2_MODE": 0, "INS_HNTC2_FREQ": 110, "INS_HNTC2_BW": 40, "INS_HNTC2_ATT": 20,
        "INS_HNTC2_HMNCS": 1, "INS_HNTC2_OPTS": 0, "INS_HNTC2_REF": 1,
        "INS_HNTC3_ENABLE": 1, "INS_HNTC3_MODE": 0, "INS_HNTC3_FREQ": 350, "INS_HNTC3_BW": 75, "INS_HNTC3_ATT": 20,
        "INS_HNTC3_HMNCS": 9, "INS_HNTC3_OPTS": 0, "INS_HNTC3_REF": 1}
HOLD_ARMED = {"FS_THR_ENABLE": 0, "DISARM_DELAY": 0}
logging.basicConfig(level=logging.ERROR)


def say(*a):
    print(*a, flush=True)


def connect(timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            m = mavutil.mavlink_connection(PORT, baud=115200, source_system=255, source_component=190)
        except Exception:
            time.sleep(1)
            continue
        t0 = time.time()
        while time.time() - t0 < 5:
            try:
                h = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
            except Exception:
                break
            if h is not None and h.autopilot == MAVC.MAV_AUTOPILOT_ARDUPILOTMEGA:
                m.target_system, m.target_component = h.get_srcSystem(), h.get_srcComponent()
                return m
        try:
            m.close()
        except Exception:
            pass
        time.sleep(1)
    sys.exit("no heartbeat from the board")


def armed(m):
    for _ in range(20):
        h = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if h is not None and h.autopilot == MAVC.MAV_AUTOPILOT_ARDUPILOTMEGA:
            return bool(h.base_mode & MAVC.MAV_MODE_FLAG_SAFETY_ARMED)
    return None


def set_checked(m, name, value):
    got = mav.param_set(m, name, value)
    if got is None or abs(got - value) > 1e-4:
        raise RuntimeError(f"{name} did not take {value}: read {got}")


def reboot(m):
    m.mav.command_long_send(m.target_system, m.target_component, MAVC.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, 0,
                            1, 0, 0, 0, 0, 0, 0)
    time.sleep(0.5)
    try:
        m.close()
    except Exception:
        pass
    time.sleep(8)
    return connect()


def request(m, msg_id, name, tries=5):
    for _ in range(tries):
        m.mav.command_long_send(m.target_system, m.target_component, MAVC.MAV_CMD_REQUEST_MESSAGE, 0,
                                msg_id, 0, 0, 0, 0, 0, 0)
        r = m.recv_match(type=name, blocking=True, timeout=2)
        if r is not None:
            return r
    return None


def git_hash(m):
    v = request(m, 148, "AUTOPILOT_VERSION")
    if v is None:
        return None, None
    return bytes(v.flight_custom_version[:8]).decode(errors="replace").rstrip("\0"), v


def ftp_get(m, remote, local, timeout=300):
    f = MAVFTP(m, m.target_system, m.target_component)
    f.cmd_get([remote, local])
    ret = f.process_ftp_reply("get", timeout=timeout)
    ok = ret.error_code == 0 and os.path.exists(local)
    say(f"fetched {remote}: {'ok' if ok else 'FAILED'} {os.path.getsize(local) if os.path.exists(local) else 0} B")
    return ok


def backup():
    m = connect()
    if armed(m):
        sys.exit("board is armed")
    git, v = git_hash(m)
    if v is not None:
        fw = v.flight_sw_version
        say(f"firmware {fw >> 24}.{(fw >> 16) & 0xff}.{(fw >> 8) & 0xff} type {fw & 0xff} git {git} "
            f"board {v.vendor_id:#x}:{v.product_id:#x} board_version {v.board_version}")
    h = m.recv_match(type="HEARTBEAT", blocking=True, timeout=3)
    say("vehicle type", h.type if h else None)
    params = {}
    m.mav.param_request_list_send(m.target_system, m.target_component)
    total, last = None, time.time()
    while time.time() - last < 5:
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
        if p is None:
            continue
        last = time.time()
        params[p.param_id] = p.param_value
        total = p.param_count
        if total and len(params) >= total:
            break
    missing = None
    if total and len(params) < total:
        missing = total - len(params)
    path = os.path.join(BASE, "board_params_before.parm")
    with open(path, "w") as fh:
        for k in sorted(params):
            fh.write(f"{k},{params[k]:.7g}\n")
    say(f"saved {len(params)} of {total} parameters to {path}" + (f", {missing} missing" if missing else ""))
    m.close()


def setup():
    m = connect()
    if armed(m):
        sys.exit("board is armed")
    names = list(TEST) + list(HOLD_ARMED)
    if os.path.exists(SAVED):
        say("keeping the settings saved earlier")
    else:
        values = {n: mav.param_get(m, n) for n in names}
        missing = [n for n, v in values.items() if v is None]
        if missing:
            say(f"not present before setup (set after enables): {missing}")
        with open(SAVED, "w") as fh:
            json.dump(values, fh, indent=1)
    # the board had scripting off, so APM/scripts does not exist yet; restore removes it again
    f = MAVFTP(m, m.target_system, m.target_component)
    f.cmd_mkdir(["APM/scripts"])
    say("mkdir APM/scripts:", f.process_ftp_reply("CreateDirectory", timeout=10).error_code)
    ok, _ = mav.ftp(m, "put", LOCAL_SCRIPT, REMOTE_SCRIPT)
    say("script uploaded:", ok)
    if not ok:
        sys.exit("script upload failed")
    # two passes with a reboot between, as some parameters only exist once their enable has been through a boot
    for _ in range(2):
        for n, v in TEST.items():
            try:
                set_checked(m, n, v)
            except RuntimeError as e:
                say("pending:", e)
        m = reboot(m)
    bad = {n: mav.param_get(m, n) for n in TEST}
    bad = {n: got for n, got in bad.items() if got is None or abs(got - TEST[n]) > 1e-4}
    say("all test settings in place" if not bad else f"NOT set: {bad}")
    m.close()
    if bad:
        sys.exit(1)


def run(tag, want_hash):
    outdir = os.path.join(BASE, tag)
    os.makedirs(outdir, exist_ok=True)
    if os.path.exists(SENTINEL):
        os.remove(SENTINEL)
    m = connect()
    git, _ = git_hash(m)
    if git != want_hash:
        sys.exit(f"board runs {git}, wanted {want_hash}")
    for n, val in TEST.items():
        got = mav.param_get(m, n)
        if got is None or abs(got - val) > 1e-4:
            sys.exit(f"{n} is {got}, wanted {val}")
    st = request(m, 2, "SYSTEM_TIME")
    up = st.time_boot_ms * 0.001 if st else 0
    if up < 25:
        time.sleep(25 - up)
    texts = []
    try:
        for n, val in HOLD_ARMED.items():
            set_checked(m, n, val)
        is_armed = False
        for _ in range(20):
            res = mav.command(m, MAVC.MAV_CMD_COMPONENT_ARM_DISARM, 1, mav.FORCE)
            if res == 0 and armed(m):
                is_armed = True
                break
            time.sleep(2)
        if not is_armed:
            raise RuntimeError("board did not arm")
        say("ARMED")
        t0 = time.time()
        while not os.path.exists(SENTINEL) and time.time() - t0 < MAX_ARMED_S:
            r = m.recv_match(type="STATUSTEXT", blocking=True, timeout=0.2)
            if r is not None:
                texts.append(r.text)
        say(f"held armed {time.time() - t0:.0f} s, still armed: {armed(m)}")
    finally:
        say("disarm result", mav.command(m, MAVC.MAV_CMD_COMPONENT_ARM_DISARM, 0, mav.FORCE))
        say("armed now:", armed(m))
        saved = json.load(open(SAVED))
        for n in HOLD_ARMED:
            set_checked(m, n, saved[n])
    time.sleep(4)
    last = os.path.join(outdir, "LASTLOG.TXT")
    if ftp_get(m, "APM/LOGS/LASTLOG.TXT", last, timeout=20):
        num = int(open(last).read().strip())
        ftp_get(m, f"APM/LOGS/{num:08d}.BIN", os.path.join(outdir, "bench.BIN"))
    say("text while armed:", sorted(set(texts)))
    m.close()
    say("session done")


def restore():
    m = connect()
    if armed(m):
        sys.exit("board is armed")
    saved = json.load(open(SAVED))
    enables = [n for n in saved if n.endswith("_ENABLE") and n != "FS_THR_ENABLE"]
    for n, v in saved.items():
        if n not in enables and v is not None:
            set_checked(m, n, v)
    for n in enables:
        if saved[n] is not None:
            set_checked(m, n, saved[n])
    f = MAVFTP(m, m.target_system, m.target_component)
    f.cmd_rm([REMOTE_SCRIPT])
    f.process_ftp_reply("RemoveFile", timeout=10)
    f = MAVFTP(m, m.target_system, m.target_component)
    f.cmd_rmdir(["APM/scripts"])
    say("rmdir APM/scripts:", f.process_ftp_reply("RemoveDirectory", timeout=10).error_code)
    m = reboot(m)
    now = {n: mav.param_get(m, n) for n in saved if saved[n] is not None}
    wrong = {n: (now[n], saved[n]) for n in now if now[n] is None or abs(now[n] - saved[n]) > 1e-4}
    say("settings restored" if not wrong else f"NOT restored: {wrong}")
    m.close()


if __name__ == "__main__":
    {"backup": backup, "setup": setup, "restore": restore}.get(sys.argv[1], lambda: run(sys.argv[2], sys.argv[3]))()
