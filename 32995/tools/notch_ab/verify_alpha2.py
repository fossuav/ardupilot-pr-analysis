#!/usr/bin/env python3
"""Independent check of the alpha2 flight card's log figures, written without the notes' tools.

usage: verify_alpha2.py LOG.BIN [LOG.BIN ...]
"""
import os
import re
import statistics as st
import sys

from pymavlink import DFReader

TYPES = ["ARM", "EV", "RPLD", "RTDT", "PM", "DSF", "ESC", "ERR", "MSG", "FILE", "LEDC", "CTUN", "BAT", "GPS"]


def pct(values, p):
    v = sorted(values)
    return v[min(len(v) - 1, int(len(v) * p))]


def spans(events, start_ids, stop_ids, end):
    out, cur = [], None
    for t, i in events:
        if i in start_ids and cur is None:
            cur = t
        elif i in stop_ids and cur is not None:
            out.append((cur, t))
            cur = None
    if cur is not None:
        out.append((cur, end))
    return out


def inside(t, windows):
    return any(a <= t <= b for a, b in windows)


for path in sys.argv[1:]:
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    r = {k: [] for k in TYPES}
    files = []
    t0 = last = None
    while True:
        m = log.recv_match(type=TYPES)
        if m is None:
            break
        k = m.get_type()
        if k == "FILE":
            if "threads" in str(m.FileName):
                d = m.Data
                d = d.encode("latin1", "replace") if isinstance(d, str) else bytes(d)
                files.append((int(m.Offset), d[:int(m.Length)]))
            continue
        t = m.TimeUS * 1e-6
        t0 = t if t0 is None else t0
        last = t
        r[k].append((t - t0, m))
    end = last - t0
    arm_ev = [(t, int(m.ArmState)) for t, m in r["ARM"]]
    armed = spans([(t, 10 if s else 11) for t, s in arm_ev], {10}, {11}, end)
    ev = [(t, int(m.Id)) for t, m in r["EV"]]
    flying = spans(ev, {28}, {18}, end)
    flying = [w for w in flying if w[1] - w[0] > 5 and any(a <= w[0] <= b for a, b in armed)]
    print(f"=== {os.path.basename(path)}: {end:.1f} s")
    print("  armed:", [(round(a, 1), round(b, 1)) for a, b in armed], " flying:",
          [(round(a, 1), round(b, 1)) for a, b in flying], f"({sum(b - a for a, b in flying):.1f} s)")

    in_f = lambda name: [(t, m) for t, m in r[name] if inside(t, flying)]
    in_a = lambda name: [(t, m) for t, m in r[name] if inside(t, armed)]
    th = [m.ThO for _, m in in_f("CTUN")]
    cur = [m.Curr for _, m in in_f("BAT") if getattr(m, "Inst", 0) == 0]
    spd = [m.Spd for _, m in in_f("GPS") if m.I == 0]
    print(f"  intensity: ThO max {max(th):.3f}, current max {max(cur):.1f} A, GPS speed max {max(spd):.1f} m/s")
    rtf = [m.dtMax for _, m in in_f("RTDT")]
    print(f"  RTDT dtMax worst in flight {max(rtf) * 1e3:.2f} ms; windows over 1 ms {sum(x > 1e-3 for x in rtf)}/{len(rtf)}")
    pm = in_f("PM")
    print(f"  PM in flight: NLon {sum(m.NLon for _, m in pm)}, MaxT worst {max(m.MaxT for _, m in pm) * 1e-3:.2f} ms, "
          f"Mem min {min(m.Mem for _, m in pm) / 1024:.1f} KB, InE {max(m.InE for _, m in pm)}, "
          f"ErC {max(m.ErC for _, m in pm)}")
    print(f"  PM armed: NLon {sum(m.NLon for _, m in in_a('PM'))}; all log InE {max(m.InE for _, m in r['PM'])}")
    print(f"  DSF: dropped {max(m.Dp for _, m in r['DSF'])}, free min {min(m.FMn for _, m in r['DSF'])} B")
    esc = in_f("ESC")
    print(f"  ESC: {len(esc) / sum(b - a for a, b in flying) / 4:.0f} Hz/motor, Err max {max(m.Err for _, m in esc):.2f}")
    errs = sorted({(int(m.Subsys), int(m.ECode)) for t, m in r["ERR"]})
    print(f"  ERR (subsys, code): {errs}; in flight: {sorted({(int(m.Subsys), int(m.ECode)) for t, m in in_f('ERR')})}")
    fs = sorted({m.Message for t, m in r["MSG"] if re.search(r"ailsafe|Internal|Takeoff blocked|crash|Crash", m.Message)})
    print(f"  failsafe-like messages: {fs}")
    rp = in_f("RPLD")
    for f in ("C0", "C1", "XHit", "XAcc"):
        v = [getattr(m, f) for _, m in rp]
        print(f"  RPLD {f}: median {st.median(v):.2f}, p5 {pct(v, 0.05):.2f}, max {max(v):.2f}")
    if armed:
        after = [m.C1 for t, m in r["RPLD"] if t > armed[-1][1] + 5]
        if after:
            print(f"  RPLD C1 more than 5 s after last disarm: median {st.median(after):.2f} (n={len(after)})")
    print(f"  RPLD C1 highest anywhere: {max(m.C1 for _, m in r['RPLD']):.2f}")

    led = [(t, int(m.On)) for t, m in r["LEDC"]]
    if led:
        def state(t):
            cur_s = None
            for lt, on in led:
                if lt > t:
                    break
                cur_s = (lt, on)
            return cur_s
        groups = {0: {"C0": [], "C1": []}, 1: {"C0": [], "C1": []}}
        for t, m in r["RPLD"]:
            s = state(t)
            if s and inside(t, flying) and t - s[0] >= 3:
                groups[s[1]]["C0"].append(m.C0)
                groups[s[1]]["C1"].append(m.C1)
        for f in ("C0", "C1"):
            print(f"  LED {f}: running {st.mean(groups[1][f]):.2f} (n={len(groups[1][f])}), "
                  f"stopped {st.mean(groups[0][f]):.2f} (n={len(groups[0][f])}), "
                  f"difference {st.mean(groups[1][f]) - st.mean(groups[0][f]):+.2f}")

    # threads.txt copies the logger took at each arming
    copies, cur_copy = [], None
    for off, d in files:
        if off == 0:
            cur_copy = bytearray()
            copies.append(cur_copy)
        if cur_copy is not None:
            cur_copy += d
    for i, c in enumerate(copies):
        first = c.split(b"\n", 1)[0].decode(errors="replace")
        print(f"  threads.txt at arming {i + 1}: {re.sub(' +', ' ', first)}")
    first_rows = [(round(t, 1), round(m.C0, 1), round(m.C1, 1)) for t, m in r["RPLD"] if m.C1 > 0][:4]
    print(f"  first non-zero RPLD rows (t, C0, C1): {first_rows}")
