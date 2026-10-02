import sys
from pymavlink import mavutil
m=mavutil.mavlink_connection(sys.argv[1])
pts=[]
while True:
    x=m.recv_match(type='TMIX')
    if x is None: break
    pts.append((x.TimeUS*1e-6,x.Mix,x.Des))
# time spent strictly between 0.1 and 0.5 while rising toward desired
start=None
for t,mx,d in pts:
    if start is None and mx>0.11 and d>mx:
        start=t
    if start is not None and mx>=0.49:
        print("%s: n=%d rise 0.1->0.5 took %.3fs (%.2f/s)"%(sys.argv[1],len(pts),t-start,0.38/(t-start)))
        break
