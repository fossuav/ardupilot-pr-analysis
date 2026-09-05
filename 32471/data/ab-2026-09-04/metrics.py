#!/usr/bin/env python3
"""Read the A/B numbers out of the logs the harness probes produce.

    python3 metrics.py run_a.BIN run_b.BIN ...

Prints, per log: worst |EKF height - truth| over the window after arming, the
XKF2.AZ range across arming, XKF2.AZ at the arm instant, and the parameters
that identify which arm the log is.

The definitions are the ones ../../plots/make_plots.py uses, so numbers from
here and numbers on the plots are the same numbers:

- height error is (-(XKF1.PD - PD0)) - (SIM.Alt - Alt0), core 0, both series
  re-zeroed at the ARM event, so it measures drift accumulated during the
  climb rather than a difference in datum. Worst is max |.| over WINDOW_S.
- the accel bias is XKF2.AZ on core 0. On platform runs the value that matters
  is the one at arm: what the filter carries into a flight where the platform
  that produced it no longer exists.

Gotchas:

- Take the FIRST PARM record for each name, not the last. context_pop() at the
  end of a probe restores the parameters it set, and those restores are logged
  too, so last-wins reports every arm as running at the defaults - which looks
  exactly like a harness that silently failed to set anything.
- A log with no ARM event is not an arm of the A/B; the probes reboot twice and
  the small BINs either side are not the flight.
- Logs written without LOG_REPLAY=1 carry the replay message *formats* but no
  replay records. They plot fine and cannot be replayed. Check with
  `mavlogdump.py --types RFRH` before assuming a log is replayable.
"""
import sys

from pymavlink import mavutil

ARMED_EV = 10
WINDOW_S = 35.0
BIAS_BEFORE_S, BIAS_AFTER_S = 40.0, 25.0
IDENT = ('ACC_ZBIAS_LEARN', 'SIM_ACC_VRF_Z', 'INS_ACC_VRFB_Z',
         'SIM_PLAT_ACC_Z', 'SIM_BARO_GEFF_M', 'EK3_OGNM_TEST_SF')


def read(path):
    m = mavutil.mavlink_connection(path)
    t_arm, ekf, truth, az, parm = None, [], [], [], {}
    while True:
        msg = m.recv_match(type=['EV', 'XKF1', 'SIM', 'XKF2', 'PARM'])
        if msg is None:
            break
        if msg.get_type() == 'PARM':
            if msg.Name in IDENT and msg.Name not in parm:
                parm[msg.Name] = msg.Value
            continue
        t = msg.TimeUS * 1e-6
        if msg.get_type() == 'EV':
            if msg.Id == ARMED_EV and t_arm is None:
                t_arm = t
        elif msg.get_type() == 'XKF1' and msg.C == 0:
            ekf.append((t, msg.PD))
        elif msg.get_type() == 'XKF2' and msg.C == 0:
            az.append((t, msg.AZ))
        elif msg.get_type() == 'SIM':
            truth.append((t, msg.Alt))
    return t_arm, ekf, truth, az, parm


def sample(series, at):
    prev = None
    for (t, v) in series:
        if t > at:
            break
        prev = v
    return prev


def report(path):
    t_arm, ekf, truth, az, parm = read(path)
    tag = path.split('/')[-1]
    ident = " ".join("%s=%g" % (k, parm[k]) for k in IDENT if k in parm)
    if t_arm is None:
        print("%-20s no ARM event - not a flight log   %s" % (tag, ident))
        return
    pd0, alt0 = sample(ekf, t_arm), sample(truth, t_arm)
    errs = []
    for (t, pd) in ekf:
        dt = t - t_arm
        if 0 <= dt <= WINDOW_S:
            alt = sample(truth, t)
            if alt is not None:
                errs.append(abs((-(pd - pd0)) - (alt - alt0)))
    win = [v for (t, v) in az if -BIAS_BEFORE_S <= t - t_arm <= BIAS_AFTER_S]
    at_arm = sample(az, t_arm)
    print("%-20s worst|err|=%.3f m  AZ range=%.3f  AZ at arm=%+.4f  %s"
          % (tag,
             max(errs) if errs else float('nan'),
             (max(win) - min(win)) if win else float('nan'),
             at_arm if at_arm is not None else float('nan'),
             ident))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        report(p)
