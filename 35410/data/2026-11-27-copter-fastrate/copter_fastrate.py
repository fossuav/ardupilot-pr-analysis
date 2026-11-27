#!/usr/bin/env python3
"""Copter fast-rate thread with oneshot motors, RPI_UAVFC on the bench bridge (127.0.0.1:5770)
and OpenOCD TCL on 50001. ESCs must be unpowered: refuses to arm above 5 V.

  copter_fastrate.py case LABEL OUTDIR [NAME=VALUE ...]
      set the params (and reboot) if any are given, then: boot texts and banner, 25 s disarmed
      collecting "Rate CPU" texts, SWD sampling of the motor slices, force-arm in STABILIZE,
      10 s armed with SWD sampling, force-disarm. Writes OUTDIR/LABEL.json.
  copter_fastrate.py set NAME=VALUE ...     set params and reboot
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/github/ardupilot-pr-analysis/32995/data/2026-11-26-buzzer-outputs"))
import buzz_bench as bb  # noqa: E402

MAV = bb.MAV
# motor outputs 1-4: (GPIO, slice, channel)
MOTORS = {1: (9, 4, "B"), 2: (8, 4, "A"), 3: (7, 3, "B"), 4: (6, 3, "A")}
OUTTOPAD = 1 << 9
SHOW = ["MOT_PWM_TYPE", "FSTRATE_ENABLE", "FSTRATE_DIV", "SCHED_LOOP_RATE", "INS_GYRO_RATE"]


def collect(m, secs, texts, extra=None):
    t_end = time.time() + secs
    while time.time() < t_end:
        msg = m.recv_match(type=["STATUSTEXT", "HEARTBEAT"], blocking=True, timeout=0.2)
        if msg is None:
            continue
        if msg.get_type() == "STATUSTEXT":
            texts.append([round(time.time(), 2), msg.text])
        elif extra is not None and msg.get_srcComponent() == m.target_component:
            extra["armed"] = bool(msg.base_mode & 128)


def sample_motors(t, secs):
    """sample the motor slices' counters and pads; the counter's spread shows the trigger interval"""
    ctr = {sl: [] for sl in (3, 4)}
    high = {o: 0 for o in MOTORS}
    n = 0
    t_end = time.time() + secs
    while time.time() < t_end:
        regs = t.rd(bb.PWM_BASE + 0x14 * 3, 10)
        st = t.rd(bb.IO_BANK0 + 8 * 6, 8)
        n += 1
        ctr[3].append(regs[2] & 0xFFFF)
        ctr[4].append(regs[7] & 0xFFFF)
        for o, (g, _, _) in MOTORS.items():
            if st[2 * (g - 6)] & OUTTOPAD:
                high[o] += 1
    out = {"samples": n, "slices": {}, "high": {o: round(high[o] / n, 4) for o in MOTORS}}
    for sl, c in ctr.items():
        c = sorted(c)
        r = bb.slice_regs(t, sl)
        out["slices"][sl] = {"ctr_max": c[-1], "ctr_p99": c[int(0.99 * (len(c) - 1))],
                             "ctr_p90": c[int(0.90 * (len(c) - 1))], "ctr_median": c[len(c) // 2], "regs": r}
        bb.log(f"  slice {sl}: TOP {r['top']:5d} DIV {r['div']:.3f} A {r['a_us']:.1f} B {r['b_us']:.1f} us; "
               f"CTR median {c[len(c) // 2]} p90 {out['slices'][sl]['ctr_p90']} p99 {out['slices'][sl]['ctr_p99']} "
               f"max {c[-1]}")
    bb.log(f"  pads high {out['high']}  n={n}")
    return out


def arm(m, on):
    m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                            1 if on else 0, 21196, 0, 0, 0, 0, 0)
    t0 = time.time()
    while time.time() - t0 < 3:
        a = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.5)
        if a and a.command == MAV.MAV_CMD_COMPONENT_ARM_DISARM:
            bb.log(f"  {'arm' if on else 'disarm'}: result {a.result}")
            return a.result
    return None


def battery_v(m):
    m.mav.command_long_send(m.target_system, m.target_component, MAV.MAV_CMD_REQUEST_MESSAGE, 0,
                            MAV.MAVLINK_MSG_ID_SYS_STATUS, 0, 0, 0, 0, 0, 0)
    s = m.recv_match(type="SYS_STATUS", blocking=True, timeout=5)
    return s.voltage_battery / 1000.0 if s else None


def set_and_reboot(pairs):
    m = bb.connect()
    bb.set_params(m, pairs)
    time.sleep(1)
    bb.reboot(m)
    time.sleep(25)


def case(label, outdir, pairs):
    os.makedirs(outdir, exist_ok=True)
    if pairs:
        set_and_reboot(pairs)
    res = {"label": label, "set": pairs}
    m = bb.connect()
    res["params"] = bb.get_params(m, SHOW)
    bb.log(f"  params {res['params']}")
    res["banner"] = bb.banner(m)
    for line in res["banner"]:
        if line.startswith("RCOut") or "Ardu" in line:
            bb.log(f"  text: {line}")
    vb = battery_v(m)
    res["battery_v"] = vb
    if vb is None or vb > 5.0:
        sys.exit(f"battery reads {vb} V: ESCs may be powered, not arming")
    texts = []
    bb.log("disarmed, 25 s")
    res["start_time"] = time.time()
    collect(m, 25, texts)
    started = False
    if not bb.openocd_running():
        bb.start_openocd(os.path.join(outdir, f"openocd_{label}.log"))
        started = True
    try:
        t = bb.Tcl()
        res["disarmed"] = sample_motors(t, 4)
        st = {}
        if arm(m, True) != 0:
            sys.exit("arm refused")
        res["arm_time"] = time.time()
        collect(m, 2, texts, st)
        res["armed"] = sample_motors(t, 5)
        collect(m, 2, texts, st)
        arm(m, False)
        res["disarm_time"] = time.time()
        collect(m, 3, texts, st)
    finally:
        if started:
            bb.release_openocd()
            try:
                os.remove(os.path.join(outdir, f"openocd_{label}.log"))
            except OSError:
                pass
    res["texts"] = texts
    m.close()
    phases = [("disarmed", res["start_time"], res["arm_time"]), ("armed", res["arm_time"], res["disarm_time"]),
              ("after", res["disarm_time"], 1e12)]
    for name, t0, t1 in phases:
        rate = [x[1] for x in texts if "Rate CPU" in x[1] and t0 <= x[0] < t1]
        span = (min(t1, texts[-1][0] if texts else t0) - t0) if texts else 0
        counts = {}
        for r in rate:
            counts[r] = counts.get(r, 0) + 1
        bb.log(f"  {name}: {len(rate)} Rate CPU texts over ~{span:.0f} s: {counts}")
        if rate:
            bb.log(f"    first {rate[0]!r}, last {rate[-1]!r}")
    with open(os.path.join(outdir, f"{label}.json"), "w") as fh:
        json.dump(res, fh, indent=1)


def parse(args):
    return [(a.split("=")[0], float(a.split("=")[1])) for a in args]


if __name__ == "__main__":
    if sys.argv[1] == "case":
        case(sys.argv[2], sys.argv[3], parse(sys.argv[4:]))
    elif sys.argv[1] == "set":
        set_and_reboot(parse(sys.argv[2:]))
    else:
        sys.exit(__doc__)
