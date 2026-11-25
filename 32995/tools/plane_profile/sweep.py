#!/usr/bin/env python3
"""Plane hot-path sweep: static call trees of the per-loop tasks, restricted to Plane-only
code, ranked by core0 XIP samples.

Usage: sweep.py ELF MAP REPO OUT_JSON SAMPLES...
Roots are Plane's FAST tasks and its 50 Hz control tasks. Calls are followed through
bl/b.w/b and veneers; the tree is cut at any function outside Plane-only code (ArduPlane
and the libraries only Plane links), which stays where it is.
"""
import collections
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripting_profile"))
import attrib  # noqa: E402

elf, mapf, repo, out_json = sys.argv[1:5]
sample_files = sys.argv[5:]

PLANE_LIBS = {"ArduPlane", "APM_Control", "AP_TECS", "AP_L1_Control", "AP_Landing", "AP_Soaring"}
ROOTS = ["Plane::ahrs_update", "Plane::update_control_mode", "Plane::stabilize", "Plane::set_servos",
         "Plane::read_radio", "Plane::update_speed_height", "Plane::check_short_rc_failsafe",
         "Plane::Log_Write_FullRate", "Plane::update_throttle_hover",
         # the navigation tasks
         "Plane::navigate", "Plane::update_alt", "Plane::calc_airspeed_errors", "Plane::adjust_altitude_target",
         "Plane::update_GPS_50Hz", "Plane::update_GPS_10Hz", "Plane::ekf_check", "Plane::update_logging10",
         "Plane::update_logging25", "Plane::update_is_flying_5Hz"]

# basename -> library, as libgroup.py does it
where = collections.defaultdict(set)
for path in subprocess.run(["git", "-C", repo, "ls-files"], capture_output=True, text=True).stdout.split():
    parts = path.split("/")
    if parts[0] == "libraries" and len(parts) > 2:
        where[os.path.basename(path)].add(parts[1])
    elif parts[0] in ("ArduPlane", "ArduCopter", "Rover", "ArduSub", "Blimp", "AntennaTracker"):
        where[os.path.basename(path)].add(parts[0])


def library(src):
    libs = where.get(src, set())
    if "ArduPlane" in libs:
        return "ArduPlane"
    if len(libs) == 1:
        return next(iter(libs))
    return "|".join(sorted(libs)) or "?"


syms = attrib.load_syms(elf)              # (start, end, demangled) for T/t/W/w with size
sstarts = [s[0] for s in syms]
ents = attrib.load_map(mapf)
estarts = [e[0] for e in ents]

info = {}
for a, b, name in syms:
    e = attrib.lookup(ents, estarts, a)
    obj = e[2] if e else ""
    info[a] = {"name": name, "size": b - a, "lib": library(attrib.obj_source(obj)), "region": attrib.region(a)}

# call graph from the disassembly
dis = subprocess.run(["arm-none-eabi-objdump", "-d", "--no-show-raw-insn", elf],
                     capture_output=True, text=True).stdout
edges = collections.defaultdict(set)
cur = None
hdr = re.compile(r"^([0-9a-f]{8}) <(.+)>:$")
call = re.compile(r"^\s*[0-9a-f]+:\s+(?:bl|blx|b\.w|b)(?:\.[a-z]+)?\s+([0-9a-f]+)\s+<([^>+]+)")
for line in dis.splitlines():
    m = hdr.match(line)
    if m:
        cur = int(m.group(1), 16)
        continue
    m = call.match(line)
    if m and cur is not None:
        t = int(m.group(1), 16) & ~1
        s = attrib.lookup(syms, sstarts, t)
        if s and s[0] != cur:
            edges[cur].add(s[0])
# a veneer forwards to the function it is named for
by_name = collections.defaultdict(list)
for a, b, name in syms:
    by_name[re.sub(r"\(.*", "", name)].append(a)
veneer_target = {}
for a, b, name in syms:
    m = re.match(r"^_*(.+)_veneer$", name)
    if m:
        dem = subprocess.run(["arm-none-eabi-c++filt", m.group(1)], capture_output=True, text=True).stdout.strip()
        for t in by_name.get(re.sub(r"\(.*", "", dem), []):
            veneer_target[a] = t

samples = collections.Counter()
total = 0
for f in sample_files:
    n = 0
    c = collections.Counter()
    for line in open(f):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            a = int(line.split()[0], 16) & ~1
        except ValueError:
            continue
        n += 1
        s = attrib.lookup(syms, sstarts, a)
        if s:
            c[s[0]] += 1
    for k, v in c.items():
        samples[k] += 100.0 * v / n / len(sample_files)   # mean % of all core0 samples

root_addrs = [a for r in ROOTS for a in by_name.get(r, [])]
seen, stack, plane_tree, cut = set(), list(root_addrs), set(), collections.Counter()
while stack:
    a = stack.pop()
    a = veneer_target.get(a, a)
    if a in seen:
        continue
    seen.add(a)
    if info[a]["lib"] not in PLANE_LIBS:
        cut[a] += 1
        continue
    plane_tree.add(a)
    stack.extend(edges.get(a, ()))

rows = []
for a in plane_tree:
    i = info[a]
    rows.append({"addr": a, "name": i["name"], "lib": i["lib"], "size": i["size"], "region": i["region"],
                 "pct": samples.get(a, 0.0), "per_kb": samples.get(a, 0.0) / max(i["size"], 1) * 1024})
rows.sort(key=lambda r: -r["pct"])
tree_bytes = sum(r["size"] for r in rows if r["region"] == "xip")
print(f"Plane-only functions reachable from the per-loop roots: {len(rows)}, {tree_bytes} B in XIP")
print(f"their XIP samples: {sum(r['pct'] for r in rows if r['region'] == 'xip'):.2f}% of core0 (mean of {len(sample_files)} profiles)")
all_plane_xip = sum(v for k, v in samples.items() if info.get(k, {}).get("lib") in PLANE_LIBS and info[k]["region"] == "xip")
print(f"all Plane-only XIP samples: {all_plane_xip:.2f}% of core0")
print(f"{'% core0':>8s} {'/KB':>6s} {'size':>6s} {'cum B':>7s}  lib           function")
cum = 0
for r in rows:
    if r["region"] != "xip":
        continue
    cum += r["size"]
    print(f"{r['pct']:8.3f} {r['per_kb']:6.2f} {r['size']:6d} {cum:7d}  {r['lib'][:13]:13s} {r['name'][:80]}")
print("calls leaving Plane-only code, by samples of the callee:")
for a, _ in sorted(cut.items(), key=lambda kv: -samples.get(kv[0], 0))[:15]:
    print(f"  {samples.get(a, 0):6.3f} {info[a]['region']:4s} {info[a]['size']:6d} {info[a]['lib'][:16]:16s} {info[a]['name'][:70]}")
# hot Plane-only XIP functions not reached statically (called through pointers: modes, logging)
missed = sorted(((v, k) for k, v in samples.items() if k not in plane_tree and info.get(k, {}).get("lib") in PLANE_LIBS
                 and info[k]["region"] == "xip"), reverse=True)
print("hot Plane-only XIP functions outside the static tree:")
for v, k in missed[:25]:
    print(f"  {v:6.3f} {info[k]['size']:6d} {info[k]['lib'][:12]:12s} {info[k]['name'][:80]}")
json.dump({"rows": rows, "missed": [{"addr": k, "pct": v, "name": info[k]["name"], "size": info[k]["size"],
                                     "lib": info[k]["lib"]} for v, k in missed]}, open(out_json, "w"), indent=1)
