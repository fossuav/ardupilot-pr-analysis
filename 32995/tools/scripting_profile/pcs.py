"""Sample one RP2350 core's DWT PCSR through OpenOCD's TCL port without halting it.

Usage: pcs.py CORE N OUTFILE [HOST]     CORE 0 or 1; writes one hex PC per line.
Runs under WSL or Windows Python (plain sockets).
"""
import socket
import sys
import time

SEP = b"\x1a"
core, n, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
host = sys.argv[4] if len(sys.argv) > 4 else "127.0.0.1"


def tcl(sock, cmd):
    sock.sendall(cmd.encode() + SEP)
    buf = b""
    while not buf.endswith(SEP):
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    return buf[:-1].decode(errors="replace").strip()


s = socket.create_connection((host, 50001), timeout=10)
cmd = f"rp2350.cm{core} read_memory 0xE000101C 32 1"
t0 = time.time()
with open(out, "w") as fh:
    fh.write(f"# core{core} n={n} start={time.strftime('%H:%M:%S')}\n")
    for _ in range(n):
        fh.write(tcl(s, cmd) + "\n")
print(f"core{core}: {n} samples in {time.time() - t0:.1f} s -> {out}")
