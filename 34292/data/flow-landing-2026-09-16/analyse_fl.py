#!/usr/bin/env python3
"""Summarise a FlowLandProbe dataflash log around the LAND touchdown.

Touchdown is when SITL truth stops moving vertically at ground level.
Position step is the growth of |EKF - truth| horizontal error (XKF1 core 0
against SIM2, aligned at LAND entry) from 1 s before touchdown to 5 s after.
"""
import math
import sys

from pymavlink import mavutil


def analyse(path, verbose=False):
    mlog = mavutil.mavlink_connection(path)
    sim, xkf, prfl, att, modes, arm, rfnd = [], [], [], [], [], [], []
    while True:
        m = mlog.recv_match(type=['SIM2', 'XKF1', 'PRFL', 'ATT', 'MODE', 'ARM', 'RFND'])
        if m is None:
            break
        t = m.TimeUS * 1e-6
        tp = m.get_type()
        if tp == 'SIM2':
            sim.append((t, m.PN, m.PE, m.PD, m.VN, m.VE))
        elif tp == 'XKF1' and m.C == 0:
            xkf.append((t, m.PN, m.PE))
        elif tp == 'PRFL' and m.C == 0:
            prfl.append((t, m))
        elif tp == 'ATT':
            att.append((t, math.hypot(m.DesRoll, m.DesPitch)))
        elif tp == 'MODE':
            modes.append((t, m.Mode))
        elif tp == 'ARM':
            arm.append((t, m.ArmState))
        elif tp == 'RFND':
            rfnd.append((t, m.Dist))
    t_land = None
    for t, md in modes:
        if md == 9:
            t_land = t
    if t_land is None or not sim:
        return {'tag': path.split('/')[-1], 'note': 'no LAND'}
    ground_pd = max(s[3] for s in sim)  # resting PD (least negative)
    t_td = None
    for s in sim:
        if s[0] > t_land and abs(s[3] - ground_pd) < 0.002 and math.hypot(s[4], s[5]) < 0.001:
            t_td = s[0]
            break
    t_disarm = None
    for t, st in arm:
        if st == 0 and t > t_land:
            t_disarm = t
            break

    def nearest(lst, t):
        return min(lst, key=lambda x: abs(x[0] - t))

    s0 = nearest(sim, t_land)
    x0 = nearest(xkf, t_land)
    off = (x0[1] - s0[1], x0[2] - s0[2])

    def err_at(t):
        s = nearest(sim, t)
        x = nearest(xkf, t)
        return math.hypot(x[1] - off[0] - s[1], x[2] - off[1] - s[2])

    res = {'tag': path.split('/')[-1].replace('.BIN', ''), 't_land': t_land, 't_td': t_td, 't_disarm': t_disarm}
    if t_td is None:
        return res
    pre = [s for s in sim if t_td - 0.5 <= s[0] < t_td]
    res['v_td'] = max(math.hypot(s[4], s[5]) for s in pre) if pre else float('nan')
    e_before = err_at(t_td - 1.0)
    e_after = max(err_at(t_td + dt * 0.1) for dt in range(0, 51))
    res['step'] = e_after - e_before
    lean = [a for t, a in att if t_td <= t <= t_td + 10]
    res['lean'] = max(lean) if lean else float('nan')
    res['disarm_after_td'] = None if t_disarm is None else t_disarm - t_td
    win = [(t, m) for t, m in prfl if t_td - 1.0 <= t <= t_td + 2.0]
    res['max_meas_flow'] = max((math.hypot(m.MX, m.MY) for t, m in win if m.F & 1), default=float('nan'))
    fused_big = [(t, m) for t, m in win if (m.F & 1) and max(abs(m.IX), abs(m.IY)) > 0.5 and max(m.TX, m.TY) < 1.0]
    res['fused_big_innov'] = len(fused_big)
    # height at which the measured flow first exceeds 3x the rate truth velocity over EKF range would give
    first = None
    for t, m in win:
        if not (m.F & 1) or t > t_td + 0.3:
            continue
        s = nearest(sim, t)
        v = math.hypot(s[4], s[5])
        pred = v / max(m.HG, 0.01)
        if math.hypot(m.MX, m.MY) > 3.0 * pred + 0.3:
            first = (t - t_td, nearest(rfnd, t)[1] if rfnd else float('nan'), m.RG)
            break
    res['phantom_start'] = first
    pre_sp = [(t, m) for t, m in prfl if t_td - 1.0 <= t <= t_td - 0.5]
    res['sp'] = pre_sp[-1][1].SP if pre_sp and hasattr(pre_sp[-1][1], 'SP') else float('nan')
    res['sv'] = pre_sp[-1][1].SV if pre_sp and hasattr(pre_sp[-1][1], 'SV') else float('nan')
    if verbose:
        print("   dt     F   IX      IY     TX    TY     MX      MY     HG    RG    RA   SP    SV")
        for t, m in win:
            sp = getattr(m, 'SP', float('nan'))
            sv = getattr(m, 'SV', float('nan'))
            print("  %6.2f %2d %7.3f %7.3f %5.2f %5.2f %7.3f %7.3f %5.3f %5.3f %4d %5.2f %5.3f" % (
                t - t_td, m.F, m.IX, m.IY, m.TX, m.TY, m.MX, m.MY, m.HG, m.RG, m.RA, sp, sv))
    return res


def fmt(r):
    if 't_td' not in r or r.get('t_td') is None:
        return "%-24s %s" % (r['tag'], r.get('note', 'no touchdown found'))
    ps = r['phantom_start']
    ps_s = "-" if ps is None else "dt=%.2f rfnd=%.3f rg=%.3f" % ps
    return "%-24s disarm=%-6s v_td=%.2f step=%.2f lean=%.1f maxflow=%.2f fusedbig=%d sigP=%.2f sigV=%.3f phantom:%s" % (
        r['tag'], "no" if r['disarm_after_td'] is None else "%.1fs" % r['disarm_after_td'],
        r['v_td'], r['step'], r['lean'], r['max_meas_flow'], r['fused_big_innov'], r.get('sp', float('nan')), r.get('sv', float('nan')), ps_s)


if __name__ == '__main__':
    verbose = '-v' in sys.argv
    for p in [a for a in sys.argv[1:] if a != '-v']:
        print(fmt(analyse(p, verbose)))
