#!/usr/bin/env python3
"""QuadPlane bench summary: core busy by PCSR, VTOL rate path share, scheduler load, XIP.

Usage: qp_summary.py ELF MAP RUNDIR...        one table over every condition in each RUNDIR
       qp_summary.py --top N ELF MAP RUNDIR/TAG_c0.txt ...   the top N functions in sample files
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripting_profile"))
import attrib  # noqa: E402

TAGS = ("dis_qs", "arm_qs", "arm_qh", "arm_ql", "arm_fbwa")
# the VTOL rate path: what rate_controller_run() and motors->output() reach, whichever thread runs them
RATE_PATH = ("AC_AttitudeControl", "AC_PID", "AP_Motors", "Thrust_Linearization", "rate_controller",
             "rate_thread", "FastRateBuffer", "get_next_gyro_sample", "SRV_Channel", "RCOutput")

top = None
args = sys.argv[1:]
if args[0] == "--top":
    top = int(args[1])
    args = args[2:]
elf, mapf, paths = args[0], args[1], args[2:]
syms = attrib.load_syms(elf)
sstarts = [s[0] for s in syms]


def samples(path):
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            yield int(line.split()[0], 16) & ~1
        except ValueError:
            continue


def busy(path):
    tot = idle = xip = rate = 0
    for a in samples(path):
        tot += 1
        s = attrib.lookup(syms, sstarts, a)
        fn = s[2] if s else ""
        if fn in attrib.IDLE:
            idle += 1
            continue
        xip += attrib.region(a) == "xip"
        rate += any(k in fn for k in RATE_PATH)
    b = tot - idle
    return 100.0 * b / tot, 100.0 * xip / max(b, 1), 100.0 * rate / tot


if top:
    for p in paths:
        c = collections.Counter()
        n = 0
        for a in samples(p):
            n += 1
            s = attrib.lookup(syms, sstarts, a)
            c[(s[2] if s else hex(a)) + (" [xip]" if attrib.region(a) == "xip" else "")] += 1
        print(f"== {p} ({n} samples)")
        for fn, k in c.most_common(top):
            print(f"  {100.0 * k / n:6.2f}%  {fn}")
    sys.exit(0)

print(f"{'run':14s} {'c0 busy':>7s} {'xip%':>5s} {'c0 rate':>7s} {'c1 busy':>7s} {'c1 rate':>7s} "
      f"{'sched':>6s} {'XIP hit':>7s} {'miss M/s':>8s} {'free':>7s}")
for d in paths:
    for tag in TAGS:
        snap = os.path.join(d, f"{tag}_snap.json")
        if not os.path.exists(snap):
            continue
        j = json.load(open(snap))
        c0 = busy(os.path.join(d, f"{tag}_c0.txt"))
        c1 = busy(os.path.join(d, f"{tag}_c1.txt"))
        xip = open(os.path.join(d, f"{tag}_xip.txt")).read()
        hit = re.search(r"hit ([\d.]+)%", xip)
        miss = re.search(r"misses ([\d.]+) M/s", xip)
        print(f"{os.path.basename(d) + ' ' + tag:14s} {c0[0]:7.1f} {c0[1]:5.1f} {c0[2]:7.2f} {c1[0]:7.1f} "
              f"{c1[2]:7.2f} {j['load_mean']:6.1f} {hit.group(1) if hit else '-':>7s} "
              f"{miss.group(1) if miss else '-':>8s} {j['free_min']:>7}")
