"""Log ArduPilot's battery current and voltage at 10 Hz while a load is switched.
aplog.py COMn secs out.csv
Prints a 2 s mean of the current every 2 s so steps show live."""
import sys, time
from pymavlink import mavutil

port, secs, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
m = mavutil.mavlink_connection(port, baud=115200)
m.wait_heartbeat(timeout=10)
m.mav.command_long_send(m.target_system, m.target_component,
                        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, 1, 100000, 0, 0, 0, 0, 0)
t0 = time.time()
win, last = [], t0
with open(out, 'w') as f:
    f.write('t_s,current_A,voltage_V\n')
    while time.time() - t0 < secs:
        msg = m.recv_match(type='SYS_STATUS', blocking=True, timeout=1)
        if msg is None:
            continue
        t = time.time() - t0
        cur = msg.current_battery / 100.0
        f.write('%.2f,%.2f,%.3f\n' % (t, cur, msg.voltage_battery / 1000.0))
        win.append(cur)
        if time.time() - last >= 2 and win:
            print('%6.1f s  current %6.2f A (2 s mean of %d)' % (t, sum(win) / len(win), len(win)), flush=True)
            win, last = [], time.time()
# back to the default stream rate
m.mav.command_long_send(m.target_system, m.target_component,
                        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, 1, 0, 0, 0, 0, 0, 0)
