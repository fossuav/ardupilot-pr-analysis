import sys, bisect
from pymavlink import mavutil
m = mavutil.mavlink_connection(sys.argv[1])
sidd = {}; probe = []
while True:
    x = m.recv_match(type=['SIDD', 'TSID'])
    if x is None: break
    if x.get_type() == 'SIDD':
        if abs(x.Targ) > 1e-3:
            sidd.setdefault(round(x.Targ, 4), x.TimeUS)
    else:
        if abs(x.S) > 1e-3:
            probe.append((x.TimeUS, round(x.S, 4)))
lags = []; unmatched = 0
first = {}
for t, v in probe:
    if v in first: continue
    first[v] = t
for v, t in first.items():
    if v in sidd: lags.append((t - sidd[v]) / 1000.0)
    else: unmatched += 1
lags.sort()
n = len(lags)
print("%s: matched %d, unmatched %d, lag ms median %.2f p10 %.2f p90 %.2f" % (sys.argv[1].split('/')[-1], n, unmatched, lags[n//2], lags[n//10], lags[9*n//10]))
