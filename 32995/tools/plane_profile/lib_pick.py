#!/usr/bin/env python3
"""Rank the functions of chosen libraries still in XIP flash by Plane core0 samples.

Usage: lib_pick.py ELF MAP REPO LIBS PROFILE_SPEC...
LIBS is comma-separated library directories (AP_NavEKF3,AP_AHRS,...). ELF/MAP are the
build being changed; PROFILE_SPEC is ELF:MAP:GLOB per build the samples were taken on, and
samples are counted by the registry's matching key, so builds can be mixed. Each file's
share of core0 counts once; the result is the mean over files. Thresholds by environment:
MIN_PCT (0.03), MIN_DENSE_PCT (0.015) at DENSE_PER_KB (1.0); prints registry lines.
"""
import collections
import glob
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripting_profile"))
import attrib  # noqa: E402
from copter_only_key import key  # noqa: E402

elf, mapf, repo, libs = sys.argv[1:5]
libs = set(libs.split(","))
specs = sys.argv[5:]
MIN_PCT = float(os.environ.get("MIN_PCT", "0.03"))
MIN_DENSE_PCT = float(os.environ.get("MIN_DENSE_PCT", "0.015"))
DENSE_PER_KB = float(os.environ.get("DENSE_PER_KB", "1.0"))
MIN_PER_KB = float(os.environ.get("MIN_PER_KB", "0.1"))     # below this a function is cold for its size

where = collections.defaultdict(set)
for p in subprocess.run(["git", "-C", repo, "ls-files"], capture_output=True, text=True).stdout.split():
    parts = p.split("/")
    if parts[0] == "libraries" and len(parts) > 2:
        where[os.path.basename(p)].add(parts[1])


def lib_of(obj):
    ls = where.get(attrib.obj_source(obj), set())
    return next(iter(ls)) if len(ls) == 1 else "|".join(sorted(ls))


syms = attrib.load_syms(elf)
ents = attrib.load_map(mapf)
es = [e[0] for e in ents]
info = {}                    # key -> (size, region, lib, name, object source)
for a, b, name in syms:
    e = attrib.lookup(ents, es, a)
    obj = e[2] if e else ""
    k = key(name)
    if k not in info or attrib.region(a) == "xip":
        info[k] = (b - a, attrib.region(a), lib_of(obj), name, attrib.obj_source(obj))

share = collections.Counter()
nfiles = 0
for spec in specs:
    pelf, pmap, pglob = spec.split(":", 2)
    psyms = attrib.load_syms(pelf)
    ps = [s[0] for s in psyms]
    for f in sorted(glob.glob(pglob)):
        nfiles += 1
        c = collections.Counter()
        n = 0
        for line in open(f):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                a = int(line.split()[0], 16) & ~1
            except ValueError:
                continue
            n += 1
            s = attrib.lookup(psyms, ps, a)
            if s:
                c[key(s[2])] += 1
        for k, v in c.items():
            share[k] += 100.0 * v / n
for k in share:
    share[k] /= nfiles

rows = []
for k, pct in share.items():
    if k not in info:
        continue
    size, region, lib, name, src = info[k]
    if region != "xip" or lib not in libs or name.endswith("_veneer"):
        continue
    rows.append((pct, size, k, lib, src))
rows.sort(reverse=True)
total = sum(r[0] for r in rows)
print(f"# {nfiles} profiles; {', '.join(sorted(libs))} in flash: {total:.2f}% of core0, {len(rows)} functions sampled")
picked = [r for r in rows if (r[0] >= MIN_PCT or (r[0] >= MIN_DENSE_PCT and r[0] / max(r[1], 1) * 1024 >= DENSE_PER_KB))
          and r[0] / max(r[1], 1) * 1024 >= MIN_PER_KB]
dropped = [r for r in rows if r[0] >= MIN_PCT and r not in picked]
print(f"# dropped as cold for their size: {len(dropped)}, {sum(r[1] for r in dropped)} B, {sum(r[0] for r in dropped):.2f}%: "
      + ", ".join(f"{r[2]} {r[1]} B" for r in dropped))
print(f"# picked {len(picked)} functions, {sum(r[1] for r in picked)} B, {sum(r[0] for r in picked):.2f}% of core0")
for pct, size, k, lib, src in picked:
    path = next((p for p in subprocess.run(["git", "-C", repo, "ls-files", f"libraries/{lib}/{src}"],
                                           capture_output=True, text=True).stdout.split()), f"libraries/{lib}/{src}")
    print(f"{path}|{k}  # {size} B, {pct:.3f}% [arduplane]")
