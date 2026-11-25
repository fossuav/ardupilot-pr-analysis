#!/usr/bin/env python3
"""One table over all runs: core busy by PCSR, scheduler load, XIP, Plane code and EKF3 shares.

Usage: summary.py ELF MAP RUNDIR...
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripting_profile"))
import attrib  # noqa: E402

elf, mapf, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]
syms = attrib.load_syms(elf)
sstarts = [s[0] for s in syms]
ents = attrib.load_map(mapf)
estarts = [e[0] for e in ents]


def busy(path):
    tot = idle = xip = plane = ekf = ctl = 0
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            a = int(line.split()[0], 16) & ~1
        except ValueError:
            continue
        tot += 1
        s = attrib.lookup(syms, sstarts, a)
        fn = s[2] if s else ""
        if fn in attrib.IDLE:
            idle += 1
            continue
        xip += attrib.region(a) == "xip"
        e = attrib.lookup(ents, estarts, a)
        obj = e[2] if e else ""
        plane += "ArduPlane" in obj or fn.startswith(("Plane::", "Mode")) and "Plane" in obj
        ekf += "NavEKF3" in obj
        ctl += any(k in obj for k in ("AP_RollController", "AP_PitchController", "AP_YawController",
                                       "AP_FW_Controller", "AP_SteerController"))
    b = tot - idle
    return 100.0 * b / tot, 100.0 * xip / max(b, 1), 100.0 * ekf / tot, 100.0 * ctl / tot


print(f"{'run':16s} {'c0 busy':>7s} {'xip%':>5s} {'EKF3':>5s} {'FWctl':>5s} {'c1 busy':>7s} "
      f"{'sched load':>10s} {'XIP hit':>7s} {'miss M/s':>8s}")
for d in dirs:
    for tag in ("dis_man", "arm_man", "arm_fbwa"):
        snap = os.path.join(d, f"{tag}_snap.json")
        if not os.path.exists(snap):
            continue
        j = json.load(open(snap))
        c0 = busy(os.path.join(d, f"{tag}_c0.txt"))
        c1 = busy(os.path.join(d, f"{tag}_c1.txt"))
        xip = open(os.path.join(d, f"{tag}_xip.txt")).read()
        hit = re.search(r"hit ([\d.]+)%", xip).group(1)
        miss = re.search(r"misses ([\d.]+) M/s", xip).group(1)
        print(f"{os.path.basename(d) + ' ' + tag:16s} {c0[0]:7.1f} {c0[1]:5.1f} {c0[2]:5.2f} {c0[3]:5.2f} "
              f"{c1[0]:7.1f} {j['load_mean']:10.1f} {hit:>7s} {miss:>8s}")
