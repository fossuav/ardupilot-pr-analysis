#!/usr/bin/env python3
"""RPI_UAVFC buzzer / LED-pad / ALT-output bench, through bridge.py on 127.0.0.1:5770 and
OpenOCD TCL on 50001.

  buzz_bench.py case LABEL [NAME=VALUE ...]   set params, reboot, banner, SWD reads, tune test
  buzz_bench.py params NAME...                print params
  buzz_bench.py set NAME=VALUE...             set params, no reboot
  buzz_bench.py put LOCAL REMOTE              MAVFTP upload
  buzz_bench.py rm REMOTE                     MAVFTP remove
"""
import json
import logging
import os
import socket
import subprocess
import sys
import time

from pymavlink import mavutil
from pymavlink.mavftp import MAVFTP

MAV = mavutil.mavlink
OOCD = "/opt/openocd-0.12.0+dev-x64-win"
SEP = b"\x1a"
CLK_SYS = 200e6
IO_BANK0 = 0x40028000
PWM_BASE = 0x400A8000
PINS = {2: "LED pad (out 8)", 3: "buzzer", 5: "TEL (out 9, ALT 1)", 12: "GP1 (out 5)",
        13: "GP2 (out 6)", 14: "GP3 (out 7)", 41: "SBUS (out 10, ALT 1)"}
SLICES = (1, 2, 6, 7, 8)
SHOW = ["SERVO5_FUNCTION", "SERVO8_FUNCTION", "SERVO9_FUNCTION", "SERVO10_FUNCTION",
        "BRD_ALT_CONFIG", "SCR_ENABLE", "NTF_BUZZ_TYPES"]
TUNE = "MFT60L1O4CC"   # two whole notes at tempo 60: 8 s of buzzer


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def win(path):
    return subprocess.check_output(["wslpath", "-w", path], text=True).strip()


def connect(timeout=60):
    m = mavutil.mavlink_connection("tcpin:0.0.0.0:5770", source_system=255, source_component=190)
    t0 = time.time()
    while time.time() - t0 < timeout:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb and hb.type != MAV.MAV_TYPE_GCS and hb.autopilot == MAV.MAV_AUTOPILOT_ARDUPILOTMEGA:
            m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
            return m
    sys.exit("no heartbeat from the board")


def pump(m, secs, texts):
    t_end = time.time() + secs
    while time.time() < t_end:
        msg = m.recv_match(type="STATUSTEXT", blocking=True, timeout=0.2)
        if msg:
            texts.append(msg.text)


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
        out.setdefault(n, None)
    return out


def set_params(m, pairs):
    for name, value in pairs:
        for _ in range(3):
            m.mav.param_set_send(m.target_system, m.target_component, name.encode(), value,
                                 MAV.MAV_PARAM_TYPE_REAL32)
            t0 = time.time()
            got = None
            while time.time() - t0 < 2:
                p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.3)
                if p and p.param_id == name:
                    got = p.param_value
                    break
            if got is not None and abs(got - value) < 1e-3:
                log(f"set {name} = {got:g}")
                break
        else:
            sys.exit(f"could not set {name} to {value}")


def banner(m):
    texts = []
    m.mav.command_long_send(m.target_system, m.target_component, 42428, 0, 0, 0, 0, 0, 0, 0, 0)
    pump(m, 4, texts)
    return texts


# ---------------- OpenOCD ----------------

def openocd_running():
    return "openocd" in subprocess.run(["tasklist.exe"], capture_output=True, text=True).stdout.lower()


class Tcl:
    def __init__(self):
        self.s = socket.create_connection(("127.0.0.1", 50001), timeout=5)

    def cmd(self, c):
        self.s.sendall(c.encode() + SEP)
        buf = b""
        while not buf.endswith(SEP):
            chunk = self.s.recv(65536)
            if not chunk:
                break
            buf += chunk
        return buf[:-1].decode(errors="replace").strip()

    def rd(self, addr, n=1):
        return [int(w, 16) for w in self.cmd(f"rp2350.cm0 read_memory {addr:#x} 32 {n}").split()]


def start_openocd(logpath):
    p = subprocess.Popen(["./openocd.exe", "-s", win(f"{OOCD}/scripts"), "-f", "interface/cmsis-dap.cfg",
                          "-f", "target/rp2350.cfg", "-c", "gdb port 50000", "-c", "tcl port 50001",
                          "-c", "telnet port 50002", "-c", "adapter speed 5000"],
                         cwd=OOCD, stdout=open(logpath, "w"), stderr=subprocess.STDOUT)
    t_end = time.time() + 20
    while time.time() < t_end:
        try:
            socket.create_connection(("127.0.0.1", 50001), timeout=2).close()
            return p
        except OSError:
            time.sleep(0.5)
    sys.exit("OpenOCD did not open its TCL port")


def release_openocd():
    if not openocd_running():
        return
    try:
        t = Tcl()
        t.cmd("poll off")
        for core in (0, 1):
            t.cmd(f"rp2350.cm{core} write_memory 0xE000EDF0 32 {{0xA05F0000}}")
        t.s.sendall(b"shutdown" + SEP)
    except OSError:
        pass
    for _ in range(40):
        if not openocd_running():
            return
        time.sleep(0.5)
    sys.exit("OpenOCD did not shut down")


def funcsel(t, g):
    return t.rd(IO_BANK0 + 8 * g + 4)[0] & 0x1F


def slice_regs(t, sl):
    csr, div, _, cc, top = t.rd(PWM_BASE + 0x14 * sl, 5)
    divf = (div >> 4) + (div & 0xF) / 16
    tick_us = divf / CLK_SYS * 1e6 if divf else 0
    return {"en": (t.rd(PWM_BASE + 0xF0)[0] >> sl) & 1, "csr": csr, "div": round(divf, 4), "top": top,
            "period_us": round((top + 1) * tick_us, 1), "a_us": round((cc & 0xFFFF) * tick_us, 1),
            "b_us": round((cc >> 16) * tick_us, 1)}


def swd_static(t):
    out = {"funcsel": {g: funcsel(t, g) for g in PINS}, "slices": {sl: slice_regs(t, sl) for sl in SLICES}}
    for g, name in PINS.items():
        log(f"  GPIO{g:2d} {name:22s} FUNCSEL {out['funcsel'][g]:2d}")
    for sl, r in out["slices"].items():
        log(f"  slice {sl:2d}: EN {r['en']} DIV {r['div']:8.4f} TOP {r['top']:5d} period {r['period_us']:8.1f} us"
            f"  A {r['a_us']:7.1f} us  B {r['b_us']:7.1f} us")
    return out


def tune_test(m, t, texts):
    m.mav.play_tune_send(m.target_system, m.target_component, TUNE.encode(), b"")
    seen = {}
    t_end = time.time() + 7
    while time.time() < t_end:
        r = slice_regs(t, 1)
        key = (r["en"], r["div"], r["top"], r["period_us"], r["a_us"], r["b_us"], funcsel(t, 2), funcsel(t, 3))
        seen[key] = seen.get(key, 0) + 1
        while True:
            msg = m.recv_match(type="STATUSTEXT", blocking=False)
            if not msg:
                break
            texts.append(msg.text)
    log("  slice 1 during the tune (EN, DIV, TOP, period us, A us, B us, GPIO2 fs, GPIO3 fs): samples")
    for k, n in sorted(seen.items(), key=lambda kv: -kv[1]):
        log(f"    {k}: {n}")
    return [list(k) + [n] for k, n in seen.items()]


def servo_raw(m):
    m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_REQUEST_MESSAGE, 0,
                            36, 0, 0, 0, 0, 0, 0)
    t0 = time.time()
    while time.time() - t0 < 3:
        r = m.recv_match(type="SERVO_OUTPUT_RAW", blocking=True, timeout=0.5)
        if r and r.port == 0:
            return {n: getattr(r, f"servo{n}_raw") for n in range(1, 11)}
    return None


def do_set_servo(m, chan, pwm):
    m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_DO_SET_SERVO, 0,
                            chan, pwm, 0, 0, 0, 0, 0)
    t0 = time.time()
    while time.time() - t0 < 3:
        a = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.5)
        if a and a.command == MAV.MAV_CMD_DO_SET_SERVO:
            log(f"  DO_SET_SERVO {chan} {pwm}: result {a.result}")
            return a.result
    log(f"  DO_SET_SERVO {chan} {pwm}: no ack")
    return None


def reboot(m):
    m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
                            0, 1, 0, 0, 0, 0, 0, 0)
    time.sleep(1)
    m.close()


def main():
    logging.basicConfig(level=logging.WARNING)
    op = sys.argv[1]
    outdir = os.path.dirname(os.path.abspath(__file__))
    if op == "params":
        m = connect()
        for k, v in get_params(m, sys.argv[2:]).items():
            print(k, v)
        return
    if op == "set":
        m = connect()
        set_params(m, [(a.split("=")[0], float(a.split("=")[1])) for a in sys.argv[2:]])
        return
    if op in ("put", "rm"):
        m = connect()
        f = MAVFTP(m, m.target_system, m.target_component)
        if op == "put":
            f.cmd_put([sys.argv[2], sys.argv[3]])
            r = f.process_ftp_reply("CreateFile", timeout=60)
        else:
            f.cmd_rm([sys.argv[2]])
            r = f.process_ftp_reply("RemoveFile", timeout=20)
        print(f"{op} error {r.error_code}")
        return
    if op != "case":
        sys.exit(__doc__)
    label = sys.argv[2]
    pairs = [(a.split("=")[0], float(a.split("=")[1])) for a in sys.argv[3:] if not a.startswith("servo:")]
    servos = [tuple(int(x) for x in a.split(":")[1:]) for a in sys.argv[3:] if a.startswith("servo:")]
    release_openocd()
    m = connect()
    if pairs:
        set_params(m, pairs)
    log(f"== {label}: rebooting")
    reboot(m)
    time.sleep(4)
    m = connect(90)
    texts = []
    pump(m, 15, texts)
    texts += banner(m)
    params = get_params(m, SHOW)
    log(f"  params {params}")
    for tx in texts:
        if tx.startswith(("RCOut", "buzz", "NeoPixel", "Scripting", "Lua", "RP2350", "PreArm: Board", "Config")) \
                or "buzzer" in tx or "failed" in tx.lower() or "error" in tx.lower():
            log(f"  text: {tx}")
    start_openocd(os.path.join(outdir, f"openocd_{label}.log"))
    t = Tcl()
    static = swd_static(t)
    raw_before = servo_raw(m)
    log(f"  SERVO_OUTPUT_RAW before: {raw_before}")
    tune = tune_test(m, t, texts)
    after = None
    if servos:
        for chan, pwm in servos:
            do_set_servo(m, chan, pwm)
        time.sleep(1)
        log(f"  SERVO_OUTPUT_RAW after: {servo_raw(m)}")
        after = swd_static(t)
        log("  tune again after DO_SET_SERVO")
        tune_test(m, t, texts)
    t.s.close()
    release_openocd()
    json.dump({"label": label, "params": params, "texts": texts, "static": static, "tune": tune,
               "raw_before": raw_before, "after_servo": after},
              open(os.path.join(outdir, f"case_{label}.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
