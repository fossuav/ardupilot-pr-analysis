#!/usr/bin/env python3
"""Attribute PCSR samples (from pcs.py) to functions, source groups and memory regions.

Usage: attrib.py ELF MAP SAMPLES [SAMPLES...] [--top N] [--json OUT]
Groups come from the object file each function was linked from (the link map),
so static functions are attributed as well as global ones.
"""
import bisect
import json
import re
import subprocess
import sys

LUA_VM = {f"{n}.c" for n in "lapi lauxlib lbaselib lbitlib lcode lcorolib lctype ldblib ldebug ldo ldump lfunc lgc "
          "linit liolib llex lmathlib lmem loadlib lobject lopcodes loslib lparser lstate lstring lstrlib "
          "ltable ltablib ltm lundump lutf8lib lvm lzio".split()}
SCRIPTING = {"AP_Scripting.cpp", "AP_Scripting_CANSensor.cpp", "AP_Scripting_CRSFMenu.cpp",
             "AP_Scripting_SerialAccess.cpp", "AP_Scripting_SerialDevice.cpp", "AP_Scripting_helpers.cpp",
             "lua_bindings.cpp", "lua_boxed_numerics.cpp", "lua_scripts.cpp", "lua_generated_bindings.cpp"}
HEAP = {"AP_MultiHeap.cpp", "MultiHeap_chibios.cpp", "MultiHeap_malloc.cpp", "tlsf.c"}
LED = {"AP_SerialLED.cpp"}
IDLE = {"rp2350_idle_c0", "rp2350_idle_c1", "__idle_thread"}


def region(a):
    if 0x10000000 <= a < 0x14000000:
        return "xip"
    if 0x20000000 <= a < 0x20080000:
        return "sram"
    if 0x20080000 <= a < 0x20081000:
        return "scrX"
    if 0x20081000 <= a < 0x20082000:
        return "scrY"
    return "other"


def load_map(path):
    """(start, end, object basename) for every input section with a size."""
    ents = []
    pending = None
    obj_re = re.compile(r"^\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S.*)$")
    one_re = re.compile(r"^ (\.\S+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S.*)$")
    for line in open(path, errors="replace"):
        m = one_re.match(line)
        if m:
            a, sz, obj = int(m.group(2), 16), int(m.group(3), 16), m.group(4)
            if sz:
                ents.append((a, a + sz, obj))
            pending = None
            continue
        if re.match(r"^ \.\S+\s*$", line):
            pending = True
            continue
        if pending:
            m = obj_re.match(line)
            if m:
                a, sz, obj = int(m.group(1), 16), int(m.group(2), 16), m.group(3)
                if sz:
                    ents.append((a, a + sz, obj))
            pending = None
    ents.sort()
    return ents


def obj_source(obj):
    # lib/libArduCopter_libs.a(lvm.c.0.o) -> lvm.c ; libc.a(foo.o) -> libc.a(foo.o)
    m = re.search(r"\(([^()]+?)\.\d+\.o\)$", obj)
    if m:
        return m.group(1)
    m = re.search(r"([^/]+?)\.\d+\.o$", obj)
    return m.group(1) if m else obj


def load_syms(elf):
    out = subprocess.run(["arm-none-eabi-nm", "-n", "-S", "-C", "--defined-only", elf],
                         capture_output=True, text=True, check=True).stdout
    syms = []
    for line in out.splitlines():
        p = line.split(None, 3)
        if len(p) == 4 and p[2] in "tTwW":
            a, sz = int(p[0], 16), int(p[1], 16)
            if sz:
                syms.append((a & ~1, (a & ~1) + sz, p[3]))
    syms.sort()
    return syms


def lookup(table, starts, a):
    i = bisect.bisect_right(starts, a) - 1
    if i >= 0 and table[i][0] <= a < table[i][1]:
        return table[i]
    return None


def group_of(src, fn, obj):
    if fn in IDLE:
        return "idle"
    if src in LUA_VM:
        return "lua_vm"
    if src in SCRIPTING:
        return "scripting_glue"
    if src in HEAP:
        return "script_heap"
    if src in LED or "serial_led" in fn:
        return "serial_led"
    if re.search(r"/(libc|libm|libgcc)\.a\(", obj):
        return "libc_libm"
    return None


def main():
    args = sys.argv[1:]
    top = 25
    jout = None
    if "--top" in args:
        i = args.index("--top")
        top = int(args[i + 1])
        del args[i:i + 2]
    if "--json" in args:
        i = args.index("--json")
        jout = args[i + 1]
        del args[i:i + 2]
    elf, mapf, files = args[0], args[1], args[2:]
    ents, syms = load_map(mapf), load_syms(elf)
    estarts, sstarts = [e[0] for e in ents], [s[0] for s in syms]

    total = bad = 0
    groups, regions, funcs = {}, {}, {}
    for f in files:
        for line in open(f):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                a = int(line, 16)
            except ValueError:
                bad += 1
                continue
            if a == 0xFFFFFFFF:
                bad += 1
                continue
            total += 1
            a &= ~1
            s = lookup(syms, sstarts, a)
            e = lookup(ents, estarts, a)
            fn = s[2] if s else f"?{a:08x}"
            obj = e[2] if e else "?"
            src = obj_source(obj)
            g = group_of(src, fn, obj)
            if g is None:
                g = "other_" + region(a)
            groups[g] = groups.get(g, 0) + 1
            if g != "idle":
                regions[region(a)] = regions.get(region(a), 0) + 1
            key = (fn, region(a), src)
            funcs[key] = funcs.get(key, 0) + 1

    busy = total - groups.get("idle", 0)
    print(f"samples {total} (unreadable {bad}); busy {100.0 * busy / max(total, 1):.1f}%")
    print("groups (share of all samples, then of busy samples):")
    for g, c in sorted(groups.items(), key=lambda kv: -kv[1]):
        print(f"  {g:16s} {c:7d} {100.0 * c / total:6.2f}%"
              + ("" if g == "idle" else f" {100.0 * c / max(busy, 1):6.2f}%"))
    print("regions of busy samples:")
    for r, c in sorted(regions.items(), key=lambda kv: -kv[1]):
        print(f"  {r:6s} {c:7d} {100.0 * c / max(busy, 1):6.2f}%")
    print(f"top {top} functions:")
    for (fn, r, src), c in sorted(funcs.items(), key=lambda kv: -kv[1])[:top]:
        print(f"  {100.0 * c / total:6.2f}% {c:6d} {r:5s} {fn[:80]}  [{src}]")
    if jout:
        json.dump({"total": total, "bad": bad, "groups": groups, "regions": regions,
                   "funcs": {f"{fn}|{r}|{src}": c for (fn, r, src), c in funcs.items()}},
                  open(jout, "w"), indent=0)


if __name__ == "__main__":
    main()
