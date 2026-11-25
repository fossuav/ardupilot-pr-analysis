#!/usr/bin/env python3
"""A/B two Plane firmwares on the RPI_UAVFC flight board, one boot per letter of SEQUENCE.

Usage: ab.py SEQUENCE ABDIR OUTDIR      e.g. ab.py ABBA <scratch>/ab <scratch>/runs/ab
ABDIR/<letter>/ holds arduplane (ELF), arduplane.apj and arduplane.bin.
Per boot: stop the bridge and OpenOCD, flash with the uploader over COM32, start the
bridge, wait for the boot, start OpenOCD, check both cores run and the flash matches the
ELF, run session.py (FAKE_GPS=1) for armed MANUAL and armed FBWA at zero throttle, then
release OpenOCD (C_DEBUGEN cleared, shutdown). The board is left disarmed with the bridge
and OpenOCD stopped.
"""
import os
import socket
import subprocess
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(TOOLS, "..", "scripting_profile")
REPO = "/home/andy/github/ardupilot-rpi"
OOCD = "/opt/openocd-0.12.0+dev-x64-win"
PORT = "COM32"
PY = os.path.expanduser("~/venv-ardupilot/bin/python")
SEP = b"\x1a"


def win(path):
    return subprocess.check_output(["wslpath", "-w", path], text=True).strip()


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def stop_bridge():
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and "
          "$_.CommandLine -like '*bridge.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True)


def openocd_running():
    out = subprocess.run(["tasklist.exe"], capture_output=True, text=True).stdout.lower()
    return "openocd" in out


def tcl(sock, cmd):
    sock.sendall(cmd.encode() + SEP)
    buf = b""
    while not buf.endswith(SEP):
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    return buf[:-1].decode(errors="replace").strip()


def release_openocd():
    if not openocd_running():
        return
    subprocess.run([sys.executable, os.path.join(TOOLS, "tcl.py"), "release"], capture_output=True, timeout=30)
    for _ in range(40):
        if not openocd_running():
            return
        time.sleep(0.5)
    sys.exit("OpenOCD did not shut down; stopping before any reboot")


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


def main():
    seq, abdir, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    for i, letter in enumerate(seq):
        run = f"run{i + 1}{letter}"
        rdir = os.path.join(out, run)
        os.makedirs(rdir, exist_ok=True)
        fw = os.path.join(abdir, letter)
        log(f"=== {run}")
        release_openocd()
        stop_bridge()
        time.sleep(1)
        r = subprocess.run(["timeout", "240", "python.exe", win(f"{REPO}/Tools/scripts/uploader.py"), "--port", PORT,
                            win(f"{fw}/arduplane.apj")], stdout=open(f"{rdir}/upload.log", "wb"), stderr=subprocess.STDOUT)
        if r.returncode != 0:
            sys.exit(f"upload failed ({r.returncode}), see {rdir}/upload.log")
        log("flashed")
        subprocess.Popen(["python.exe", "-u", win(f"{PROFILE}/bridge.py"), PORT, "127.0.0.1", "5770"],
                         stdout=open(f"{rdir}/bridge.log", "w"), stderr=subprocess.STDOUT)
        time.sleep(25)
        start_openocd(f"{rdir}/openocd.log")
        chk = subprocess.run([sys.executable, os.path.join(TOOLS, "tcl.py"), "dhcsr"], capture_output=True, text=True)
        ver = subprocess.run([sys.executable, os.path.join(TOOLS, "tcl.py"), "verify", f"{fw}/arduplane.bin",
                              "0x10020000"], capture_output=True, text=True)
        open(f"{rdir}/check.txt", "w").write(chk.stdout + ver.stdout)
        if "halted=1" in chk.stdout or "lockup=1" in chk.stdout or "flash matches the image" not in ver.stdout:
            release_openocd()
            sys.exit(f"{run}: core halted or flash does not match {letter}; see {rdir}/check.txt")
        log("cores running, flash matches")
        env = dict(os.environ, FAKE_GPS="1", EKF_WAIT="120")
        s = subprocess.run(["timeout", "600", PY, os.path.join(TOOLS, "session.py"), rdir,
                            *os.environ.get("CONDS", "arm_man:armed:0:30000 arm_fbwa:armed:5:30000").split()],
                           env=env, stdout=open(f"{rdir}/session.log", "w"), stderr=subprocess.STDOUT)
        release_openocd()
        tail = open(f"{rdir}/session.log").read().splitlines()
        log(f"session exit {s.returncode}; {[l for l in tail if l.startswith('final')]}")
        if s.returncode != 0:
            stop_bridge()
            sys.exit(f"{run}: session failed, see {rdir}/session.log")
    stop_bridge()
    log("done")


if __name__ == "__main__":
    main()
