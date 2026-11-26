#!/usr/bin/env python3
"""Summarise a rover_ab.py run: per boot and condition, core0 busy, its XIP share, core1, the
scheduler load, the costliest tasks and free memory, then A against B per condition.

Usage: rover_abana.py ABDIR RUNDIR      each boot's samples use its own letter's ELF and map
"""
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attrib  # noqa: E402

abdir, rundir = sys.argv[1:3]
CONDS = os.environ.get("CONDS", "arm_man arm_acro arm_auto").split()
cache = {}


def tables(letter):
    if letter not in cache:
        syms = attrib.load_syms(f"{abdir}/{letter}/ardurover")
        cache[letter] = (syms, [s[0] for s in syms])
    return cache[letter]


def busy(path, letter):
    syms, ss = tables(letter)
    tot = idle = xip = 0
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            a = int(line.split()[0], 16) & ~1
        except ValueError:
            continue
        tot += 1
        s = attrib.lookup(syms, ss, a)
        if s and s[2] in attrib.IDLE:
            idle += 1
            continue
        xip += attrib.region(a) == "xip"
    return 100.0 * (tot - idle) / tot, 100.0 * xip / tot


def task(path, name):
    for line in open(path):
        m = re.match(re.escape(name) + r"\s+MIN=\s*\d+ MAX=\s*(\d+) AVG=\s*(\d+)", line)
        if m:
            return int(m.group(2))
    return 0


rows = []
for rdir in sorted(glob.glob(f"{rundir}/run*")):
    letter = rdir[-1]
    for cond in CONDS:
        snap = f"{rdir}/{cond}_snap.json"
        if not os.path.exists(snap):
            continue
        j = json.load(open(snap))
        c0, c0x = busy(f"{rdir}/{cond}_c0.txt", letter)
        c1, _ = busy(f"{rdir}/{cond}_c1.txt", letter)
        hit = float(re.search(r"hit ([\d.]+)%", open(f"{rdir}/{cond}_xip.txt").read()).group(1))
        t = f"{rdir}/{cond}_tasks.txt"
        rows.append(dict(run=os.path.basename(rdir), letter=letter, cond=cond, c0=c0, c0x=c0x, c1=c1,
                         load=j["load_mean"], hit=hit, free=j["free_min"], ahrs=task(t, "Rover::ahrs_update"),
                         mode=task(t, "Rover::update_current_mode"), servos=task(t, "Rover::set_servos")))
print(f"{'run':8s} {'cond':10s} {'c0 busy':>7s} {'c0 xip':>6s} {'c1':>5s} {'load':>5s} {'XIP hit':>7s} "
      f"{'ahrs us':>7s} {'mode us':>7s} {'servo us':>8s} {'free':>7s}")
for r in rows:
    print(f"{r['run']:8s} {r['cond']:10s} {r['c0']:7.1f} {r['c0x']:6.1f} {r['c1']:5.1f} {r['load']:5.1f} {r['hit']:7.2f} "
          f"{r['ahrs']:7d} {r['mode']:7d} {r['servos']:8d} {r['free']:7d}")
print()
for cond in CONDS:
    for k in ("c0", "c0x", "c1", "load", "hit", "ahrs", "mode", "free"):
        a = [r[k] for r in rows if r["cond"] == cond and r["letter"] == "A"]
        b = [r[k] for r in rows if r["cond"] == cond and r["letter"] == "B"]
        if a and b:
            ma, mb = sum(a) / len(a), sum(b) / len(b)
            print(f"{cond:10s} {k:5s} A {ma:9.2f} ({min(a):.2f}-{max(a):.2f})  B {mb:9.2f} ({min(b):.2f}-{max(b):.2f})  "
                  f"B-A {mb - ma:+.2f}")
