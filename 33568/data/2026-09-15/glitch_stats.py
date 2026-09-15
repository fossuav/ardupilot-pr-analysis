import sys, math
from pymavlink import mavutil
f=sys.argv[1]; t0=float(sys.argv[2]); t1=float(sys.argv[3])
m=mavutil.mavlink_connection(f)
prev=None; trans=[]; msgs={}; x1=[]; sim=[]; gps=[]
while True:
    r=m.recv_match(type=['XKF1','XKF4','SIM','MSG','GPS','POS'])
    if r is None: break
    t=r.get_type(); ts=r.TimeUS*1e-6
    if t=='MSG':
        if 'EKF3 IMU0' in r.Message and t0-5<ts<t1+40:
            k=r.Message.replace('EKF3 IMU0 ','')
            msgs[k]=msgs.get(k,0)+1
        continue
    if t=='SIM': sim.append((ts,r.Lat,r.Lng)); continue
    if t=='POS': gps.append((ts,r.Lat,r.Lng)); continue
    if t=='GPS': continue
    if r.C!=0: continue
    if t=='XKF4':
        if prev is not None and r.AID!=prev and t0-5<ts<t1+40: trans.append((round(ts,2),prev,r.AID))
        prev=r.AID
    else:
        x1.append((ts,r.VN,r.VE))
print('AID transitions', len(trans), trans[:20])
print('IMU0 texts', msgs)
# max EKF velocity error vs finite-diff truth not available; report max |VE|,|VN| in window
w=[a for a in x1 if t0<a[0]<t1+40]
print('max |V| in window %.2f' % max(math.hypot(a[1],a[2]) for a in w))
# horizontal error POS (EKF location) vs SIM truth at end of window
def near(arr,t):
    return min(arr,key=lambda a: abs(a[0]-t))
from math import radians, cos
for tt in [t0-1, t0+20, t0+40, t0+60, t1+5, t1+20, t1+38]:
    p=near(gps,tt); s=near(sim,tt)
    dn=(p[1]-s[1])*111319.5; de=(p[2]-s[2])*111319.5*cos(radians(s[1]))
    print('t=%.1f EKF-vs-truth N %.1f E %.1f' % (tt,dn,de))
