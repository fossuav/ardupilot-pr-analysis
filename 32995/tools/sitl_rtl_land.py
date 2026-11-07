"""SITL A/B: RTL's landing descent from 22 m under different vertical
waypoint settings. Uses ~/github/ardupilot-master's SITL Copter binary.
usage: python3 sitl_rtl_land.py OUTDIR
"""
import os
import subprocess
import sys
import time

from pymavlink import mavutil

AP = os.path.expanduser('~/github/ardupilot-master')
BIN = AP + '/build/sitl/bin/arducopter'
OUT = sys.argv[1]
INST = 7
PORT = 5760 + 10 * INST

COMMON = {'RTL_ALT_M': 20, 'RTL_LOIT_TIME': 1000, 'LAND_SPD_MS': 0.5, 'LAND_ALT_LOW_M': 10,
          'WP_SPD_UP': 5, 'LAND_SPD_HIGH_MS': 0}
CASES = [
    ('A log 9: WP_ACC_Z 10, WP_SPD_DN 10', {'WP_ACC_Z': 10, 'WP_SPD_DN': 10}),
    ('B defaults: WP_ACC_Z 1, WP_SPD_DN 1.5', {'WP_ACC_Z': 1, 'WP_SPD_DN': 1.5}),
    ('C WP_ACC_Z 1, WP_SPD_DN 10', {'WP_ACC_Z': 1, 'WP_SPD_DN': 10}),
    ('D WP_ACC_Z 10, WP_SPD_DN 1.5', {'WP_ACC_Z': 10, 'WP_SPD_DN': 1.5}),
    ('E log 9 + LAND_SPD_HIGH_MS 2', {'WP_ACC_Z': 10, 'WP_SPD_DN': 10, 'LAND_SPD_HIGH_MS': 2}),
]


def set_param(m, name, value):
    for _ in range(5):
        m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value),
                             mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=2)
        while msg is not None and msg.param_id != name:
            msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=2)
        if msg is not None and abs(msg.param_value - value) < 1e-3:
            return True
    print(f'    could not set {name}')
    return False


def run(label, params):
    wd = os.path.join(OUT, label.split()[0])
    os.makedirs(wd, exist_ok=True)
    p = subprocess.Popen([BIN, '--model', 'quad', '--speedup', '10', '-w', '-I', str(INST),
                          '--defaults', AP + '/Tools/autotest/default_params/copter.parm',
                          '--home', '51.7095544,-0.6366983,118.5,0'],
                         cwd=wd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        m = mavutil.mavlink_connection(f'tcp:127.0.0.1:{PORT}', source_system=250)
        m.wait_heartbeat(timeout=60)
        m.mav.request_data_stream_send(m.target_system, m.target_component,
                                       mavutil.mavlink.MAV_DATA_STREAM_ALL, 20, 1)
        for k, v in {**COMMON, **params}.items():
            set_param(m, k, v)
        t_end = time.time() + 180
        while time.time() < t_end:
            m.set_mode('GUIDED')
            m.arducopter_arm()
            hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=2)
            if hb and hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
                break
            time.sleep(1)
        else:
            print(f'{label}: never armed')
            return
        m.mav.command_long_send(m.target_system, m.target_component,
                                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 22)
        while True:
            g = m.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5)
            if g and g.relative_alt > 21500:
                break
        t0 = time.time()
        while time.time() - t0 < 1.0:
            m.recv_match(blocking=True, timeout=1)
        m.set_mode('RTL')
        rows = []
        t_end = time.time() + 120
        while time.time() < t_end:
            msg = m.recv_match(type=['GLOBAL_POSITION_INT', 'HEARTBEAT'], blocking=True, timeout=5)
            if msg is None:
                continue
            if msg.get_type() == 'GLOBAL_POSITION_INT':
                rows.append((msg.time_boot_ms * 1e-3, msg.relative_alt * 1e-3, msg.vz * 1e-2))
            elif not msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED and rows:
                break
        # descent speed at each height crossing, and at contact
        out = []
        for h in (15, 10, 5, 2, 1, 0.3):
            v = next((r[2] for r in rows if r[1] <= h), float('nan'))
            out.append(f'{h:>4} m: {v:4.1f}')
        tc = next((r[0] for r in rows if r[1] <= 0.3), None)
        t10 = next((r[0] for r in rows if r[1] <= 10), None)
        tl = next((r[0] for r in rows if r[1] <= 21 and r[2] > 0.2), None)
        print(f'{label:38s} descent m/s at  ' + '  '.join(out) +
              (f'   22->0.3 m {tc - tl:5.1f} s, 10->0.3 m {tc - t10:5.1f} s' if tc and tl and t10 else ''))
    finally:
        p.terminate()
        p.wait(timeout=10)


for label, params in CASES:
    run(label, params)
