#!/usr/bin/env python3
"""PCSR samples by library and memory region, and the hottest functions running from XIP flash.

Usage: libgroup.py ELF MAP REPO SAMPLES [--top N]
Library = the directory under libraries/, the vehicle directory, ChibiOS, or the toolchain
archive the sample's object came from (source basename looked up in REPO's git ls-files).
"""
import bisect
import collections
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripting_profile"))
import attrib  # noqa: E402

elf, mapf, repo, samples = sys.argv[1:5]
top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 25

where = collections.defaultdict(set)
for path in subprocess.run(["git", "-C", repo, "ls-files"], capture_output=True, text=True).stdout.split():
    parts = path.split("/")
    if parts[0] == "libraries" and len(parts) > 2:
        lib = parts[1]
    elif parts[0] in ("ArduPlane", "ArduCopter", "Rover", "ArduSub", "Blimp", "AntennaTracker"):
        lib = parts[0]
    else:
        lib = "/".join(parts[:2])
    where[os.path.basename(path)].add(lib)


def library(obj, src, fn):
    if fn in attrib.IDLE:
        return "idle"
    if "libch.a" in obj or "ChibiOS" in obj:
        return "ChibiOS"
    m = re.search(r"/(libc|libm|libgcc|libstdc\+\+)\.a\(", obj)
    if m:
        return m.group(1)
    if "picolibc" in obj:
        return "picolibc"
    libs = where.get(src)
    if libs and len(libs) == 1:
        return next(iter(libs))
    if libs:
        # a basename shared by several trees: this is a ChibiOS Plane build
        for pref in ("AP_HAL_ChibiOS", "ArduPlane", "AP_HAL", "GCS_MAVLink", "AP_Vehicle"):
            if pref in libs:
                return pref
        return "|".join(sorted(libs))[:40]
    return "?" + src[:30]


ents = attrib.load_map(mapf)
estarts = [e[0] for e in ents]
syms = attrib.load_syms(elf)
sstarts = [s[0] for s in syms]

bylib = collections.Counter()
bylib_xip = collections.Counter()
xipfn = collections.Counter()
fnlib = {}
total = busy = 0
for line in open(samples):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    try:
        a = int(line.split()[0], 16) & ~1
    except ValueError:
        continue
    total += 1
    s = attrib.lookup(syms, sstarts, a)
    e = attrib.lookup(ents, estarts, a)
    fn = s[2] if s else f"?{a:08x}"
    obj = e[2] if e else "?"
    src = attrib.obj_source(obj)
    lib = library(obj, src, fn)
    if lib == "idle":
        continue
    busy += 1
    bylib[lib] += 1
    if attrib.region(a) == "xip":
        bylib_xip[lib] += 1
        xipfn[fn] += 1
        fnlib[fn] = lib

print(f"{os.path.basename(samples)}: {total} samples, busy {100.0 * busy / total:.1f}%, "
      f"of busy in XIP {100.0 * sum(bylib_xip.values()) / max(busy, 1):.1f}%")
print(f"{'library':28s} {'% all':>7s} {'% busy':>7s} {'xip % all':>9s}")
for lib, c in bylib.most_common(22):
    print(f"{lib:28s} {100.0 * c / total:7.2f} {100.0 * c / busy:7.2f} {100.0 * bylib_xip[lib] / total:9.2f}")
print(f"top {top} functions in XIP flash (% of all samples):")
for fn, c in xipfn.most_common(top):
    print(f"  {100.0 * c / total:5.2f}  {fnlib[fn][:18]:18s} {fn[:90]}")
