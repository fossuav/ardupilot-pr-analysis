"""COM port <-> TCP bridge for the RPI_UAVFC bench (run with Windows Python).

Usage: python.exe bridge.py COM15 127.0.0.1 5771   (the Rover tools listen on 5771)

Keeps reopening the COM port across board reboots and keeps reconnecting to
the WSL-side listener, so each WSL tool can listen, do its work and exit.
Bytes arriving while nothing is connected are dropped.
"""
import socket
import sys
import time

import serial

port, host, tcp_port = sys.argv[1], sys.argv[2], int(sys.argv[3])


def open_serial():
    while True:
        try:
            return serial.Serial(port, 115200, timeout=0.005)
        except serial.SerialException:
            time.sleep(0.5)


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


ser = open_serial()
log(f"opened {port}")
while True:
    try:
        s = socket.create_connection((host, tcp_port), timeout=1)
    except OSError:
        try:
            ser.reset_input_buffer()
        except serial.SerialException:
            ser.close()
            ser = open_serial()
            log(f"reopened {port}")
        time.sleep(0.2)
        continue
    log("client connected")
    s.settimeout(0.005)
    try:
        while True:
            try:
                d = ser.read(4096)
            except serial.SerialException:
                ser.close()
                ser = open_serial()
                log(f"reopened {port}")
                continue
            if d:
                s.sendall(d)
            try:
                r = s.recv(4096)
                if not r:
                    break
                ser.write(r)
            except socket.timeout:
                pass
    except OSError:
        pass
    s.close()
    log("client gone")
