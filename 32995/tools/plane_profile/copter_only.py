#!/usr/bin/env python3
"""Which RP2350 placement registry entries does a Plane build place in SRAM for nothing?

Usage: copter_only.py PLANE_ELF PLANE_MAP REPO OUT_JSON PROFILES_SPEC...
PROFILES_SPEC is ELF:MAP:SAMPLES_GLOB, one per build the samples were taken on.

Each entry present in the Plane ELF is classed by evidence:
  runs        sampled in some Plane profile (core0 or core1)
  multirotor  never sampled, and every caller chain, direct calls and function
              pointers in data alike, ends in multirotor code: QuadPlane and its
              VTOL modes, or the AC_* and AP_Motors libraries
  cold        never sampled, but some caller chain reaches fixed-wing code
  unref       never sampled, and nothing in the Plane ELF calls or points to it
Entries the Plane ELF does not have at all are "absent" and cost Plane nothing.
"""
import collections
import glob
import json
import os
import re
import struct
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripting_profile"))
import attrib  # noqa: E402

elf, mapf, repo, out_json = sys.argv[1:5]
specs = sys.argv[5:]
REG_DIR = os.path.join(repo, "libraries/AP_HAL_ChibiOS/rp2350")
REGISTRIES = ("rp2350_ramfunc2_registry.txt", "rp2350_scratchx_registry.txt", "rp2350_scratchy_registry.txt")
M_LIBS = {"AC_AttitudeControl", "AC_PosControl", "AC_WPNav", "AP_Motors", "AC_InputManager", "AC_Avoidance",
          "AC_PrecLand", "AC_Sprayer", "AC_AutoTune", "ArduCopter"}
M_PLANE_FILES = {"quadplane.cpp", "tailsitter.cpp", "tiltrotor.cpp", "VTOL_Assist.cpp", "qautotune.cpp",
                 "mode_qacro.cpp", "mode_qautotune.cpp", "mode_qhover.cpp", "mode_qland.cpp", "mode_qloiter.cpp",
                 "mode_qrtl.cpp", "mode_qstabilize.cpp", "transition.h"}


def key(name):
    """The registry's matching key: drop a decltype return type, the argument list and spaces."""
    if name.startswith("decltype"):
        depth = 0
        for i in range(8, len(name)):
            if name[i] == "(":
                depth += 1
            elif name[i] == ")":
                depth -= 1
                if depth == 0:
                    name = name[i + 1:].lstrip()
                    break
    depth = 0
    for i, c in enumerate(name):
        if c == "<":
            depth += 1
        elif c == ">" and depth:
            depth -= 1
        elif c == "(" and depth == 0:
            name = name[:i]
            break
    return re.sub(r"\s+", "", name)


# --- registries
entries = []
for reg in REGISTRIES:
    for line in open(os.path.join(REG_DIR, reg)):
        if not line.strip() or line.lstrip().startswith("#") or "|" not in line:
            continue
        path, rest = line.split("|", 1)
        sym = rest.split("#", 1)[0].strip()
        if not sym:
            continue
        only = re.search(r"\[only ([A-Za-z_][A-Za-z0-9_]*)\]", line)
        entries.append({"registry": reg, "path": path.strip(), "sym": sym,
                        "key": sym if path.strip() == "(archive)" else key(sym),
                        "archive": path.strip() == "(archive)", "only": only.group(1) if only else None})

# --- library of an object, as in libgroup.py
where = collections.defaultdict(set)
for p in subprocess.run(["git", "-C", repo, "ls-files"], capture_output=True, text=True).stdout.split():
    parts = p.split("/")
    if parts[0] == "libraries" and len(parts) > 2:
        where[os.path.basename(p)].add(parts[1])
    elif parts[0] in ("ArduPlane", "ArduCopter", "Rover", "ArduSub", "Blimp", "AntennaTracker"):
        where[os.path.basename(p)].add(parts[0])


def lib_of(obj):
    if "libch.a" in obj or "ChibiOS" in obj:
        return "ChibiOS"
    m = re.search(r"/(libc|libm|libgcc)\.a\(", obj)
    if m:
        return m.group(1)
    src = attrib.obj_source(obj)
    libs = where.get(src, set())
    for pref in ("ArduPlane", "AP_HAL_ChibiOS"):
        if pref in libs:
            return pref
    return next(iter(libs)) if len(libs) == 1 else ("|".join(sorted(libs)) or "?")


def is_multirotor(obj):
    lib = lib_of(obj)
    return lib in M_LIBS or (lib == "ArduPlane" and attrib.obj_source(obj) in M_PLANE_FILES)


# --- the Plane ELF
nm = subprocess.run(["arm-none-eabi-nm", "-S", "--defined-only", elf], capture_output=True, text=True).stdout
rows = []
for line in nm.splitlines():
    p = line.split()
    if len(p) == 4:
        rows.append((int(p[0], 16), int(p[1], 16), p[2], p[3]))
dem = subprocess.run(["arm-none-eabi-c++filt"], input="\n".join(r[3] for r in rows), capture_output=True,
                     text=True).stdout.splitlines()
funcs = {}            # addr -> {name, key, size}
by_key = collections.defaultdict(list)
data_syms = []        # (start, end, name)
for (a, sz, t, m), d in zip(rows, dem):
    if t in "TtWw" and sz:
        a &= ~1
        funcs[a] = {"name": d, "key": key(d), "size": sz, "mangled": m}
        by_key[key(d)].append(a)
    elif t in "DdRrBbVv" and sz:
        data_syms.append((a, a + sz, d))
data_syms.sort()
ents = attrib.load_map(mapf)
estarts = [e[0] for e in ents]


def obj_at(a):
    e = attrib.lookup(ents, estarts, a)
    return e[2] if e else ""


fstarts = sorted(funcs)
fends = {a: a + funcs[a]["size"] for a in funcs}


def func_at(a):
    import bisect
    i = bisect.bisect_right(fstarts, a) - 1
    if i >= 0 and fstarts[i] <= a < fends[fstarts[i]]:
        return fstarts[i]
    return None


# direct calls
dis = subprocess.run(["arm-none-eabi-objdump", "-d", "--no-show-raw-insn", elf], capture_output=True, text=True).stdout
callers = collections.defaultdict(set)
cur = None
hdr = re.compile(r"^([0-9a-f]{8}) <(.+)>:$")
call = re.compile(r"^\s*[0-9a-f]+:\s+(?:bl|blx|b\.w|b)(?:\.[a-z]+)?\s+([0-9a-f]+)\s+<")
for line in dis.splitlines():
    m = hdr.match(line)
    if m:
        cur = func_at(int(m.group(1), 16))
        continue
    m = call.match(line)
    if m and cur is not None:
        t = func_at(int(m.group(1), 16) & ~1)
        if t is not None and t != cur:
            callers[t].add(cur)
# a veneer's callers call its target
for a, f in funcs.items():
    mm = re.match(r"^_*(.+)_veneer$", f["mangled"])
    if not mm:
        continue
    tgt_dem = subprocess.run(["arm-none-eabi-c++filt", mm.group(1)], capture_output=True, text=True).stdout.strip()
    for t in by_key.get(key(tgt_dem), []):
        callers[t] |= callers.get(a, set())

# pointers to functions in data (vtables, tables, functors)
secs = []
out = subprocess.run(["arm-none-eabi-readelf", "-S", "-W", elf], capture_output=True, text=True).stdout
for line in out.splitlines():
    p = line.replace("[ ", "[").split()
    if len(p) > 6 and p[0].startswith("[") and p[2] == "PROGBITS" and int(p[5], 16):
        secs.append((p[1], int(p[3], 16), int(p[4], 16), int(p[5], 16)))
blob = open(elf, "rb").read()
pointed = collections.defaultdict(set)   # func addr -> data owner objects
# code sections too: thread entries, callbacks and functors take a function's
# address from a literal pool
for name, va, off, size in secs:
    for i in range(0, size - 3, 4):
        w = struct.unpack_from("<I", blob, off + i)[0]
        if w & 1 and (w & ~1) in funcs:
            pointed[w & ~1].add(obj_at(va + i) or f"?{name}")

# samples, aggregated by key across builds
samples = collections.Counter()
for spec in specs:
    pelf, pmap, pglob = spec.split(":", 2)
    syms = attrib.load_syms(pelf)
    ss = [s[0] for s in syms]
    files = sorted(glob.glob(pglob))
    for f in files:
        for line in open(f):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                a = int(line.split()[0], 16) & ~1
            except ValueError:
                continue
            s = attrib.lookup(syms, ss, a)
            if s:
                samples[key(s[2])] += 1
total_samples = sum(samples.values())


def reaches_fixed_wing(a, depth=10):
    """Does some caller chain of a, direct or through a data pointer, leave multirotor code?"""
    seen, frontier = {a}, [a]
    for _ in range(depth):
        nxt = []
        for f in frontier:
            for o in pointed.get(f, ()):
                if not (o.startswith("?") or is_multirotor(o)):
                    return True
            for c in callers.get(f, ()):
                if c in seen:
                    continue
                seen.add(c)
                if not is_multirotor(obj_at(c)):
                    return True
                nxt.append(c)
        frontier = nxt
        if not frontier:
            break
    return False


results = []
for e in entries:
    if e["archive"]:
        member = e["sym"]
        addrs = [a for a in funcs if member.split("-", 1)[-1] in obj_at(a) and ".a(" in obj_at(a)]
    else:
        addrs = by_key.get(e["key"], [])
    if not addrs:
        e.update(cls="absent", size=0, samples=0, lib="")
        results.append(e)
        continue
    size = sum(funcs[a]["size"] for a in addrs)
    smp = sum(samples.get(funcs[a]["key"], 0) for a in addrs)
    objs = {obj_at(a) for a in addrs}
    lib = lib_of(next(iter(objs)))
    region = attrib.region(addrs[0])
    if smp:
        cls = "runs"
    elif all(is_multirotor(o) for o in objs) or not any(reaches_fixed_wing(a) for a in addrs):
        refd = any(callers.get(a) or pointed.get(a) for a in addrs)
        cls = "multirotor" if refd or all(is_multirotor(o) for o in objs) else "unref"
    else:
        cls = "cold"
    e.update(cls=cls, size=size, samples=smp, lib=lib, region=region)
    results.append(e)

print(f"profiles: {total_samples} samples")
for reg in REGISTRIES:
    rs = [r for r in results if r["registry"] == reg]
    print(f"\n{reg}: {len(rs)} entries")
    for cls in ("absent", "runs", "cold", "multirotor", "unref"):
        sel = [r for r in rs if r["cls"] == cls]
        print(f"  {cls:10s} {len(sel):4d} entries {sum(r['size'] for r in sel):7d} B")
json.dump(results, open(out_json, "w"), indent=1)
