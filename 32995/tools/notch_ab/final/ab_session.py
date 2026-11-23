"""MAVLink side of the notch A/B on the motorless RPI_UAVFC bench (run with Windows Python).

  ab_session.py setup            save the settings it changes, install the RPM script, set the quad's notches, reboot
  ab_session.py run TAG HASH     check the firmware, force-arm, hold until the SWD sampler is done, disarm, pull the log
  ab_session.py restore          put the saved settings back, remove the RPM script, reboot
"""
# Paths come from NOTCH_AB_* environment variables (pass them with WSLENV to Windows Python).
import json
import logging
import os
import sys
import time

sys.path.append(os.environ["NOTCH_AB_PYMAVLINK_SITE"])
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripting_profile"))

from pymavlink import mavutil  # noqa: E402
from pymavlink.mavftp import MAVFTP  # noqa: E402
import mav  # noqa: E402

PORT = "COM15"
BASE = os.environ["NOTCH_AB_DATA_WIN"]
SAVED = os.path.join(BASE, "original_params.json")
LOCAL_SCRIPT = os.path.join(BASE, "notch_ab_rpm.lua")
REMOTE_SCRIPT = "APM/scripts/notch_ab_rpm.lua"
SENTINEL = os.path.join(BASE, "sampling_done")
MAX_ARMED_S = 180
MAVC = mavutil.mavlink

# the quad's notch set from log 15, with the analog OSD off core1 as on the quad
# bidirectional DShot is off: the bench's motorless ESCs would otherwise report 0 RPM over the injected values
TEST = {"OSD_TYPE": 0, "SCR_ENABLE": 1, "SERVO_BLH_BDMASK": 0, "INS_HNTCH_HMNCS": 15,
        "INS_HNTC2_ENABLE": 1, "INS_HNTC2_MODE": 0, "INS_HNTC2_FREQ": 110, "INS_HNTC2_BW": 40, "INS_HNTC2_ATT": 20,
        "INS_HNTC2_HMNCS": 1, "INS_HNTC2_OPTS": 0, "INS_HNTC2_REF": 1,
        "INS_HNTC3_ENABLE": 1, "INS_HNTC3_MODE": 0, "INS_HNTC3_FREQ": 350, "INS_HNTC3_BW": 75, "INS_HNTC3_ATT": 20,
        "INS_HNTC3_HMNCS": 9, "INS_HNTC3_OPTS": 0, "INS_HNTC3_REF": 1}
# the enables go first and last on restore, so a sub-parameter is never written while hidden
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


def ftp_get(m, remote, local, timeout=300):
    f = MAVFTP(m, m.target_system, m.target_component)
    f.cmd_get([remote, local])
    ret = f.process_ftp_reply("get", timeout=timeout)
    ok = ret.error_code == 0 and os.path.exists(local)
    say(f"fetched {remote}: {'ok' if ok else 'FAILED'} {os.path.getsize(local) if os.path.exists(local) else 0} B")
    return ok


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
            sys.exit(f"could not read {missing}")
        with open(SAVED, "w") as fh:
            json.dump(values, fh, indent=1)
    say("original:", json.load(open(SAVED)))
    ok, _ = mav.ftp(m, "put", LOCAL_SCRIPT, REMOTE_SCRIPT)
    say("script uploaded:", ok)
    if not ok:
        sys.exit("script upload failed")
    for n, v in TEST.items():
        set_checked(m, n, v)
    m = reboot(m)
    # the third notch's parameters only exist once its enable has been through a boot
    for n, v in TEST.items():
        set_checked(m, n, v)
    m = reboot(m)
    say("after reboot:", {n: mav.param_get(m, n) for n in ("OSD_TYPE", "SCR_ENABLE", "INS_HNTCH_HMNCS", "INS_HNTC3_FREQ")})
    m.close()


def run(tag, want_hash):
    outdir = os.path.join(BASE, tag)
    os.makedirs(outdir, exist_ok=True)
    if os.path.exists(SENTINEL):
        os.remove(SENTINEL)
    m = connect()
    v = request(m, 148, "AUTOPILOT_VERSION")
    git = bytes(v.flight_custom_version[:8]).decode(errors="replace").rstrip("\0") if v else None
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
        # a forced arm is still refused until the EKF has initialised
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
        ftp_get(m, "@SYS/threads.txt", os.path.join(outdir, "threads_armed.txt"), timeout=20)
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
        if n not in enables:
            set_checked(m, n, v)
    for n in enables:
        set_checked(m, n, saved[n])
    f = MAVFTP(m, m.target_system, m.target_component)
    f.cmd_rm([REMOTE_SCRIPT])
    f.process_ftp_reply("RemoveFile", timeout=10)
    m = reboot(m)
    now = {n: mav.param_get(m, n) for n in saved}
    wrong = {n: (now[n], saved[n]) for n in saved if now[n] is None or abs(now[n] - saved[n]) > 1e-4}
    say("settings restored" if not wrong else f"NOT restored: {wrong}")
    f = MAVFTP(m, m.target_system, m.target_component)
    f.cmd_list(["APM/scripts"])
    f.process_ftp_reply("ListDirectory", timeout=10)
    say("APM/scripts:", [e.name for e in f.list_result if not e.is_dir])
    m.close()


if __name__ == "__main__":
    if sys.argv[1] == "setup":
        setup()
    elif sys.argv[1] == "run":
        run(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "restore":
        restore()
