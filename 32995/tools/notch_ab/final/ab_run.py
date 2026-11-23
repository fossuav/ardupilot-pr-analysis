#!/usr/bin/env python3
"""Run the notch A/B: flash, arm, sample both cores over SWD without halting, in alternating boots.

usage: ab_run.py SEQUENCE     e.g. ABBAAB
"""
# Paths come from NOTCH_AB_* environment variables (pass them with WSLENV to Windows Python).
import os
import re
import socket
import subprocess
import sys
import time

S = os.environ["NOTCH_AB_SCRATCH"]
AB = f"{S}/notch-ab-final"
BASE = os.environ["NOTCH_AB_DATA"]
BASE_WIN = os.environ["NOTCH_AB_DATA_WIN"]
REPO = os.environ["NOTCH_AB_REPO"]
OOCD = "/opt/openocd-0.12.0+dev-x64-win"
PCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripting_profile", "pcs.py")
SEP = b"\x1a"
DHCSR = 0xE000EDF0
SETTLE_S = 14
SAMPLES = {1: 40000, 0: 25000}


def win(p):
    return subprocess.check_output(["wslpath", "-w", p], text=True).strip()


def tcl(sock, cmd):
    sock.sendall(cmd.encode() + SEP)
    buf = b""
    while not buf.endswith(SEP):
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    return buf[:-1].decode(errors="replace").strip()


def flash(tag, log):
    r = subprocess.run(["timeout", "240", "python.exe", win(f"{REPO}/Tools/scripts/uploader.py"), "--port", "COM15",
                        win(f"{AB}/{tag}/arducopter.apj")], stdout=open(log, "wb"), stderr=subprocess.STDOUT)
    if r.returncode != 0:
        sys.exit(f"upload failed, see {log}")


def sample(run_id):
    outdir = f"{BASE}/{run_id}"
    logf = open(f"{outdir}/openocd.log", "w")
    scripts = win(f"{OOCD}/scripts")
    proc = subprocess.Popen(["./openocd.exe", "-s", scripts, "-f", "interface/cmsis-dap.cfg", "-f", "target/rp2350.cfg",
                             "-c", "gdb port 50000", "-c", "tcl port 50001", "-c", "telnet port 50002",
                             "-c", "adapter speed 5000"], cwd=OOCD, stdout=logf, stderr=subprocess.STDOUT)
    sock = None
    try:
        deadline = time.time() + 15
        while time.time() < deadline and proc.poll() is None:
            try:
                sock = socket.create_connection(("127.0.0.1", 50001), timeout=5)
                break
            except OSError:
                time.sleep(0.2)
        if sock is None:
            raise RuntimeError("OpenOCD did not open its TCL port")
        sock.settimeout(15)
        time.sleep(0.5)
        for core in (0, 1):
            v = int(tcl(sock, f"rp2350.cm{core} read_memory {DHCSR:#x} 32 1").split()[0], 16)
            if (v >> 17) & 1 or (v >> 19) & 1:
                raise RuntimeError(f"core{core} halted or locked up: DHCSR {v:#x}")
        for core, n in SAMPLES.items():
            out = subprocess.run(["python.exe", "-u", win(PCS), str(core), str(n), f"{BASE_WIN}\\{run_id}\\pcsr{core}.txt"],
                                 capture_output=True, text=True, timeout=120)
            print("  " + out.stdout.strip().split("->")[0], flush=True)
    finally:
        if sock is not None:
            tcl(sock, "poll off")
            for core in (0, 1):
                tcl(sock, f"rp2350.cm{core} write_memory {DHCSR:#x} 32 {{0xA05F0000}}")
            try:
                sock.sendall(b"shutdown" + SEP)
            except OSError:
                pass
            sock.close()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill.exe", "/IM", "openocd.exe", "/F"], capture_output=True)
            print("  OpenOCD had to be killed", flush=True)
        logf.close()


sequence = sys.argv[1]
hashes = {}
for tag in sorted(set(sequence)):
    text = subprocess.check_output(["strings", "-a", f"{AB}/{tag}/arducopter.elf"], text=True, errors="replace")
    hashes[tag] = re.search(r"ArduCopter V4\.8\.0-dev \(([0-9a-f]{8})\)", text).group(1)
print("builds:", hashes, flush=True)

for i, tag in enumerate(sequence):
    run_id = f"run{i + 1}{tag}"
    os.makedirs(f"{BASE}/{run_id}", exist_ok=True)
    print(f"=== {run_id}: {hashes[tag]}", flush=True)
    flash(tag, f"{BASE}/{run_id}/upload.log")
    p = subprocess.Popen(["timeout", "560", "python.exe", "-u", win(f"{AB}/ab_session.py"), "run", run_id, hashes[tag]],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sampled = False
    try:
        for line in p.stdout:
            line = line.strip()
            if "WARNING" not in line:
                print("  " + line, flush=True)
            if line == "ARMED" and not sampled:
                sampled = True
                time.sleep(SETTLE_S)
                try:
                    sample(run_id)
                finally:
                    open(f"{BASE}/sampling_done", "w").close()
    finally:
        p.wait()
    if p.returncode != 0 or not sampled:
        sys.exit(f"{run_id} failed, session exit {p.returncode}")
print("ab_run done", flush=True)
