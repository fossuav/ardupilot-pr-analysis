import sys, math
from pymavlink import mavutil
for f in sys.argv[1:]:
    m=mavutil.mavlink_connection(f)
    prev=None; trans=[]; pos=[]; sim=[]; x1=[]; ofs=[]
    while True:
        r=m.recv_match(type=['XKF1','XKF4','SIM','POS'])
        if r is None: break
        t=r.get_type(); ts=r.TimeUS*1e-6
        if t=='SIM': sim.append((ts,r.Lat,r.Lng)); continue
        if t=='POS': pos.append((ts,r.Lat,r.Lng)); continue
        if r.C!=0: continue
        if t=='XKF4':
            if prev is not None and r.AID!=prev: trans.append((ts,prev,r.AID))
            prev=r.AID
            ofs.append((ts,r.OFN,r.OFE))
    def near(arr,t): return min(arr,key=lambda a: abs(a[0]-t))
    def err(t):
        p=near(pos,t); s=near(sim,t)
        return math.hypot((p[1]-s[1])*111319.5,(p[2]-s[2])*111319.5*math.cos(math.radians(s[1])))
    print(f.split('/')[-1], [(round(a,1),b,c) for a,b,c in trans])
    rel=[a for a in trans if a[2]==2][-1][0]; back=[a for a in trans if a[1]==2 and a[2]==0][-1][0]
    for label,tt in [('rel-0.5',rel-0.5),('rel+0.5',rel+0.5),('rel+3',rel+3),('back-0.3',back-0.3),('back+1',back+1)]:
        print('  %s t=%.1f EKF pos error vs truth %.1f m' % (label,tt,err(tt)))
    o=near(ofs,back+0.3); print('  reset delta on return to GPS OFN %.1f OFE %.1f' % (o[1],o[2]))
