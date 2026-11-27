#!/usr/bin/env python3
"""RPI_UAVFC oneshot / buzzer bench on the flight board, through bridge.py on 127.0.0.1:5770
and OpenOCD TCL on 50001. Sets no parameters.

  oneshot_bench.py measure LABEL OUTDIR   banner, SERVO_OUTPUT_RAW, SWD registers, pulse sampling, tune
  oneshot_bench.py dump OUTFILE           raw copy of the parameter storage flash over SWD
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/github/ardupilot-pr-analysis/32995/data/2026-11-26-buzzer-outputs"))
import buzz_bench as bb  # noqa: E402

STORAGE_BASE = 0x10010000   # STORAGE_FLASH_PAGE 16 x 4 KB, below the 128 KB reserve
STORAGE_LEN = 0x10000
# output: (GPIO, slice, channel)
OUTS = {3: (7, 3, "B"), 4: (6, 3, "A"), 5: (12, 6, "A"), 6: (13, 6, "B"), 8: (2, 1, "A")}
OUTTOPAD = 1 << 9
SIO_GPIO_IN = 0xD0000004


def pulses(t, secs=6.0):
    """sample each output's slice counter and pad level; returns per-output stats"""
    lo_sl = min(s for _, s, _ in OUTS.values())
    hi_sl = max(s for _, s, _ in OUTS.values())
    lo_g = min(g for g, _, _ in OUTS.values())
    hi_g = max(g for g, _, _ in OUTS.values())
    ctr = {o: [] for o in OUTS}
    high = {o: 0 for o in OUTS}
    high_in = {o: 0 for o in OUTS}
    n = 0
    t_end = time.time() + secs
    while time.time() < t_end:
        sl = t.rd(bb.PWM_BASE + 0x14 * lo_sl, 5 * (hi_sl - lo_sl + 1))
        st = t.rd(bb.IO_BANK0 + 8 * lo_g, 2 * (hi_g - lo_g + 1))
        gin = t.rd(SIO_GPIO_IN)[0]
        n += 1
        for o, (g, s, _) in OUTS.items():
            ctr[o].append(sl[5 * (s - lo_sl) + 2] & 0xFFFF)
            if st[2 * (g - lo_g)] & OUTTOPAD:
                high[o] += 1
            if gin & (1 << g):
                high_in[o] += 1
    out = {}
    for o, (g, s, ch) in OUTS.items():
        c = sorted(ctr[o])
        out[o] = {"gpio": g, "slice": s, "ch": ch, "samples": n,
                  "ctr_max": c[-1], "ctr_p99": c[int(0.99 * (len(c) - 1))], "ctr_median": c[len(c) // 2],
                  "high_frac_outtopad": round(high[o] / n, 4), "high_frac_gpio_in": round(high_in[o] / n, 4)}
        bb.log(f"  out {o} GPIO{g:2d} slice {s}{ch}: CTR max {c[-1]:5d} p99 {out[o]['ctr_p99']:5d} "
               f"median {out[o]['ctr_median']:5d}  high {out[o]['high_frac_outtopad']:.3f} "
               f"(GPIO_IN {out[o]['high_frac_gpio_in']:.3f})  n={n}")
    return out


def measure(label, outdir):
    os.makedirs(outdir, exist_ok=True)
    res = {"label": label}
    m = bb.connect()
    res["banner"] = bb.banner(m)
    for line in res["banner"]:
        bb.log(f"  text: {line}")
    res["servo_raw"] = bb.servo_raw(m)
    bb.log(f"  SERVO_OUTPUT_RAW {res['servo_raw']}")
    started = False
    if not bb.openocd_running():
        bb.start_openocd(os.path.join(outdir, f"openocd_{label}.log"))
        started = True
    try:
        t = bb.Tcl()
        res["funcsel"] = {g: bb.funcsel(t, g) for g in (2, 3, 6, 7, 12, 13)}
        bb.log(f"  FUNCSEL {res['funcsel']}")
        res["slices"] = {}
        for sl in (1, 3, 4, 6):
            r = bb.slice_regs(t, sl)
            res["slices"][sl] = r
            bb.log(f"  slice {sl}: EN {r['en']} DIV {r['div']:8.4f} TOP {r['top']:5d} period {r['period_us']:8.1f} us"
                   f"  A {r['a_us']:7.1f} us  B {r['b_us']:7.1f} us")
        res["pulses"] = pulses(t)
        texts = []
        res["tune"] = bb.tune_test(m, t, texts)
        res["tune_texts"] = texts
    finally:
        if started:
            bb.release_openocd()
    m.close()
    with open(os.path.join(outdir, f"{label}.json"), "w") as fh:
        json.dump(res, fh, indent=1)


def dump(outfile):
    started = False
    if not bb.openocd_running():
        bb.start_openocd(outfile + ".openocd.log")
        started = True
    try:
        t = bb.Tcl()
        words = []
        chunk = 1024
        for off in range(0, STORAGE_LEN, chunk * 4):
            w = t.rd(STORAGE_BASE + off, chunk)
            if len(w) != chunk:
                sys.exit(f"short read at {STORAGE_BASE + off:#x}")
            words.extend(w)
        data = b"".join(x.to_bytes(4, "little") for x in words)
        with open(outfile, "wb") as fh:
            fh.write(data)
        bb.log(f"storage {STORAGE_BASE:#x}+{STORAGE_LEN:#x}: {len(data)} bytes, "
               f"{sum(1 for b in data if b != 0xFF)} not erased")
    finally:
        if started:
            bb.release_openocd()


if __name__ == "__main__":
    if sys.argv[1] == "measure":
        measure(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "dump":
        dump(sys.argv[2])
    else:
        sys.exit(__doc__)
