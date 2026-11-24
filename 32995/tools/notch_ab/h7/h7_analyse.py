#!/usr/bin/env python3
"""Analyse the #35358 TBS_LUCID_H7 A/B: CPU share from J-Link PC samples, and the log's loop and notch figures.

usage: h7_analyse.py BENCH_DIR ELF_DIR [--top]
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
TOP = "--top" in sys.argv
IDLE = re.compile(r"(_idle_thread|__idle_thread|idle_loop|chSysHalt|port_wait_for_interrupt)")
TRIG = re.compile(r"^(sinf|cosf|__ieee754_rem_pio2f|__math_invalidf|__sincosf.*|calculate_sinf_cosf)$")
UPDATE = re.compile(r"(NotchFilter<.*>::init_with_A_and_Q|HarmonicNotchFilter<.*>::(update|set_center_frequency|expand)|"
                    r"^sinf$|^cosf$|__ieee754_rem_pio2f|__math_invalidf|calculate_sinf_cosf)")


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


def profile(tag, path):
    pcs = [int(x, 16) & ~1 for x in open(path).read().split() if re.fullmatch(r"[0-9A-F]{8}", x)]
    names = {}
    for pc in pcs:
        n = name_at(tag, pc)
        names[n] = names.get(n, 0) + 1
    n = len(pcs)
    idle = sum(c for k, c in names.items() if k and IDLE.search(k))
    upd = sum(c for k, c in names.items() if k and UPDATE.search(k))
    trig = sum(c for k, c in names.items() if k and TRIG.search(k))
    top = sorted(names.items(), key=lambda kv: -kv[1])[:12]
    return {"n": n, "busy": 100 * (n - idle) / n, "update": 100 * upd / n, "trig": 100 * trig / n,
            "unknown": 100 * names.get(None, 0) / n, "top": [(k, round(100 * c / n, 2)) for k, c in top]}


def log_stats(path):
    if not os.path.exists(path):
        return None
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    r = {k: [] for k in ("PM", "RTDT", "ARM", "ESC", "FTN1", "FTN")}
    t0 = None
    while True:
        m = log.recv_match(type=list(r))
        if m is None:
            break
        t = m.TimeUS * 1e-6
        t0 = t if t0 is None else t0
        r[m.get_type()].append((t - t0, m))
    disarm = [t for t, m in r["ARM"] if not m.ArmState]
    end = disarm[0] if disarm else (r["PM"][-1][0] if r["PM"] else 0)
    pm = [m for t, m in r["PM"] if 6 <= t <= end]
    rt = [m for t, m in r["RTDT"] if 3.5 <= t <= end - 0.2]
    esc = [m for t, m in r["ESC"] if 6 <= t <= end]
    ftn = [m for t, m in (r["FTN1"] or r["FTN"]) if 6 <= t <= end]
    out = {"pm_n": len(pm), "rt_n": len(rt), "esc_n": len(esc), "ftn_n": len(ftn)}
    if pm:
        out.update(load=st.median(m.Load for m in pm) * 0.1, nlon=sum(m.NLon for m in pm), maxt_ms=max(m.MaxT for m in pm) * 1e-3)
    if rt:
        out.update(dt_avg_us=st.mean(m.dtAvg for m in rt) * 1e6, dt_worst_ms=max(m.dtMax for m in rt) * 1e3)
    if esc:
        f = [m.RPM / 60 for m in esc]
        out.update(motor_hz=(round(min(f)), round(st.median(f)), round(max(f))))
    if ftn:
        out["ftn_fields"] = ftn[0].get_fieldnames()[:8]
        nd = [getattr(m, "NDn", None) for m in ftn]
        out["notches"] = sorted(set(x for x in nd if x is not None))
    return out


rows = []
for d in sorted(glob.glob(f"{BASE}/run*"), key=lambda x: int(re.search(r"run(\d+)", x).group(1))):
    if not os.path.exists(f"{d}/pcsr.txt"):
        continue
    run = os.path.basename(d)
    tag = run[-1]
    row = {"run": run, "tag": tag, "pc": profile(tag, f"{d}/pcsr.txt"), "log": log_stats(f"{d}/bench.BIN")}
    rows.append(row)
    p, lg = row["pc"], row["log"] or {}
    print(f"{run}: busy {p['busy']:.2f}% (notch update {p['update']:.2f}, trig {p['trig']:.2f}, unresolved {p['unknown']:.2f}; "
          f"n={p['n']}); log {({k: (round(v, 3) if isinstance(v, float) else v) for k, v in lg.items()})}")
    if TOP:
        for k, v in p["top"]:
            print(f"    {v:6.2f}  {k}")

print("\nby build: mean of boots (min-max) [change from A]")
for label, get in (("busy, PC samples", lambda r: r["pc"]["busy"]), ("notch update", lambda r: r["pc"]["update"]),
                   ("trig", lambda r: r["pc"]["trig"]), ("PM load %", lambda r: (r["log"] or {}).get("load")),
                   ("rate loop dt avg us", lambda r: (r["log"] or {}).get("dt_avg_us")),
                   ("worst rate loop dt ms", lambda r: (r["log"] or {}).get("dt_worst_ms"))):
    parts, base = [], None
    for t in "AB":
        v = [get(x) for x in rows if x["tag"] == t]
        v = [x for x in v if x is not None]
        if not v:
            continue
        m = st.mean(v)
        base = m if t == "A" else base
        parts.append(f"{t} {m:7.2f} ({min(v):.2f}-{max(v):.2f})" + ("" if t == "A" or base is None else f" [{m - base:+.2f}]"))
    print(f"  {label:24s} " + "   ".join(parts))
