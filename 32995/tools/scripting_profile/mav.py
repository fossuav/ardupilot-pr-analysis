#!/usr/bin/env python3
"""RPI_UAVFC bench MAVLink tool, reached through bridge.py (run with ~/venv-ardupilot/bin/python).

  mav.py get NAME...              print parameters
  mav.py set NAME=VALUE...        set parameters and read them back
  mav.py put LOCAL REMOTE         MAVLink FTP upload
  mav.py fetch REMOTE LOCAL       MAVLink FTP download
  mav.py snap OUTDIR TAG [SECS]   SYS_STATUS load, MEMINFO, STATUSTEXT for SECS, then threads.txt and tasks.txt
  mav.py window OUTDIR TAG SECS   read threads.txt first (zeroes the thread statistics), then snap
  mav.py mode N                   set the custom flight mode
  mav.py scripting stop|restart   MAV_CMD_SCRIPTING
  mav.py arm|disarm               forced
  mav.py reboot
  mav.py watch SECS               print STATUSTEXT and the armed state
"""
import json
import logging
import os
import sys
import time

from pymavlink import mavutil
from pymavlink.mavftp import MAVFTP

PORT = 5770
MAV = mavutil.mavlink
FORCE = 21196


def connect():
    m = mavutil.mavlink_connection(f"tcpin:0.0.0.0:{PORT}", source_system=255, source_component=190)
    t0 = time.time()
    while time.time() - t0 < 30:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb and hb.type != MAV.MAV_TYPE_GCS and hb.autopilot == MAV.MAV_AUTOPILOT_ARDUPILOTMEGA:
            m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
            return m
    sys.exit("no heartbeat from the board")


def param_get(m, name):
    for _ in range(4):
        m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
        t0 = time.time()
        while time.time() - t0 < 1.5:
            p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
            if p is not None and p.param_id == name:
                return p.param_value
    return None


def param_set(m, name, value):
    for _ in range(4):
        m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value),
                             MAV.MAV_PARAM_TYPE_REAL32)
        t0 = time.time()
        while time.time() - t0 < 1.5:
            p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
            if p is not None and p.param_id == name:
                return p.param_value
    return None


def command(m, cmd, *params):
    p = list(params) + [0] * (7 - len(params))
    for _ in range(3):
        m.mav.command_long_send(m.target_system, m.target_component, cmd, 0, *p)
        t0 = time.time()
        while time.time() - t0 < 3:
            a = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.5)
            if a is not None and a.command == cmd:
                return a.result
    return None


def ftp(m, op, a, b):
    logging.basicConfig(level=logging.WARNING)
    f = MAVFTP(m, m.target_system, m.target_component)
    if op == "get":
        f.cmd_get([a, b])
    else:
        f.cmd_put([a, b])
    ret = f.process_ftp_reply(op, timeout=60)
    return ret.error_code == 0, ret


def set_intervals(m):
    # the same telemetry in every condition: SYS_STATUS and MEMINFO at 2 Hz
    for msg_id in (MAV.MAVLINK_MSG_ID_SYS_STATUS, MAV.MAVLINK_MSG_ID_MEMINFO):
        command(m, MAV.MAV_CMD_SET_MESSAGE_INTERVAL, msg_id, 500000)


def snap(m, outdir, tag, secs):
    os.makedirs(outdir, exist_ok=True)
    set_intervals(m)
    loads, free, texts, armed, mode = [], [], [], None, None
    t0 = time.time()
    while time.time() - t0 < secs:
        msg = m.recv_match(type=["SYS_STATUS", "MEMINFO", "STATUSTEXT", "HEARTBEAT"], blocking=True, timeout=1)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "SYS_STATUS":
            loads.append(msg.load / 10.0)
        elif t == "MEMINFO":
            free.append(getattr(msg, "freemem32", 0) or msg.freemem)
        elif t == "STATUSTEXT":
            texts.append(msg.text)
        elif t == "HEARTBEAT" and msg.get_srcSystem() == m.target_system:
            armed = bool(msg.base_mode & MAV.MAV_MODE_FLAG_SAFETY_ARMED)
            mode = msg.custom_mode
    res = {"tag": tag, "time": time.strftime("%H:%M:%S"), "armed": armed, "mode": mode, "secs": secs,
           "sched_load_pct": {"n": len(loads), "mean": sum(loads) / len(loads) if loads else None,
                              "max": max(loads) if loads else None},
           "freemem32": {"n": len(free), "min": min(free) if free else None,
                         "mean": sum(free) / len(free) if free else None},
           "statustext": texts}
    for name in ("threads.txt", "tasks.txt"):
        ok, _ = ftp(m, "get", f"@SYS/{name}", os.path.join(outdir, f"{tag}_{name}"))
        res[name] = ok
    with open(os.path.join(outdir, f"{tag}_snap.json"), "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "statustext"}))
    for t in texts:
        print("  text:", t)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    op, args = sys.argv[1], sys.argv[2:]
    m = connect()
    if op == "get":
        for n in args:
            print(n, param_get(m, n))
    elif op == "set":
        for a in args:
            n, v = a.split("=", 1)
            got = param_set(m, n, float(v))
            print(n, "->", got, "" if got is not None and abs(got - float(v)) < 1e-6 else "MISMATCH")
    elif op in ("put", "fetch"):
        ok, ret = ftp(m, "put" if op == "put" else "get", args[0], args[1])
        print(op, "ok" if ok else f"failed {ret}")
    elif op == "rm":
        logging.basicConfig(level=logging.WARNING)
        f = MAVFTP(m, m.target_system, m.target_component)
        f.cmd_rm([args[0]])
        print("rm sent; reply", f.process_ftp_reply("RemoveFile", timeout=10).error_code)
    elif op == "window":
        ftp(m, "get", "@SYS/threads.txt", os.path.join(args[0], f"{args[1]}_prime.txt"))
        snap(m, args[0], args[1], float(args[2]))
    elif op == "mode":
        print("mode result", command(m, MAV.MAV_CMD_DO_SET_MODE, MAV.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, int(args[0])))
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=3)
        print("custom_mode now", hb.custom_mode if hb else None)
    elif op == "snap":
        snap(m, args[0], args[1], float(args[2]) if len(args) > 2 else 20)
    elif op == "scripting":
        cmd = {"stop": MAV.SCRIPTING_CMD_STOP, "restart": MAV.SCRIPTING_CMD_STOP_AND_RESTART}[args[0]]
        print("scripting", args[0], "result", command(m, MAV.MAV_CMD_SCRIPTING, cmd))
    elif op in ("arm", "disarm"):
        print(op, "result", command(m, MAV.MAV_CMD_COMPONENT_ARM_DISARM, 1 if op == "arm" else 0, FORCE))
    elif op == "reboot":
        print("reboot result", command(m, MAV.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, 1))
    elif op == "watch":
        t0 = time.time()
        while time.time() - t0 < float(args[0]):
            msg = m.recv_match(type=["STATUSTEXT", "HEARTBEAT"], blocking=True, timeout=1)
            if msg is None:
                continue
            if msg.get_type() == "STATUSTEXT":
                print(f"{time.time() - t0:6.1f} {msg.text}")
            elif msg.get_srcSystem() == m.target_system and int(time.time() - t0) % 10 == 0:
                print(f"{time.time() - t0:6.1f} armed={bool(msg.base_mode & MAV.MAV_MODE_FLAG_SAFETY_ARMED)}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
