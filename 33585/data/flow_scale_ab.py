import sys, math
from pymavlink import mavutil

def analyse(path, label):
    m = mavutil.mavlink_connection(path)
    rows = {"XKF1": [], "XKF4": [], "XKF5": [], "SIM2": [], "RCIN": [], "SIM": []}
    while True:
        msg = m.recv_match(type=list(rows), blocking=False)
        if msg is None:
            break
        d = msg.to_dict()
        if msg.get_type() in ("XKF1", "XKF4", "XKF5") and d.get("C", 0) != 0:
            continue
        rows[msg.get_type()].append(d)
    if not rows["SIM2"]:
        return None

    def at(series, t, field):
        best, bt = None, None
        for r in series:
            dt = abs(r["TimeUS"] - t)
            if bt is None or dt < bt:
                bt, best = dt, r[field]
        return best

    # legs: RCIN.C2 pushed forward
    legs, cur = [], None
    for r in rows["RCIN"]:
        fwd = r["C2"] < 1400
        if fwd and cur is None:
            cur = [r["TimeUS"], r["TimeUS"]]
        elif fwd:
            cur[1] = r["TimeUS"]
        elif cur is not None:
            if cur[1] - cur[0] > 5e6:
                legs.append(cur)
            cur = None
    if cur is not None and cur[1] - cur[0] > 5e6:
        legs.append(cur)

    ground = rows["SIM"][0]["Alt"] if rows["SIM"] else 0.0
    print("\n=== %s (%s): %d forward legs" % (label, path.split('/')[-1], len(legs)))
    for i, (t0, t1) in enumerate(legs):
        w0 = t1 - 4e6
        def mean(series, fn):
            v = [fn(r) for r in series if w0 <= r["TimeUS"] <= t1]
            return sum(v) / len(v) if v else float("nan")
        ekf_spd = mean(rows["XKF1"], lambda r: math.hypot(r["VN"], r["VE"]))
        true_spd = mean(rows["SIM2"], lambda r: math.hypot(r["VN"], r["VE"]))
        hagl = mean(rows["XKF5"], lambda r: r["HAGL"])
        true_agl = mean(rows["SIM"], lambda r: r["Alt"] - ground)
        # XKF5.NI is 100 x max(flowTestRatio), the innovation consistency ratio for the
        # flow observations fused by the main filter (Logging.cpp:197); >= 100 is a reject
        ni = [r["NI"] for r in rows["XKF5"] if t0 <= r["TimeUS"] <= t1]
        ofn = max(ni or [float("nan")]) / 100.0
        ofe = (sum(ni) / len(ni) / 100.0) if ni else float("nan")
        ss = [r["SS"] for r in rows["XKF4"] if t0 <= r["TimeUS"] <= t1]
        rel = all(v & (1 << 3) for v in ss)
        terr = all(v & (1 << 6) for v in ss)
        print("  leg %d  H_est %5.2f m  H_true %5.2f m  H ratio %5.2f | "
              "EKF spd %5.2f  true spd %5.2f  v ratio %5.2f | "
              "max flow innov ratio %.3f/%.3f | horiz_pos_rel always %s | terrain_alt always %s"
              % (i + 1, hagl, true_agl, hagl / true_agl if true_agl else float("nan"),
                 ekf_spd, true_spd, ekf_spd / true_spd if true_spd else float("nan"),
                 ofn, ofe, rel, terr))

for path, label in ((sys.argv[1], "CONTROL  scale x1"), (sys.argv[2], "PROVOKED scale x2")):
    analyse(path, label)
