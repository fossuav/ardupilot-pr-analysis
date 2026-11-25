#!/usr/bin/env python3
"""Summarise an ab.py run: per boot and condition, core0 busy, where its busy time ran,
the Plane-only code's share, scheduler load and the FAST task costs.

Usage: abana.py ABDIR RUNDIR REPO
Each boot's samples are attributed with its own build's ELF and map.
"""
import collections
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripting_profile"))
import attrib  # noqa: E402

abdir, rundir, repo = sys.argv[1:4]
PLANE_LIBS = {"ArduPlane", "APM_Control", "AP_TECS", "AP_L1_Control", "AP_Landing", "AP_Soaring"}

where = collections.defaultdict(set)
for path in subprocess.run(["git", "-C", repo, "ls-files"], capture_output=True, text=True).stdout.split():
    parts = path.split("/")
    if parts[0] == "libraries" and len(parts) > 2:
        where[os.path.basename(path)].add(parts[1])
    elif parts[0] in ("ArduPlane", "ArduCopter", "Rover", "ArduSub", "Blimp", "AntennaTracker"):
        where[os.path.basename(path)].add(parts[0])


def lib_of(obj):
    libs = where.get(attrib.obj_source(obj), set())
    if "ArduPlane" in libs:
        return "ArduPlane"
    return next(iter(libs)) if len(libs) == 1 else "other"


cache = {}


def tables(letter):
    if letter not in cache:
        elf = f"{abdir}/{letter}/arduplane"
        syms = attrib.load_syms(elf)
        ents = attrib.load_map(f"{abdir}/{letter}/arduplane.map")
        cache[letter] = (syms, [s[0] for s in syms], ents, [e[0] for e in ents])
    return cache[letter]


def profile(path, letter):
    syms, ss, ents, es = tables(letter)
    tot = idle = xip = plane = plane_xip = veneer = 0
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
        fn = s[2] if s else ""
        if fn in attrib.IDLE:
            idle += 1
            continue
        x = attrib.region(a) == "xip"
        xip += x
        veneer += fn.endswith("_veneer")
        e = attrib.lookup(ents, es, a)
        if e and lib_of(e[2]) in PLANE_LIBS:
            plane += 1
            plane_xip += x
    b = tot - idle
    return {"busy": 100 * b / tot, "xip_of_busy": 100 * xip / max(b, 1), "plane": 100 * plane / tot,
            "plane_xip": 100 * plane_xip / tot, "veneer": 100 * veneer / tot}


def tasks(path):
    d = {}
    for line in open(path):
        m = re.match(r"(\S.*?)\s+MIN=\s*(\d+) MAX=\s*(\d+) AVG=\s*(\d+)", line)
        if m:
            d[m.group(1)] = (int(m.group(4)), int(m.group(3)))
    return d


rows = []
for rdir in sorted(glob.glob(f"{rundir}/run*")):
    run = os.path.basename(rdir)
    letter = run[-1]
    for cond in ("arm_man", "arm_fbwa"):
        snap = f"{rdir}/{cond}_snap.json"
        if not os.path.exists(snap):
            continue
        j = json.load(open(snap))
        p = profile(f"{rdir}/{cond}_c0.txt", letter)
        c1 = profile(f"{rdir}/{cond}_c1.txt", letter)["busy"]
        t = tasks(f"{rdir}/{cond}_tasks.txt")
        xip = open(f"{rdir}/{cond}_xip.txt").read()
        hit = float(re.search(r"hit ([\d.]+)%", xip).group(1))
        fast = sum(v[0] for k, v in t.items() if k.endswith("*"))
        rows.append(dict(run=run, letter=letter, cond=cond, load=j["load_mean"], c1=c1, hit=hit, fast=fast,
                         stab=t["Plane::stabilize*"][0], servos=t["Plane::set_servos*"][0],
                         ahrs=t["Plane::ahrs_update*"][0], ctl=t["Plane::update_control_mode*"][0],
                         free=j["free_min"], **p))

hdr = (f"{'run':8s} {'cond':8s} {'c0 busy':>7s} {'xip%':>5s} {'plane':>6s} {'pl xip':>6s} {'veneer':>6s} "
       f"{'c1':>5s} {'load':>5s} {'XIP hit':>7s} {'FAST us':>7s} {'stab':>5s} {'servos':>6s} {'ahrs':>5s} {'ctlmode':>7s} {'free':>7s}")
print(hdr)
for r in rows:
    print(f"{r['run']:8s} {r['cond']:8s} {r['busy']:7.1f} {r['xip_of_busy']:5.1f} {r['plane']:6.2f} {r['plane_xip']:6.2f} "
          f"{r['veneer']:6.2f} {r['c1']:5.1f} {r['load']:5.1f} {r['hit']:7.2f} {r['fast']:7d} {r['stab']:5d} "
          f"{r['servos']:6d} {r['ahrs']:5d} {r['ctl']:7d} {r['free']:7d}")
print()
for cond in ("arm_man", "arm_fbwa"):
    for k in ("busy", "plane", "load", "hit", "fast", "stab", "servos", "ahrs", "ctl", "free"):
        a = [r[k] for r in rows if r["cond"] == cond and r["letter"] == "A"]
        b = [r[k] for r in rows if r["cond"] == cond and r["letter"] == "B"]
        if a and b:
            ma, mb = sum(a) / len(a), sum(b) / len(b)
            print(f"{cond:8s} {k:7s} A {ma:9.2f} ({min(a):.2f}-{max(a):.2f})  B {mb:9.2f} ({min(b):.2f}-{max(b):.2f})  "
                  f"B-A {mb - ma:+.2f}")
