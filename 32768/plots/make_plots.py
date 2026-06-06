#!/usr/bin/env python3
"""Regenerate the before/after plots for the PR #32768 analysis.

Run from the 32768/ directory:  python3 plots/make_plots.py
Reads the SITL BINs under data/ and writes PNGs to plots/.

All BINs are SITL autotest captures (ArduCopter, EKF3). "arm-only" is the
implemented PR design (reset the height datum once, at arm); "periodic" is the
explored alternative (reset every 10 s while disarmed), preserved on branch
pr-baro-drift-minimum-periodic-reset and as draft PR #33338.
"""
import os
from pymavlink import mavutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 32768/

def load(fn):
    m = mavutil.mavlink_connection(os.path.join(HERE, fn))
    arm1 = arm0 = None
    balt = None
    xk = []    # (t, estAlt=-PD, VD)  core 0
    rel = []   # (t, RelOriginAlt, baro)
    while True:
        msg = m.recv_match(blocking=False)
        if msg is None:
            break
        t = msg.get_type()
        if t == 'ARM':
            if msg.ArmState == 1 and arm1 is None:
                arm1 = msg.TimeUS/1e6
            if msg.ArmState == 0 and arm1 and arm0 is None:
                arm0 = msg.TimeUS/1e6
        elif t == 'CTUN':
            balt = getattr(msg, 'BAlt', None)
        elif t == 'XKF1' and getattr(msg, 'C', None) == 0:
            xk.append((msg.TimeUS/1e6, -msg.PD, msg.VD))
        elif t == 'POS':
            rel.append((msg.TimeUS/1e6, getattr(msg, 'RelOriginAlt', None), balt))
    return dict(arm1=arm1, arm0=arm0, xk=xk, rel=rel)

def az_series(fn):
    m = mavutil.mavlink_connection(os.path.join(HERE, fn))
    xs = []; ys = []
    while True:
        msg = m.recv_match(type=['XKF2'], blocking=False)
        if msg is None:
            break
        if getattr(msg, 'C', None) == 1:
            xs.append(msg.TimeUS/1e6); ys.append(msg.AZ)
    return xs, ys

# ---------- Plot A: arm-time reset clears drift + phantom velocity, no kick ----------
d = load('data/arm-only/barodrift_arm.BIN')
arm = d['arm1']
xk = [r for r in d['xk'] if arm-12 <= r[0] <= arm+6]
ts = [r[0]-arm for r in xk]; est = [r[1] for r in xk]; vd = [r[2] for r in xk]
relw = [r for r in d['rel'] if arm-12 <= r[0] <= arm+6]
bt = [r[0]-arm for r in relw]; baro = [r[2] for r in relw]
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True)
ax1.plot(bt, baro, color='tab:orange', lw=1.3, label='baro height (drifting; vehicle stationary)')
ax1.plot(ts, est, color='tab:blue', lw=1.6, label='EKF height estimate')
ax1.axvline(0, color='k', ls='--', lw=1, label='arm (datum reset)')
ax1.set_ylabel('height above origin (m)')
ax1.set_title('Arm-time reset: ~9 m of accumulated baro drift cleared in one sample')
ax1.legend(loc='center left', fontsize=8); ax1.grid(alpha=0.3)
ax2.plot(ts, vd, color='tab:red', lw=1.6, label='EKF velocity down (VD)')
ax2.axvline(0, color='k', ls='--', lw=1); ax2.axhline(0, color='gray', lw=0.6)
ax2.set_ylabel('velocity down (m/s)'); ax2.set_xlabel('time relative to arm (s)')
ax2.set_title('No kick: phantom -0.3 m/s (drift read as motion) removed, no transient (|VD|<0.02)')
ax2.legend(loc='upper right', fontsize=8); ax2.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots/A_arm_reset.png'), dpi=110)
print('A: post-arm |VD| max %.3f' % max(abs(v) for t, v in zip(ts, vd) if t > 0.5))

# ---------- Plot B: periodic reset corrupts height with ExternalNav source ----------
per = load('data/periodic/gpsvicon_FAIL.BIN')
ar = load('data/arm-only/gpsvicon_clean.BIN')
def rel_aligned(dd, lo, hi):
    a0 = dd['arm0']
    pts = [(r[0]-a0, r[1], r[2]) for r in dd['rel'] if a0+lo <= r[0] <= a0+hi]
    return [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
px, py, pb = rel_aligned(per, -14, 5)
ax_, ay, _ = rel_aligned(ar, -14, 5)
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(px, pb, color='tab:orange', lw=1.2, label='true height (baro), both runs ~identical')
ax.plot(ax_, ay, color='tab:green', lw=1.8, label='EKF height - arm-only (no periodic reset)')
ax.plot(px, py, color='tab:red', lw=1.8, label='EKF height - periodic reset (Plane-mimic)')
ax.axvline(0, color='k', ls='--', lw=1, label='disarm (periodic reset fires)')
ax.text(-5.8, 8.9, 'periodic reset fires at disarm ->\nreported height jumps to takeoff\naltitude (~9.5 m) while the vehicle\nis sitting on the ground',
        fontsize=8.5, ha='left', va='top', color='tab:red',
        bbox=dict(boxstyle='round', fc='white', ec='tab:red', alpha=0.95))
ax.set_xlabel('time relative to disarm (s)'); ax.set_ylabel('height above origin (m)')
ax.set_title('GPS off + ExternalNav (vicon) height source.\n'
             'resetHeightDatum has no guard for ExternalNav -> corrupts the height estimate.')
ax.legend(loc='lower left', fontsize=8); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots/B_gpsvicon.png'), dpi=110)
print('B: periodic final rel=%.2f, arm-only final rel=%.2f' % (py[-1], ay[-1]))

# ---------- Plot C: GPS-denied post-arm drift (periodic disturbs disarmed bias learning) ----------
ao = load('data/arm-only/barodrift_arm.BIN')
pg = load('data/periodic/guard_barodrift.BIN')
def arm_window(dd, lo, hi):
    a = dd['arm1']
    pts = [(r[0]-a, r[1], r[2]) for r in dd['xk'] if a+lo <= r[0] <= a+hi]
    return [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
aot, aoe, aov = arm_window(ao, -0.1, 3.0)
pgt, pge, pgv = arm_window(pg, -0.1, 3.0)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True)
ax1.axhline(0, color='gray', lw=0.6)
ax1.plot(aot, aoe, color='tab:green', lw=1.8, label='arm-only (no periodic reset)')
ax1.plot(pgt, pge, color='tab:red', lw=1.8, label='periodic reset (+ ExternalNav guard)')
ax1.axvline(0, color='k', ls='--', lw=1, label='arm')
ax1.set_ylim(-0.1, 0.3)
ax1.set_ylabel('EKF height (m)')
ax1.set_title('GPS-denied (indoor): post-arm altitude, baro drift already stopped before arm.\n'
              'Periodic reset degraded disarmed Z-bias learning -> estimate climbs after arm.')
ax1.legend(loc='upper left', fontsize=8); ax1.grid(alpha=0.3)
ax2.axhline(0, color='gray', lw=0.6)
ax2.plot(aot, aov, color='tab:green', lw=1.8, label='arm-only VD')
ax2.plot(pgt, pgv, color='tab:red', lw=1.8, label='periodic VD (growing = integrating bias error)')
ax2.axvline(0, color='k', ls='--', lw=1)
ax2.set_ylabel('velocity down (m/s)'); ax2.set_xlabel('time relative to arm (s)')
ax2.legend(loc='lower left', fontsize=8); ax2.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots/C_gps_denied_postarm.png'), dpi=110)
print('C: arm-only estAlt@+2s=%.3f periodic estAlt@+2s=%.3f'
      % ([e for t, e in zip(aot, aoe) if t >= 2][0], [e for t, e in zip(pgt, pge) if t >= 2][0]))

# ---------- Plot D: the velocity reset is what interrupts bias learning ----------
fx, fy = az_series('data/periodic/fullreset_bias.BIN')     # zero velocity.z -> slow
hx, hy = az_series('data/periodic/heightonly_bias.BIN')    # leave velocity.z -> normal
fig, ax = plt.subplots(figsize=(9, 5))
ax.axhline(0.7, color='gray', ls=':', lw=1, label='true injected bias (0.7)')
ax.plot(fx, fy, color='tab:red', lw=1.8, label='full reset - zero velocity.z (slow, ~0.56 @47s)')
ax.plot(hx, hy, color='tab:green', lw=1.8, label='height-only reset - leave velocity.z (~0.70 @44s)')
ax.set_xlim(0, 50); ax.set_ylim(0, 0.8)
ax.set_xlabel('time since boot (s)'); ax.set_ylabel('learned Z accel bias  XKF2.AZ (m/s/s)')
ax.set_title('GPS-denied on-ground bias learning with the periodic reset firing.\n'
             'Zeroing velocity.z erases the zero-velocity bias signal; re-datuming height only does not.')
ax.legend(loc='lower right', fontsize=8.5); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots/D_velocity_vs_bias.png'), dpi=110)
print('D: full max=%.3f height-only max=%.3f' % (max(fy), max(hy)))
