#!/usr/bin/env python3
"""Attribute the PC-sample difference between two runs (attrib.py --json) to cost categories.

Usage: categ.py BASE.json RUN.json
Points are percentage points of all core0 samples (run minus base).
"""
import json
import re
import sys

GC = {"lgc.c"}
HOOK_FN = {"luaG_traceexec"}
VM = {f"{n}.c" for n in "lapi lauxlib lbaselib lcode lcorolib lctype ldebug ldo ldump lfunc linit llex "
      "lmathlib lmem lobject lopcodes loslib lparser lstate lstring lstrlib ltable ltablib ltm lundump "
      "lutf8lib lvm lzio".split()}


def cat(fn, src):
    if fn == "rp2350_idle_c0":
        return "idle"
    if fn in HOOK_FN:
        return "VM instruction hook (luaG_traceexec)"
    if src in GC:
        return "Lua GC (lgc.c)"
    if fn.startswith("load_function") or fn == "strcmp":
        return "binding name lookup (load_function + strcmp)"
    if src in VM:
        return "Lua VM and API"
    if src in ("lua_generated_bindings.cpp", "lua_bindings.cpp", "lua_boxed_numerics.cpp",
               "AP_Scripting_helpers.cpp"):
        return "binding glue"
    if src in ("lua_scripts.cpp", "AP_Scripting.cpp"):
        return "script runner"
    if "chmemheaps" in src or src in ("AP_MultiHeap.cpp", "MultiHeap_chibios.cpp", "tlsf.c"):
        return "heap alloc/free"
    if src.startswith("AP_Logger") or "Logger" in fn:
        return "AP_Logger (logger:write)"
    if re.search(r"(libc|libm|libgcc)\.a\(", src) or src.endswith(".S") and fn != "strcmp":
        return "libc/libm/libgcc"
    if "libch.a" in src:
        return "ChibiOS kernel"
    if src.startswith("AP_NavEKF") or src.startswith("AP_AHRS") or src.startswith("AP_DAL"):
        return "AHRS/EKF"
    return "other ArduPilot"


def load(p):
    d = json.load(open(p))
    out = {}
    for k, c in d["funcs"].items():
        fn, _, src = k.split("|")
        out[cat(fn, src)] = out.get(cat(fn, src), 0) + c
    return {k: 100.0 * v / d["total"] for k, v in out.items()}


a, b = load(sys.argv[1]), load(sys.argv[2])
rows = sorted(((k, b.get(k, 0) - a.get(k, 0), a.get(k, 0), b.get(k, 0)) for k in set(a) | set(b)),
              key=lambda r: -r[1])
busy = -(b.get("idle", 0) - a.get("idle", 0))
print(f"core0 busy +{busy:.2f} points")
for k, dlt, va, vb in rows:
    if k == "idle":
        continue
    print(f"  {dlt:+6.2f}  ({100 * dlt / busy:5.1f}% of the increase)  {k:46s} {va:5.2f} -> {vb:5.2f}")
