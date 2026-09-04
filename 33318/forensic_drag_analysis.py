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

Usage: forensic_drag_analysis.py [--use-aglkf] <log.bin> <t0> <t1>

--use-aglkf reconstructs the speed cap from the 2-state AGL KF (XKF6.HAgl) instead
of terrainState (XKF5.HAGL). Use it for logs from builds that route the AGL KF
height into getEkfControlLimits (EK3_OPTIONS bit 3 / AglKfForOptflow); otherwise the
reconstructed cap will not match the firmware.
"""
import sys
import math
import numpy as np
from pymavlink import mavutil

GRAVITY = 9.80665
RNG_ON_GND = 0.1  # rngOnGnd approx (m); MAX(HAGL, rngOnGnd) in getEkfControlLimits


def load(path):
    mlog = mavutil.mavlink_connection(path)
    want = ['PSCN', 'PSCE', 'PIDN', 'PIDE', 'XKF5', 'XKF6', 'PARM']
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
        if t in ('XKF5', 'XKF6') and getattr(m, 'C', 0) != 0:
            continue
        d[t].append(m)
    return d, params


def arr(msgs, *fields):
    ts = np.array([m.TimeUS / 1e6 for m in msgs])
    cols = [np.array([getattr(m, f) for m in msgs]) for f in fields]
    return (ts, *cols)


def interp(t_grid, ts, vals):
    return np.interp(t_grid, ts, vals)


def hagl_on_grid(d, g, use_aglkf):
    """Height-above-ground on the analysis grid, matching what the firmware feeds
    the flow speed cap. Default is XKF5.HAGL (terrainState - pd). With use_aglkf,
    use XKF6.HAgl (the 2-state AGL KF) where it is logged - it is only logged while
    the KF is valid, so where it is absent fall back to terrainState exactly as
    getEkfControlLimits does. Returns (hagl, label, aglkf_coverage_fraction)."""
    th, hagl5 = arr(d['XKF5'], 'HAGL')
    h5 = interp(g, th, hagl5)
    if not use_aglkf:
        return h5, 'XKF5.HAGL (terrainState)', 0.0
    if not d.get('XKF6'):
        return h5, 'XKF5.HAGL (--use-aglkf set but no XKF6 in log)', 0.0
    t6, h6 = arr(d['XKF6'], 'HAgl')
    h6g = interp(g, t6, h6)
    # mark grid points with an XKF6 sample within 0.5 s as KF-covered (valid)
    if len(t6) > 1:
        idx = np.clip(np.searchsorted(t6, g), 1, len(t6) - 1)
        gap = np.minimum(np.abs(g - t6[idx - 1]), np.abs(g - t6[idx]))
    else:
        gap = np.full_like(g, np.inf)
    covered = gap < 0.5
    return np.where(covered, h6g, h5), 'XKF6.HAgl (AGL KF)', float(np.mean(covered))


def compute(path, t0, t1, use_aglkf=False):
    d, p = load(path)
    ang_max_deg = p.get('LOIT_ANG_MAX', 0.0)
    if ang_max_deg <= 0:
        ang_max_deg = 30.0
    loit_speed = p.get('LOIT_SPEED_MS', 12.5)
    flow_max = p.get('EK3_FLOW_MAX', 2.5)
    pilot_acc_max = GRAVITY * math.tan(math.radians(ang_max_deg))

    tn, dvn, vn, dpn, pn, dan, tan_ = arr(d['PSCN'], 'DVN', 'VN', 'DPN', 'PN', 'DAN', 'TAN')
    te, dve, ve, dpe, pe, dae, tae = arr(d['PSCE'], 'DVE', 'VE', 'DPE', 'PE', 'DAE', 'TAE')
    tin, in_i, in_ff = arr(d['PIDN'], 'I', 'FF')
    tie, ie_i, ie_ff = arr(d['PIDE'], 'I', 'FF')

    sel = (tn >= t0) & (tn <= t1)
    g = tn[sel]
    dvn, vn, dpn, pn, dan, tan_ = dvn[sel], vn[sel], dpn[sel], pn[sel], dan[sel], tan_[sel]
    dve_g, ve_g = interp(g, te, dve), interp(g, te, ve)
    dpe_g, pe_g = interp(g, te, dpe), interp(g, te, pe)
    dae_g, tae_g = interp(g, te, dae), interp(g, te, tae)
    hagl_g, _, _ = hagl_on_grid(d, g, use_aglkf)
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
    # --use-aglkf: reconstruct the speed cap from the 2-state AGL KF (XKF6.HAgl)
    # instead of terrainState (XKF5.HAGL). Use for logs from builds that route the
    # AGL KF height into getEkfControlLimits (EK3_OPTIONS bit 3 / AglKfForOptflow).
    argv = list(sys.argv)
    use_aglkf = '--use-aglkf' in argv
    if use_aglkf:
        argv.remove('--use-aglkf')

    if argv[1] == '--plot':
        # --plot out.png before.bin bt0 bt1 after.bin at0 at1
        out = argv[2]
        b = compute(argv[3], float(argv[4]), float(argv[5]), use_aglkf)
        a = compute(argv[6], float(argv[7]), float(argv[8]), use_aglkf)
        plot_compare(b, a, out)
        return
    path, t0, t1 = argv[1], float(argv[2]), float(argv[3])
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
    tin, in_i, in_ff = arr(d['PIDN'], 'I', 'FF')
    tie, ie_i, ie_ff = arr(d['PIDE'], 'I', 'FF')

    sel = (tn >= t0) & (tn <= t1)
    g = tn[sel]
    dvn, vn, dpn, pn, dan = dvn[sel], vn[sel], dpn[sel], pn[sel], dan[sel]
    tan_ = tan_[sel]
    dve_g = interp(g, te, dve); ve_g = interp(g, te, ve)
    dpe_g = interp(g, te, dpe); pe_g = interp(g, te, pe)
    dae_g = interp(g, te, dae); tae_g = interp(g, te, tae)
    hagl_g, hagl_src, aglkf_cov = hagl_on_grid(d, g, use_aglkf)
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
    print(f"  cap height source: {hagl_src}" +
          (f"  (AGL KF covers {aglkf_cov*100:.0f}% of grid)" if use_aglkf else ""))
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
