"""Measure the GPS receiver's RF environment through ArduPilot's serial passthrough.
gpsrf.py COMn secs out_prefix [gps_baud]

Joins USB to the GPS UART (SERIAL_PASS1 0, SERIAL_PASS2 2), then polls the
u-blox receiver directly once a second for:
  MON-RF   jamming state, CW suppression, noise per ms, AGC
  NAV-SAT  satellites tracked and their C/N0
  MON-SPAN the RF spectrum (every 5 s)
NAV-PVT, which ArduPilot already has the receiver send, gives fix type and
satellites used. Writes out_prefix_rf.csv (one row a second) and
out_prefix_span.csv (one row per spectrum).

Only polls are sent, so the receiver's configuration is not changed.
With USB as the first port, the firmware runs the GPS UART at whatever baud
the PC opens USB at, so USB is opened at the GPS's own rate (default 230400).
Passthrough ends by itself SERIAL_PASSTIMO (15 s) after the last poll, and the
firmware resets SERIAL_PASS2 to -1. MAVLink on USB then stays deaf until a
reboot: the passthrough re-opened the port from the timer thread, which the
ChibiOS UART driver then treats as the port's owner."""
import struct
import sys
import time

import serial
from pymavlink import mavutil

port, secs, prefix = sys.argv[1], float(sys.argv[2]), sys.argv[3]
gps_baud = int(sys.argv[4]) if len(sys.argv) > 4 else 230400


def mav_param(m, name, value=None):
    if value is not None:
        m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value),
                             mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    for _ in range(3):
        m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
        t0 = time.time()
        while time.time() - t0 < 2:
            msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.5)
            if msg is not None and msg.param_id == name:
                return msg.param_value
    return None


def ubx(cls, mid, payload=b''):
    body = struct.pack('<BBH', cls, mid, len(payload)) + payload
    a = b = 0
    for c in body:
        a = (a + c) & 0xFF
        b = (b + a) & 0xFF
    return b'\xb5\x62' + body + bytes([a, b])


def frames(buf):
    """Yield (cls, id, payload) from buf, return the unconsumed tail."""
    out = []
    i = 0
    while True:
        j = buf.find(b'\xb5\x62', i)
        if j < 0 or len(buf) - j < 8:
            return out, buf[j:] if j >= 0 else b''
        cls, mid, n = struct.unpack_from('<BBH', buf, j + 2)
        if n > 2000:
            i = j + 2
            continue
        if len(buf) - j < 8 + n:
            return out, buf[j:]
        a = b = 0
        for c in buf[j + 2:j + 6 + n]:
            a = (a + c) & 0xFF
            b = (b + a) & 0xFF
        if buf[j + 6 + n] == a and buf[j + 7 + n] == b:
            out.append((cls, mid, bytes(buf[j + 6:j + 6 + n])))
            i = j + 8 + n
        else:
            i = j + 2


# set up the passthrough over MAVLink
m = mavutil.mavlink_connection(port, baud=115200)
m.wait_heartbeat(timeout=10)
p1 = mav_param(m, 'SERIAL_PASS1', 0)
p2 = mav_param(m, 'SERIAL_PASS2', 2)
print('SERIAL_PASS1 %s SERIAL_PASS2 %s' % (p1, p2), flush=True)
if p1 is None or p2 is None or int(p1) != 0 or int(p2) != 2:
    sys.exit('passthrough parameters did not take')
m.close()
time.sleep(1.5)

s = serial.Serial(port, gps_baud, timeout=0.05)
nbytes = nframes = 0
buf = b''
state = {'fix': None, 'numSV': None, 'rf': None, 'sat': None}
t0 = time.time()
last_poll = last_span = 0.0
nrf = nspan = 0
with open(prefix + '_rf.csv', 'w') as frf, open(prefix + '_span.csv', 'w') as fsp:
    frf.write('t_s,fixType,numSV_used,jamState,cwSupp,noisePerMS,agcCnt,antStatus,sv_tracked,sv_cno_gt0,cno_max,cno_top4_mean\n')
    fsp.write('t_s,center_Hz,span_Hz,res_Hz,pga_dB,bins_dB...\n')
    while time.time() - t0 < secs:
        now = time.time() - t0
        if now - last_poll >= 1.0:
            last_poll = now
            s.write(ubx(0x0A, 0x38) + ubx(0x01, 0x35))  # MON-RF, NAV-SAT polls
            if now - last_span >= 5.0:
                last_span = now
                s.write(ubx(0x0A, 0x31))  # MON-SPAN poll
            if state['rf'] is not None:
                rf, sat = state['rf'], state['sat'] or (0, 0, 0, 0.0)
                frf.write('%.1f,%s,%s,%d,%d,%d,%d,%d,%d,%d,%d,%.1f\n' % ((now, state['fix'], state['numSV']) + rf + sat))
                frf.flush()
                print('%5.0f s fix %s used %s | jam %d cw %3d noise %3d agc %4d ant %d | tracked %d cno>0 %d max %d top4 %.1f' % (
                    (now, state['fix'], state['numSV']) + rf + sat), flush=True)
                nrf += 1
        chunk = s.read(4096)
        nbytes += len(chunk)
        buf += chunk
        got, buf = frames(buf)
        nframes += len(got)
        for cls, mid, p in got:
            if (cls, mid) == (0x01, 0x07) and len(p) >= 92:  # NAV-PVT
                state['fix'], state['numSV'] = p[20], p[23]
            elif (cls, mid) == (0x0A, 0x38) and len(p) >= 4 + 24:  # MON-RF block 0
                flags, ant = p[5], p[6]
                noise, agc = struct.unpack_from('<HH', p, 16)
                state['rf'] = (flags & 3, p[20], noise, agc, ant)
            elif (cls, mid) == (0x01, 0x35) and len(p) >= 8:  # NAV-SAT
                n = p[5]
                cnos = sorted((p[8 + 12 * k + 2] for k in range(n) if 8 + 12 * k + 12 <= len(p)), reverse=True)
                pos = [c for c in cnos if c > 0]
                top = pos[:4]
                state['sat'] = (n, len(pos), cnos[0] if cnos else 0, sum(top) / len(top) if top else 0.0)
            elif (cls, mid) == (0x0A, 0x31) and len(p) >= 4 + 272:  # MON-SPAN block 0
                spec = p[4:4 + 256]
                span, res, center = struct.unpack_from('<III', p, 4 + 256)
                pga = p[4 + 268]
                db = [v * 0.25 for v in spec]
                fsp.write('%.1f,%d,%d,%d,%d,%s\n' % (now, center, span, res, pga, ','.join('%.2f' % v for v in db)))
                fsp.flush()
                nspan += 1
                med = sorted(db)[128]
                peaks = sorted(range(256), key=lambda k: db[k], reverse=True)[:4]
                l1 = int(round((1575.42e6 - center) * 256 / span + 128)) if span else -1
                desc = ', '.join('%.2f MHz %+.1f dB' % ((center + span * (k - 128) / 256) / 1e6, db[k] - med) for k in peaks)
                l1s = ' | L1 bin %+.1f dB' % (db[l1] - med) if 0 <= l1 < 256 else ''
                print('        span: centre %.2f MHz, %.1f MHz wide, pga %d dB, peaks above median: %s%s' % (
                    center / 1e6, span / 1e6, pga, desc, l1s), flush=True)
s.close()
print('%d bytes, %d UBX frames, %d RF rows, %d spectra.' % (nbytes, nframes, nrf, nspan))
print('Passthrough ends 15 s after the last poll; MAVLink on USB then needs a reboot.')
