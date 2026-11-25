#!/usr/bin/env python3
"""Pick the Plane hot-path functions to place in SRAM from sweep.py's output.

Usage: select.py SWEEP_JSON COPTER_ELF REPO
Keeps Plane-only functions in XIP flash with at least MIN_PCT of core0 on average, or
MIN_DENSE_PCT and DENSE_PER_KB, and rejects any name (demangled, without arguments, as
the registry matches) that also exists in the Copter ELF, so Copter cannot move.
Prints registry lines with the source file of each function.
"""
import json
import os
import re
import subprocess
import sys

MIN_PCT = float(os.environ.get("MIN_PCT", "0.03"))          # mean share of core0 samples
MIN_DENSE_PCT = float(os.environ.get("MIN_DENSE_PCT", "0.015"))
DENSE_PER_KB = float(os.environ.get("DENSE_PER_KB", "1.0"))

sweep, copter_elf, repo = sys.argv[1:4]
d = json.load(open(sweep))
cands = [r for r in d["rows"] if r["region"] == "xip"] + d["missed"]


def key(name):
    # the registry's matching key: demangled name without the argument list or spaces
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


copter = set()
out = subprocess.run(["arm-none-eabi-nm", "-C", "--defined-only", copter_elf], capture_output=True, text=True).stdout
for line in out.splitlines():
    p = line.split(None, 2)
    if len(p) == 3 and p[1] in "tTwW":
        copter.add(key(p[2]))

# where each Plane function is defined, for the registry's documentation path
def source_of(name):
    """(path, from a header) for the registry's documentation path."""
    k = key(name)
    if "method_wrapper" in k:
        return "(profiled)", False
    fn = k.split("::")[-1]
    cls = k.split("::")[-2] if "::" in k else None
    if cls:
        pat = rf"(^|[^A-Za-z0-9_]){re.escape(cls)}::{re.escape(fn)}\s*\("
    else:
        pat = rf"^[A-Za-z].*[^A-Za-z0-9_]{re.escape(fn)}\s*\("
    r = subprocess.run(["git", "-C", repo, "grep", "-lE", pat, "--", "ArduPlane", "libraries/APM_Control",
                        "libraries/AP_TECS", "libraries/AP_L1_Control", "libraries/AP_Landing"],
                       capture_output=True, text=True).stdout.split()
    cpp = [f for f in r if f.endswith(".cpp")]
    if cpp:
        return cpp[0], False
    # defined in its class body in a header
    r = subprocess.run(["git", "-C", repo, "grep", "-lE", rf"[^A-Za-z0-9_]{re.escape(fn)}\s*\(", "--",
                        "ArduPlane/*.h", "libraries/APM_Control/*.h", "libraries/AP_Landing/*.h"],
                       capture_output=True, text=True).stdout.split()
    hdr = [f for f in r if cls and cls.lower().replace("_", "") in f.lower().replace("_", "")] or r
    return (hdr[0] if hdr else "?"), True


picked, rejected = [], []
seen = set()
for r in sorted(cands, key=lambda r: -r["pct"]):
    k = key(r["name"])
    if k in seen:
        continue
    seen.add(k)
    per_kb = r["pct"] / max(r["size"], 1) * 1024
    hot = r["pct"] >= MIN_PCT or (r["pct"] >= MIN_DENSE_PCT and per_kb >= DENSE_PER_KB)
    if not hot:
        continue
    if per_kb < 0.1:
        rejected.append((r, "cold for its size"))
        continue
    if k in copter:
        rejected.append((r, "name exists in Copter"))
        continue
    picked.append(r)

total = sum(r["size"] for r in picked)
print(f"# picked {len(picked)} functions, {total} B, {sum(r['pct'] for r in picked):.2f}% of core0 on average")
for r in picked:
    path, header = source_of(r["name"])
    name = r["name"] if "method_wrapper" in r["name"] else key(r["name"])
    name = re.sub(r"\(void\*\)$", "", name)
    marks = "[arduplane]" + (" [inlinable]" if header else "")
    print(f"{path}|{name}  # {r['size']} B {marks}")
print("# rejected:")
for r, why in rejected:
    print(f"#   {key(r['name'])} {r['size']} B {r['pct']:.3f}%: {why}")
