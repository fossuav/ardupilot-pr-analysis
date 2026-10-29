"""Log Betaflight's raw ADC buffer over OpenOCD's TCL port while a load is switched.
pinlog.py secs out.csv [addr]
addr defaults to adcValues in the 2026-10-29 RASPBERRY_PI_UAVFC build
(0x20057778): slot 0 battery (GPIO46), slot 1 current (GPIO47).
Prints a 2 s mean of the current pin every 2 s so steps show live."""
import socket, sys, time

secs, out = float(sys.argv[1]), sys.argv[2]
addr = sys.argv[3] if len(sys.argv) > 3 else '0x20057778'
s = socket.create_connection(('127.0.0.1', 50001))


def cmd(c):
    s.sendall(c.encode() + b'\x1a')
    buf = b''
    while not buf.endswith(b'\x1a'):
        buf += s.recv(65536)
    return buf[:-1].decode(errors='replace').strip()


t0 = time.time()
win, last = [], t0
with open(out, 'w') as f:
    f.write('t_s,vbat_raw,curr_raw,curr_mV\n')
    while time.time() - t0 < secs:
        r = cmd('rp2350.cm0 read_memory %s 16 2' % addr).split()
        if len(r) == 2:
            v, c = int(r[0], 16), int(r[1], 16)
            t = time.time() - t0
            mv = c * 3300.0 / 4096
            f.write('%.2f,%d,%d,%.2f\n' % (t, v, c, mv))
            win.append(mv)
        if time.time() - last >= 2 and win:
            print('%6.1f s  current pin %6.2f mV (2 s mean of %d)' % (time.time() - t0, sum(win) / len(win), len(win)),
                  flush=True)
            win, last = [], time.time()
        time.sleep(0.1)
