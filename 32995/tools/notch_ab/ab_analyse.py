#!/usr/bin/env python3
"""Analyse the notch A/B runs: core load from SWD PC samples and the log, by build and by boot.

usage: ab_analyse.py BASE_DIR ELF_DIR
"""
import bisect
import glob
import os
import re
import statistics as st
import subprocess
import sys

from pymavlink import DFReader

BASE, ELFS = sys.argv[1], sys.argv[2]
UPDATE = re.compile(r"(NotchFilter<.*>::init_with_A_and_Q|HarmonicNotchFilter<.*>::(update|set_center_frequency|expand)|"
                    r"^sinf$|^cosf$|__ieee754_rem_pio2f|__kernel_sinf|__kernel_cosf|rem_pio2f_veneer|_sinf_veneer|_cosf_veneer)")
LIBM = re.compile(r"(^sinf$|^cosf$|__ieee754_rem_pio2f|__kernel_sinf|__kernel_cosf|rem_pio2f_veneer|_sinf_veneer|_cosf_veneer)")


def load_syms(elf):
    out = []
    for line in subprocess.check_output(["arm-none-eabi-nm", "-S", "-n", "-C", elf], text=True, errors="replace").splitlines():
        p = line.split(None, 3)
        if len(p) == 4 and p[2] in "tTwW":
            out.append((int(p[0], 16) & ~1, int(p[1], 16), re.sub(r"\(.*", "", p[3])))
    out.sort()
    return out, [s[0] for s in out]


SYMS = {t: load_syms(f"{ELFS}/{t}/arducopter.elf") for t in "AB"}


def name_at(tag, pc):
    syms, starts = SYMS[tag]
    i = bisect.bisect_right(starts, pc) - 1
    if i < 0:
        return None
    a, size, name = syms[i]
    return name if pc < a + max(size, 1) else None


def pcs(path):
    out = []
    for line in open(path, errors="replace"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            v = int(line.split()[0], 16)
        except ValueError:
            continue
        if v != 0xFFFFFFFF:
            out.append(v & ~1)
    return out


def profile(tag, path, idle):
    p = pcs(path)
    names = {}
    for pc in p:
        n = name_at(tag, pc)
        names[n] = names.get(n, 0) + 1
    busy = len(p) - names.get(idle, 0)
    upd = sum(c for n, c in names.items() if n and UPDATE.search(n))
    lib = sum(c for n, c in names.items() if n and LIBM.search(n))
    flash = sum(1 for pc in p if 0x10000000 <= pc < 0x20000000)
    return {"n": len(p), "busy": 100 * busy / len(p), "update": 100 * upd / len(p), "libm": 100 * lib / len(p),
            "flash": 100 * flash / len(p)}


def log_stats(path):
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    r = {k: [] for k in ("RPLD", "RTDT", "PM", "ESC", "ARM", "DSF")}
    t0 = None
    while True:
        m = log.recv_match(type=list(r))
        if m is None:
            break
        t = m.TimeUS * 1e-6
        t0 = t if t0 is None else t0
        r[m.get_type()].append((t - t0, m))
    disarm = [t for t, m in r["ARM"] if not m.ArmState]
    end = disarm[0] if disarm else r["RPLD"][-1][0]
    win = lambda name, skip=6: [m for t, m in r[name] if skip <= t <= end]
    rp = win("RPLD")
    rt = win("RTDT", 2)
    pm = win("PM", 0)
    esc = win("ESC")
    freq = [m.RPM / 60 for m in esc]
    return {"C0": st.median(m.C0 for m in rp), "C1": st.median(m.C1 for m in rp), "XHit": st.median(m.XHit for m in rp),
            "dt_avg_us": st.mean(m.dtAvg for m in rt) * 1e6, "dt_worst_ms": max(m.dtMax for m in rt) * 1e3,
            "dt_p99_ms": sorted(m.dtMax for m in rt)[int(len(rt) * 0.99)] * 1e3,
            "nlon": sum(m.NLon for m in pm), "maxt_ms": max(m.MaxT for m in pm) * 1e-3,
            "drop": max(m.Dp for _, m in r["DSF"]), "mem_kb": min(m.Mem for m in pm) / 1024,
            "motor_hz": (min(freq), st.median(freq), max(freq)) if freq else None,
            "above_400": 100 * sum(sum(f * h > 400 for h in (1, 2, 3, 4)) for f in freq) / (4 * len(freq)) if freq else 0}


rows = []
for d in sorted(glob.glob(f"{BASE}/run*"), key=lambda x: int(re.search(r"run(\d+)", x).group(1))):
    run = os.path.basename(d)
    tag = run[-1]
    row = {"run": run, "tag": tag}
    row["c1"] = profile(tag, f"{d}/pcsr1.txt", "rp2350_idle_c1")
    row["c0"] = profile(tag, f"{d}/pcsr0.txt", "rp2350_idle_c0")
    row["log"] = log_stats(f"{d}/bench.BIN")
    th = open(f"{d}/threads_armed.txt", errors="replace").readline()
    row["threads"] = re.sub(" +", " ", th.strip())
    rows.append(row)
    l = row["log"]
    print(f"{run}: core1 busy {row['c1']['busy']:.2f}% (notch update {row['c1']['update']:.2f}, trig {row['c1']['libm']:.2f}, "
          f"flash {row['c1']['flash']:.2f}; n={row['c1']['n']}), core0 busy {row['c0']['busy']:.2f}%; "
          f"RPLD C1 {l['C1']:.2f} C0 {l['C0']:.2f}; rate gap worst {l['dt_worst_ms']:.2f} ms p99 {l['dt_p99_ms']:.2f}; "
          f"dtAvg {l['dt_avg_us']:.1f} us; NLon {l['nlon']} MaxT {l['maxt_ms']:.2f}; drop {l['drop']}; "
          f"motors {tuple(round(x) for x in l['motor_hz']) if l['motor_hz'] else None} Hz, centres above 400 Hz {l['above_400']:.0f}%")

print("\nby build (mean of boots, then min-max):")
for label, get in (("core1 busy, PC samples", lambda r: r["c1"]["busy"]), ("core1 notch update", lambda r: r["c1"]["update"]),
                   ("core1 trig (libm)", lambda r: r["c1"]["libm"]), ("core1 in flash", lambda r: r["c1"]["flash"]),
                   ("core0 busy, PC samples", lambda r: r["c0"]["busy"]), ("RPLD C1", lambda r: r["log"]["C1"]),
                   ("RPLD C0", lambda r: r["log"]["C0"]), ("rate gap worst ms", lambda r: r["log"]["dt_worst_ms"]),
                   ("rate gap p99 ms", lambda r: r["log"]["dt_p99_ms"])):
    a = [get(r) for r in rows if r["tag"] == "A"]
    b = [get(r) for r in rows if r["tag"] == "B"]
    if a and b:
        print(f"  {label:24s} A {st.mean(a):7.2f} ({min(a):.2f}-{max(a):.2f})   B {st.mean(b):7.2f} ({min(b):.2f}-{max(b):.2f})   "
              f"B-A {st.mean(b) - st.mean(a):+.2f}")
