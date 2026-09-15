#!/usr/bin/env python3
"""acro-exit transient in the AccelBiasLearningInhibitedInAcro flight"""
import sys
import numpy as np
from pymavlink import DFReader
for path in sys.argv[1:]:
    r = DFReader.DFReader_binary(path)
    modes, az, alt, pd = [], [], [], []
    while True:
        m = r.recv_match(type=['MODE', 'XKF2', 'SIM2', 'XKF1'])
        if m is None:
            break
        t = m.TimeUS * 1e-6
        ty = m.get_type()
        if ty == 'MODE':
            modes.append((t, m.Mode))
        elif ty == 'XKF2' and m.C == 0:
            az.append((t, m.AZ))
        elif ty == 'XKF1' and m.C == 0:
            pd.append((t, m.PD))
        elif ty == 'SIM2':
            alt.append((t, -m.PD))
    az, alt, pd = np.array(az), np.array(alt), np.array(pd)
    t_in = [t for t, md in modes if md == 1][0]
    t_out = [t for t, md in modes if md == 2 and t > t_in][0]
    post = az[(az[:, 0] > t_out) & (az[:, 0] < t_out + 20)]
    ipk = post[:, 1].argmax()
    a0 = np.interp(t_out, alt[:, 0], alt[:, 1])
    w = alt[(alt[:, 0] > t_out) & (alt[:, 0] < t_out + 20)]
    err = pd[:, 1] + np.interp(pd[:, 0], alt[:, 0], alt[:, 1])
    ref = err[(pd[:, 0] > t_in - 5) & (pd[:, 0] < t_in)].mean()
    e_exit = np.interp(t_out, pd[:, 0], err) - ref
    settle = next((t - t_out for t, a in post if abs(a - 0.5) < 0.05 and t - t_out > post[ipk, 0] - t_out), float('nan'))
    print("%s: AZ at exit %.2f, peak %.2f at +%.1fs, within 0.05 of 0.5 by +%.1fs; "
          "hgt err at exit %.2f m; truth alt drop in 20s alt hold %.1f m (min %.1f from %.1f)" %
          (path.split('/')[-1], np.interp(t_out, az[:, 0], az[:, 1]), post[ipk, 1], post[ipk, 0] - t_out,
           settle, e_exit, a0 - w[:, 1].min(), w[:, 1].min(), a0))
