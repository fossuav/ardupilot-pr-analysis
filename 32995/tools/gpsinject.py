"""Turn on the u-blox receiver's MON-RF output so ArduPilot logs it as UBX1/UBX2.
gpsinject.py COMn [epochs]

Sends UBX through ArduPilot's GPS_RTCM_DATA injection, which writes the bytes
to the GPS UART unchanged:
  1. a MON-VER poll; the reply makes ArduPilot print "u-blox ... HW: ... SW:",
     which shows the injection reaches the receiver
  2. CFG-VALSET to the RAM layer only: CFG-MSGOUT-UBX_MON_RF_UART1 = epochs
     (default 5, so 1 Hz at a 5 Hz navigation rate)
The setting lasts until the receiver loses power. Run it once ArduPilot has
detected and configured the GPS (about 20 s after boot)."""
import struct
import sys
import time

from pymavlink import mavutil

port = sys.argv[1]
epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
CFG_MSGOUT_UBX_MON_RF_UART1 = 0x2091035A


def ubx(cls, mid, payload=b''):
    body = struct.pack('<BBH', cls, mid, len(payload)) + payload
    a = b = 0
    for c in body:
        a = (a + c) & 0xFF
        b = (b + a) & 0xFF
    return b'\xb5\x62' + body + bytes([a, b])


def inject(m, data):
    assert len(data) <= 180
    m.mav.gps_rtcm_data_send(0, len(data), data.ljust(180, b'\0'))


m = mavutil.mavlink_connection(port, baud=115200)
m.wait_heartbeat(timeout=10)

inject(m, ubx(0x0A, 0x04))  # MON-VER poll
seen = False
t0 = time.time()
while time.time() - t0 < 5:
    msg = m.recv_match(type='STATUSTEXT', blocking=True, timeout=0.5)
    if msg is not None and 'u-blox' in msg.text:
        print('reply via ArduPilot: %s' % msg.text)
        seen = True
        break
if not seen:
    sys.exit('no MON-VER reply seen; injection did not reach the receiver')

valset = struct.pack('<BBBB', 0, 0x01, 0, 0) + struct.pack('<IB', CFG_MSGOUT_UBX_MON_RF_UART1, epochs)
inject(m, ubx(0x06, 0x8A, valset))
print('sent CFG-VALSET (RAM): MON-RF every %d navigation epochs' % epochs)
