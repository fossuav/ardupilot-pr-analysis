"""Measure the load PEAK after a measurement start, over several boots (run with Windows Python).

The first threads.txt read of a boot starts the measurement and clears the peak.
The second read, 4 s later, holds whatever the start left in the peak, and the
third is a control over a window with no start in it. The board stays disarmed.

usage: peak_session.py TAG HASH BOOTS
"""
import os
import re
import time

import ab_session as a

TAG, HASH, BOOTS = a.sys.argv[1], a.sys.argv[2], int(a.sys.argv[3])
OUT = os.path.join(a.BASE, "peak")
os.makedirs(OUT, exist_ok=True)
PAT = re.compile(r"C0 LOAD=\s*([\d.]+)% PEAK=\s*([\d.]+)% C1 LOAD=\s*([\d.]+)% PEAK=\s*([\d.]+)%")


def read(m, name):
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        os.remove(path)
    f = a.MAVFTP(m, m.target_system, m.target_component)
    f.cmd_get(["@SYS/threads.txt", path])
    f.process_ftp_reply("get", timeout=20)
    x = PAT.search(open(path, errors="replace").readline())
    return [float(v) for v in x.groups()] if x else None


m = a.connect()
v = a.request(m, 148, "AUTOPILOT_VERSION")
git = bytes(v.flight_custom_version[:8]).decode(errors="replace").rstrip("\0")
if git != HASH:
    a.sys.exit(f"board runs {git}, wanted {HASH}")
for boot in range(BOOTS):
    m = a.reboot(m)
    st = a.request(m, 2, "SYSTEM_TIME")
    up = st.time_boot_ms * 0.001 if st else 0
    if up < 15:
        time.sleep(15 - up)
    first = read(m, f"{TAG}_{boot}_1.txt")
    time.sleep(4)
    second = read(m, f"{TAG}_{boot}_2.txt")
    time.sleep(4)
    third = read(m, f"{TAG}_{boot}_3.txt")
    print(f"RESULT {TAG} boot {boot}: first {first} second {second} third {third}", flush=True)
m.close()
