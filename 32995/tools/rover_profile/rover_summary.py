#!/usr/bin/env python3
"""One table over Rover runs: core busy by PCSR, where core0's busy time runs, scheduler load, XIP.

Usage: rover_summary.py ELF MAP RUNDIR...
Columns are percent of all core0 samples, except xip%, which is the share of core0's busy
samples that ran from XIP flash. rover = Rover/ objects; ar = the AR_* controllers and motors
(AR_AttitudeControl, AR_PosControl, AR_WPNav, AR_Motors, AR_PivotTurn); ekf = AP_NavEKF3.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attrib  # noqa: E402

elf, mapf, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]
syms = attrib.load_syms(elf)
sstarts = [s[0] for s in syms]
ents = attrib.load_map(mapf)
estarts = [e[0] for e in ents]
AR = ("AR_AttitudeControl", "AR_PosControl", "AR_WPNav", "AR_Motors", "AR_PivotTurn", "AP_MotorsUGV")
TAGS = ("dis_man", "arm_man", "arm_acro", "arm_hold", "arm_loiter", "arm_auto")


def busy(path):
    tot = idle = xip = rover = rover_xip = ar = ekf = 0
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
        x = attrib.region(a) == "xip"
        xip += x
        e = attrib.lookup(ents, estarts, a)
        obj = e[2] if e else ""
        if obj.startswith("Rover/") or "/Rover/" in obj:
            rover += 1
            rover_xip += x
        ar += any(k in obj for k in AR)
        ekf += "NavEKF3" in obj
    b = tot - idle
    pct = 100.0 / max(tot, 1)
    return {"busy": b * pct, "xip": 100.0 * xip / max(b, 1), "rover": rover * pct, "rover_xip": rover_xip * pct,
            "ar": ar * pct, "ekf": ekf * pct}


print(f"{'run':18s} {'c0 busy':>7s} {'xip%':>5s} {'rover':>6s} {'(xip)':>6s} {'AR_*':>5s} {'EKF3':>5s} "
      f"{'c1 busy':>7s} {'load':>5s} {'XIP hit':>7s} {'miss M/s':>8s} {'free':>7s} {'S3 max':>6s}")
for d in dirs:
    for tag in TAGS:
        snap = os.path.join(d, f"{tag}_snap.json")
        if not os.path.exists(snap):
            continue
        j = json.load(open(snap))
        c0 = busy(os.path.join(d, f"{tag}_c0.txt"))
        c1 = busy(os.path.join(d, f"{tag}_c1.txt"))
        xip = open(os.path.join(d, f"{tag}_xip.txt")).read()
        hit = re.search(r"hit ([\d.]+)%", xip).group(1)
        miss = re.search(r"misses ([\d.]+) M/s", xip).group(1)
        s3 = j.get("s3_range") or [0, 0]
        print(f"{os.path.basename(d) + ' ' + tag:18s} {c0['busy']:7.1f} {c0['xip']:5.1f} {c0['rover']:6.2f} "
              f"{c0['rover_xip']:6.2f} {c0['ar']:5.2f} {c0['ekf']:5.2f} {c1['busy']:7.1f} {j['load_mean'] or 0:5.1f} "
              f"{hit:>7s} {miss:>8s} {j['free_min'] or 0:7d} {s3[1]:6d}")
