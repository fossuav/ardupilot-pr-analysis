#!/usr/bin/env python3
"""Run the #35358 A/B on the TBS_LUCID_H7 bench: flash, arm, sample the PC over J-Link without halting, alternating builds.

usage: h7_run.py flash TAG | sample OUTFILE N | SEQUENCE     e.g. ABBAABBA

Builds are H7_SCRATCH/<TAG>/arducopter.{elf,apj}. The MAVLink side is h7_session.py under Windows Python.
"""
import os
import re
import subprocess
import sys
import time

S = os.environ["H7_SCRATCH"]
REPO = os.environ["H7_REPO"]
TOOLS = os.environ["H7_TOOLS"]
BASE = os.environ["H7_BENCH"]
BASE_WIN = os.environ["H7_BENCH_WIN"]
JLINK = os.environ["H7_JLINK"]
SETTLE_S = 14
SAMPLES = 40000
SENTINEL = f"{BASE}/sampling_done"


def win(p):
    return subprocess.check_output(["wslpath", "-w", p], text=True).strip()


ENV = dict(os.environ, H7_BENCH_DIR=BASE_WIN, H7_TOOLS=win(TOOLS), WSLENV="H7_BENCH_DIR:H7_TOOLS")


def flash(tag, log):
    r = subprocess.run(["timeout", "300", "python.exe", win(f"{REPO}/Tools/scripts/uploader.py"), "--port", "COM29,COM27",
                        win(f"{S}/{tag}/arducopter.apj")], stdout=open(log, "wb"), stderr=subprocess.STDOUT)
    if r.returncode != 0:
        sys.exit(f"upload failed, see {log}")


def jlink(script_lines, name):
    path = f"{BASE}/{name}.jlink"
    with open(path, "w", newline="\r\n") as fh:
        fh.write("\n".join(["si SWD", "speed 4000", "device STM32H743VI", "connect"] + script_lines + ["exit"]) + "\n")
    out = subprocess.run(["timeout", "300", JLINK, "-NoGui", "1", "-ExitOnError", "1", "-CommandFile", f"{BASE_WIN}\\{name}.jlink"],
                         capture_output=True, text=True, errors="replace", cwd=BASE)
    return out.returncode, out.stdout


def sample(outfile, n):
    # DHCSR before and after: the core must not be halted, and C_DEBUGEN is cleared on the way out so a fault
    # handler's breakpoint cannot stop the core once the probe has gone
    t0 = time.time()
    rc, text = jlink(["mem32 E000EDF0 1"] + ["mem32 E000101C 1"] * n + ["mem32 E000EDF0 1", "w4 E000EDF0 A05F0000"],
                     "sample")
    dhcsr = re.findall(r"E000EDF0 = ([0-9A-F]{8})", text)
    pcs = re.findall(r"E000101C = ([0-9A-F]{8})", text)
    if rc != 0 or len(dhcsr) < 2 or len(pcs) != n:
        sys.exit(f"sampling failed: rc {rc}, {len(pcs)} samples\n{text[-600:]}")
    halted = [d for d in dhcsr if int(d, 16) & (1 << 17)]
    with open(outfile, "w") as fh:
        fh.write(f"# n={n} start={time.strftime('%H:%M:%S')} dhcsr={','.join(dhcsr)}\n")
        fh.write("\n".join(pcs) + "\n")
    print(f"  {n} samples in {time.time() - t0:.1f} s, DHCSR {', '.join(dhcsr)}{' HALTED' if halted else ''}",
          flush=True)
    if halted:
        sys.exit("core was halted during sampling")


def elf_hash(tag):
    text = subprocess.check_output(["strings", "-a", f"{S}/{tag}/arducopter.elf"], text=True, errors="replace")
    return re.search(r"ArduCopter V4\.8\.0-dev \(([0-9a-f]{8})\)", text).group(1)


def session(*args):
    return subprocess.Popen(["timeout", "600", "python.exe", "-u", f"{BASE_WIN}\\h7_session.py", *args],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=ENV, cwd=BASE)


def run_sequence(sequence):
    hashes = {t: elf_hash(t) for t in sorted(set(sequence))}
    print("builds:", hashes, flush=True)
    for i, tag in enumerate(sequence):
        run_id = f"run{i + 1}{tag}"
        outdir = f"{BASE}/{run_id}"
        os.makedirs(outdir, exist_ok=True)
        print(f"=== {run_id}: {hashes[tag]}", flush=True)
        flash(tag, f"{outdir}/upload.log")
        p = session("run", run_id, hashes[tag])
        sampled = False
        try:
            for line in p.stdout:
                line = line.strip()
                print("  " + line, flush=True)
                if line == "ARMED" and not sampled:
                    sampled = True
                    time.sleep(SETTLE_S)
                    try:
                        sample(f"{outdir}/pcsr.txt", SAMPLES)
                    finally:
                        open(SENTINEL, "w").close()
        finally:
            p.wait()
        if p.returncode != 0 or not sampled:
            sys.exit(f"{run_id} failed, session exit {p.returncode}")
    print("sequence done", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "flash":
        os.makedirs(f"{BASE}/flash_{sys.argv[2]}", exist_ok=True)
        flash(sys.argv[2], f"{BASE}/flash_{sys.argv[2]}/upload.log")
        print("flashed", sys.argv[2])
    elif sys.argv[1] == "sample":
        sample(sys.argv[2], int(sys.argv[3]))
    else:
        run_sequence(sys.argv[1])
