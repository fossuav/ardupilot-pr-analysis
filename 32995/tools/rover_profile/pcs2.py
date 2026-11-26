#!/usr/bin/env python3
"""Sample both RP2350 cores' DWT PCSR alternately through OpenOCD's TCL port, without halting.

Usage: pcs2.py N OUTPREFIX     N samples per core; writes OUTPREFIX_c0.txt and OUTPREFIX_c1.txt
"""
import socket
import sys
import time

SEP = b"\x1a"
n, prefix = int(sys.argv[1]), sys.argv[2]


def tcl(sock, cmd):
    sock.sendall(cmd.encode() + SEP)
    buf = b""
    while not buf.endswith(SEP):
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    return buf[:-1].decode(errors="replace").strip()


s = socket.create_connection(("127.0.0.1", 50001), timeout=10)
cmds = [f"rp2350.cm{c} read_memory 0xE000101C 32 1" for c in (0, 1)]
t0 = time.time()
fh = [open(f"{prefix}_c{c}.txt", "w") for c in (0, 1)]
for c in (0, 1):
    fh[c].write(f"# core{c} n={n} start={time.strftime('%H:%M:%S')}\n")
for _ in range(n):
    for c in (0, 1):
        fh[c].write(tcl(s, cmds[c]) + "\n")
for f in fh:
    f.close()
print(f"pcs2: {n} samples per core in {time.time() - t0:.1f} s")
