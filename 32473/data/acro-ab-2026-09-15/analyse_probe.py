#!/usr/bin/env python3
"""Summarise accel bias and height error across the acro segment of a probe log."""
import sys
import numpy as np
from pymavlink import DFReader


def load(path):
    r = DFReader.DFReader_binary(path)
    global sim
    sim = []
    mode, xkf2, xkf1, sim2 = [], {0: [], 1: []}, {0: [], 1: []}, []
    while True:
        m = r.recv_match(type=['MODE', 'XKF2', 'XKF1', 'SIM2', 'SIM'])
        if m is None:
            break
        t = m.TimeUS * 1e-6
        ty = m.get_type()
        if ty == 'MODE':
            mode.append((t, m.Mode))
        elif ty == 'XKF2' and m.C in (0, 1):
            xkf2[m.C].append((t, m.AX, m.AY, m.AZ))
        elif ty == 'XKF1' and m.C in (0, 1):
            xkf1[m.C].append((t, m.PD, m.Roll, m.Pitch))
        elif ty == 'SIM2':
            sim2.append((t, m.PD))
        elif ty == 'SIM':
            sim.append((t, m.Roll, m.Pitch))
    return mode, {k: np.array(v) for k, v in xkf2.items()}, {k: np.array(v) for k, v in xkf1.items()}, np.array(sim2)


def at(arr, t, col):
    return float(np.interp(t, arr[:, 0], arr[:, col]))


def main(path):
    mode, xkf2, xkf1, sim2 = load(path)
    t_in = next(t for t, md in mode if md == 1)
    t_out = next(t for t, md in mode if md == 2 and t > t_in)
    out = {"log": path.split('/')[-1], "acro_s": round(t_out - t_in, 1)}
    for c in (0,):
        b = xkf2[c]
        presel = (b[:, 0] > t_in - 5) & (b[:, 0] < t_in)
        pre = b[presel][:, 1:].mean(axis=0) if presel.sum() else b[:5, 1:].mean(axis=0)
        inacro = b[(b[:, 0] >= t_in) & (b[:, 0] <= t_out)][:, 1:]
        dev = np.abs(inacro - pre).max(axis=0)
        end = b[b[:, 0] <= t_out][-1, 1:]
        post10 = np.array([at(b, t_out + 10, i) for i in (1, 2, 3)])
        post35 = np.array([at(b, t_out + 35, i) for i in (1, 2, 3)])
        fmt = lambda v: "%+.3f/%+.3f/%+.3f" % tuple(v)
        out["bias_pre"] = fmt(pre)
        out["bias_maxdev_acro"] = fmt(dev)
        out["bias_end_acro"] = fmt(end)
        out["bias_exit+10"] = fmt(post10)
        out["bias_exit+35"] = fmt(post35)
        k = xkf1[c]
        err = k[:, 1] - np.interp(k[:, 0], sim2[:, 0], sim2[:, 1])
        refsel = (k[:, 0] > t_in - 10) & (k[:, 0] < t_in)
        ref = err[refsel].mean() if refsel.sum() else err[:20].mean()
        err = err - ref
        def win(a, b_):
            sel = (k[:, 0] >= a) & (k[:, 0] <= b_)
            e = err[sel]
            return "mean|%.2f| max|%.2f|" % (np.abs(e).mean(), np.abs(e).max())
        out["hgt_err_acro"] = win(t_in, t_out)
        out["hgt_err_exit0-10"] = win(t_out, t_out + 10)
        out["hgt_err_exit10-35"] = win(t_out + 10, t_out + 35)
        sa = np.array(sim)
        sel = (k[:, 0] >= t_in) & (k[:, 0] <= t_out)
        kk = k[sel]
        def aerr(est, col):
            tru = np.interp(kk[:, 0], sa[:, 0], np.degrees(np.unwrap(np.radians(sa[:, col]))))
            return np.abs((est - tru + 180) % 360 - 180)
        re = aerr(kk[:, 2], 1)
        pe = aerr(kk[:, 3], 2)
        # only compare near-level samples, the euler angles fold through a flip
        lvl = (np.abs(kk[:, 2]) < 45) & (np.abs(kk[:, 3]) < 45)
        out["tilt_err_acro_lvl"] = "roll mean %.2f max %.2f, pitch mean %.2f max %.2f deg" % (
            re[lvl].mean(), re[lvl].max(), pe[lvl].mean(), pe[lvl].max())
    for key, val in out.items():
        print("%-18s %s" % (key, val))
    print()


for p in sys.argv[1:]:
    main(p)
