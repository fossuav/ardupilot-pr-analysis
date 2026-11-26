#!/usr/bin/env python3
"""QuadPlane rate thread bench on RPI_UAVFC: one boot per configuration, then session.py.

Usage: qp_bench.py OUTDIR FWDIR CONFIG...
  CONFIG = TAG:NAME=VALUE,NAME=VALUE...   e.g. A:Q_FSTRATE_ENABLE=0,SCHED_LOOP_RATE=300
Per configuration: release OpenOCD, set the parameters and reboot (qp_params.py), wait for
the boot to settle, start OpenOCD, check both cores run and the flash matches FWDIR/arduplane.bin,
run session.py (FAKE_GPS=1) with CONDS, release OpenOCD. The bridge must be running.
"""
import os
import subprocess
import sys
import time

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plane_profile")
sys.path.insert(0, TOOLS)
import ab  # noqa: E402  start_openocd(), release_openocd()

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.expanduser("~/venv-ardupilot/bin/python")
CONDS = os.environ.get("CONDS", "dis_qs:disarmed:17:30000 arm_qs:armed:17:30000 arm_qh:armed:18:30000 "
                       "arm_ql:armed:19:30000 arm_fbwa:armed:5:30000").split()

out, fw, configs = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(out, exist_ok=True)
for cfg in configs:
    tag, params = cfg.split(":", 1)
    rdir = os.path.join(out, tag)
    os.makedirs(rdir, exist_ok=True)
    ab.log(f"=== {tag}: {params}")
    ab.release_openocd()
    r = subprocess.run(["timeout", "180", PY, os.path.join(HERE, "qp_params.py"), "--reboot", *params.split(",")],
                       stdout=open(f"{rdir}/params.log", "w"), stderr=subprocess.STDOUT)
    if r.returncode != 0:
        sys.exit(f"{tag}: parameters or reboot failed, see {rdir}/params.log")
    time.sleep(20)
    ab.start_openocd(f"{rdir}/openocd.log")
    chk = subprocess.run([sys.executable, os.path.join(TOOLS, "tcl.py"), "dhcsr"], capture_output=True, text=True)
    ver = subprocess.run([sys.executable, os.path.join(TOOLS, "tcl.py"), "verify", f"{fw}/arduplane.bin",
                          "0x10020000"], capture_output=True, text=True)
    open(f"{rdir}/check.txt", "w").write(chk.stdout + ver.stdout)
    if "halted=1" in chk.stdout or "lockup=1" in chk.stdout or "flash matches the image" not in ver.stdout:
        ab.release_openocd()
        sys.exit(f"{tag}: core halted or flash does not match; see {rdir}/check.txt")
    ab.log("cores running, flash matches")
    env = dict(os.environ, FAKE_GPS="1", EKF_WAIT="40")
    s = subprocess.run(["timeout", "900", PY, os.path.join(TOOLS, "session.py"), rdir, *CONDS],
                       env=env, stdout=open(f"{rdir}/session.log", "w"), stderr=subprocess.STDOUT)
    ab.release_openocd()
    tail = open(f"{rdir}/session.log").read().splitlines()
    ab.log(f"session exit {s.returncode}; {[t for t in tail if t.startswith('final')]}")
    if s.returncode != 0:
        sys.exit(f"{tag}: session failed, see {rdir}/session.log")
ab.log("done")
