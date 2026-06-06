#!/usr/bin/env python3
"""Forensic validation of the AC_Loiter drag/feed-forward fix against flight logs.

For a DataFlash log and time window this reconstructs the loiter drag-deceleration
term from the same inputs calc_desired_velocity() uses, and reports the
position-controller feed-forward (PSCN/PSCE DAN/DAE) and velocity-PID integrator
(PIDN/PIDE I) behaviour. The point is to test, against data:

  1. whether the EKF ground-speed limit collapsed (AID_RELATIVE/optical flow at low
     height), inflating drag_decel far above any plausible real aerodynamic drag, and
  2. whether the fix's deceleration is carried by the feed-forward (correct) or has to
     be wound into the velocity-PID I-term (the "papers over via I-term" claim).

Usage: forensic_drag_analysis.py <log.bin> <t0> <t1>
"""
import sys
import math
import numpy as np
from pymavlink import mavutil

GRAVITY = 9.80665
RNG_ON_GND = 0.1  # rngOnGnd approx (m); MAX(HAGL, rngOnGnd) in getEkfControlLimits


def load(path):
    mlog = mavutil.mavlink_connection(path)
    want = ['PSCN', 'PSCE', 'PIDN', 'PIDE', 'XKF5', 'PARM']
    d = {k: [] for k in want if k != 'PARM'}
    params = {}
    while True:
        m = mlog.recv_match(type=want)
        if m is None:
            break
        t = m.get_type()
        if t == 'PARM':
            params[m.Name] = m.Value
            continue
        if t == 'XKF5' and getattr(m, 'C', 0) != 0:
            continue
        d[t].append(m)
    return d, params


def arr(msgs, *fields):
    ts = np.array([m.TimeUS / 1e6 for m in msgs])
    cols = [np.array([getattr(m, f) for m in msgs]) for f in fields]
    return (ts, *cols)


def interp(t_grid, ts, vals):
    return np.interp(t_grid, ts, vals)


def compute(path, t0, t1):
    d, p = load(path)
    ang_max_deg = p.get('LOIT_ANG_MAX', 0.0)
    if ang_max_deg <= 0:
        ang_max_deg = 30.0
    loit_speed = p.get('LOIT_SPEED_MS', 12.5)
    flow_max = p.get('EK3_FLOW_MAX', 2.5)
    pilot_acc_max = GRAVITY * math.tan(math.radians(ang_max_deg))

    tn, dvn, vn, dpn, pn, dan, tan_ = arr(d['PSCN'], 'DVN', 'VN', 'DPN', 'PN', 'DAN', 'TAN')
    te, dve, ve, dpe, pe, dae, tae = arr(d['PSCE'], 'DVE', 'VE', 'DPE', 'PE', 'DAE', 'TAE')
    th, hagl = arr(d['XKF5'], 'HAGL')
    tin, in_i, in_ff = arr(d['PIDN'], 'I', 'FF')
    tie, ie_i, ie_ff = arr(d['PIDE'], 'I', 'FF')

    sel = (tn >= t0) & (tn <= t1)
    g = tn[sel]
    dvn, vn, dpn, pn, dan, tan_ = dvn[sel], vn[sel], dpn[sel], pn[sel], dan[sel], tan_[sel]
    dve_g, ve_g = interp(g, te, dve), interp(g, te, ve)
    dpe_g, pe_g = interp(g, te, dpe), interp(g, te, pe)
    dae_g, tae_g = interp(g, te, dae), interp(g, te, tae)
    hagl_g = interp(g, th, hagl)
    in_i_g, ie_i_g = interp(g, tin, in_i), interp(g, tie, ie_i)

    ekf_lim = max(flow_max - 1.0, 0.0) * np.maximum(hagl_g, RNG_ON_GND)
    gnd_lim = np.maximum(np.minimum(loit_speed, ekf_lim), 0.2)
    des_speed = np.hypot(dvn, dve_g)
    drag_decel = pilot_acc_max * des_speed / gnd_lim
    iterm_mag = np.hypot(in_i_g, ie_i_g)
    ff_mag = np.hypot(dan, dae_g)
    spd = np.hypot(vn, ve_g)
    dirn = np.where(spd > 1e-3, vn / np.maximum(spd, 1e-3), 0.0)
    dire = np.where(spd > 1e-3, ve_g / np.maximum(spd, 1e-3), 0.0)
    along_err = (pn - dpn) * dirn + (pe_g - dpe_g) * dire
    return dict(t=g - g[0], drag_decel=drag_decel, iterm=iterm_mag, ff=ff_mag,
                along_err=along_err, des_speed=des_speed, pilot_acc_max=pilot_acc_max)


def plot_compare(before, after, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 1, figsize=(11, 10), sharex=False)
    for r, (lbl, c) in zip((before, after), (('before fix (log276)', 'C3'), ('after fix (log278)', 'C0'))):
        pass
    rows = [('along-track position error (m)  -  + = ahead of target', 'along_err'),
            ('velocity-PID I-term magnitude (m/s^2)', 'iterm'),
            ('reconstructed drag_decel (m/s^2)  -  fix does not change this', 'drag_decel')]
    for i, (title, key) in enumerate(rows):
        ax[i].plot(before['t'], before[key], 'C3', lw=1.0, label='before fix (log276)')
        ax[i].plot(after['t'], after[key], 'C0', lw=1.0, label='after fix (log278)')
        ax[i].set_title(title, fontsize=10)
        ax[i].grid(True, alpha=0.3)
        ax[i].legend(loc='upper right', fontsize=8)
    ax[-1].set_xlabel('time since loiter start (s)')
    fig.suptitle('AC_Loiter drag/feed-forward fix: I-term abuse and overshoot removed; drag_decel root cause unchanged', fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print(f'wrote {out}')


def main():
    if sys.argv[1] == '--plot':
        # --plot out.png before.bin bt0 bt1 after.bin at0 at1
        out = sys.argv[2]
        b = compute(sys.argv[3], float(sys.argv[4]), float(sys.argv[5]))
        a = compute(sys.argv[6], float(sys.argv[7]), float(sys.argv[8]))
        plot_compare(b, a, out)
        return
    path, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    d, p = load(path)

    ang_max_deg = p.get('LOIT_ANG_MAX', 0.0)
    if ang_max_deg <= 0:
        ang_max_deg = 30.0  # 2/3 of lean max fallback not reconstructed; logs here set it
    loit_speed = p.get('LOIT_SPEED_MS', 12.5)
    flow_max = p.get('EK3_FLOW_MAX', 2.5)
    pilot_acc_max = GRAVITY * math.tan(math.radians(ang_max_deg))

    # position controller (low rate) is the analysis grid
    tn, dvn, vn, dpn, pn, dan, tan_ = arr(d['PSCN'], 'DVN', 'VN', 'DPN', 'PN', 'DAN', 'TAN')
    te, dve, ve, dpe, pe, dae, tae = arr(d['PSCE'], 'DVE', 'VE', 'DPE', 'PE', 'DAE', 'TAE')
    th, hagl = arr(d['XKF5'], 'HAGL')
    tin, in_i, in_ff = arr(d['PIDN'], 'I', 'FF')
    tie, ie_i, ie_ff = arr(d['PIDE'], 'I', 'FF')

    sel = (tn >= t0) & (tn <= t1)
    g = tn[sel]
    dvn, vn, dpn, pn, dan = dvn[sel], vn[sel], dpn[sel], pn[sel], dan[sel]
    tan_ = tan_[sel]
    dve_g = interp(g, te, dve); ve_g = interp(g, te, ve)
    dpe_g = interp(g, te, dpe); pe_g = interp(g, te, pe)
    dae_g = interp(g, te, dae); tae_g = interp(g, te, tae)
    hagl_g = interp(g, th, hagl)
    in_i_g = interp(g, tin, in_i); in_ff_g = interp(g, tin, in_ff)
    ie_i_g = interp(g, tie, ie_i); ie_ff_g = interp(g, tie, ie_ff)

    # reconstruct the EKF speed cap and drag term exactly as calc_desired_velocity does
    ekf_lim = max(flow_max - 1.0, 0.0) * np.maximum(hagl_g, RNG_ON_GND)
    gnd_lim = np.maximum(np.minimum(loit_speed, ekf_lim), 0.2)
    des_speed = np.hypot(dvn, dve_g)
    act_speed = np.hypot(vn, ve_g)
    drag_decel = pilot_acc_max * des_speed / gnd_lim

    ff_mag = np.hypot(dan, dae_g)               # commanded feed-forward accel magnitude
    tgt_mag = np.hypot(tan_, tae_g)             # total target accel magnitude
    iterm_mag = np.hypot(in_i_g, ie_i_g)        # velocity-PID integrator magnitude
    pidff_mag = np.hypot(in_ff_g, ie_ff_g)      # velocity-PID feed-forward magnitude

    # along-track position tracking error (positive = vehicle ahead of desired)
    perr_n = pn - dpn
    perr_e = pe_g - dpe_g
    # project onto instantaneous travel direction
    spd = np.hypot(vn, ve_g)
    dirn = np.where(spd > 1e-3, vn / np.maximum(spd, 1e-3), 0.0)
    dire = np.where(spd > 1e-3, ve_g / np.maximum(spd, 1e-3), 0.0)
    along_err = perr_n * dirn + perr_e * dire
    perr_mag = np.hypot(perr_n, perr_e)

    def st(name, a):
        print(f"  {name:28s} min={a.min():+7.3f} max={a.max():+7.3f} "
              f"mean={a.mean():+7.3f} P95|.|={np.percentile(np.abs(a),95):6.3f}")

    print(f"\n=== {path}  window {t0:.1f}-{t1:.1f}s ===")
    print(f"  params: LOIT_ANG_MAX={ang_max_deg:.0f}deg pilot_acc_max={pilot_acc_max:.2f} m/s^2  "
          f"LOIT_SPEED_MS={loit_speed:.1f}  EK3_FLOW_MAX={flow_max:.1f}")
    print(f"  samples on grid: {len(g)}")
    st("HAGL (m)", hagl_g)
    st("ekf gnd-speed cap (m/s)", ekf_lim)
    st("gnd_speed_limit used (m/s)", gnd_lim)
    st("desired speed (m/s)", des_speed)
    st("actual speed (m/s)", act_speed)
    st("RECON drag_decel (m/s^2)", drag_decel)
    st("FF accel cmd |DAN,DAE|", ff_mag)
    st("target accel |TAN,TAE|", tgt_mag)
    st("vel-PID I-term |IN,IE|", iterm_mag)
    st("vel-PID FF |FFN,FFE|", pidff_mag)
    st("pos err along-track (m)", along_err)
    st("pos err magnitude (m)", perr_mag)
    print(f"  drag_decel / pilot_acc_max  max ratio = {(drag_decel/pilot_acc_max).max():.2f}")
    print(f"  peak forward overshoot (max along-track pos err) = {along_err.max():+.3f} m")


if __name__ == '__main__':
    main()
