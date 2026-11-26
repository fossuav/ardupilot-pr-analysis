"""XIP cache hit rate over fixed windows, read through OpenOCD's TCL port.

Usage: xipctr.py WINDOWS SECONDS TAG
Clears XIP_CTRL CTR_HIT/CTR_ACC (0x400C800C/0x400C8010, write any value to
clear), waits, reads both; both cores' XIP accesses together. Nothing in the
flight build reads or clears them unless the perf report or XIP profiler is on.
"""
import socket
import sys
import time

SEP = b"\x1a"
windows, secs, tag = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3]


def tcl(sock, cmd):
    sock.sendall(cmd.encode() + SEP)
    buf = b""
    while not buf.endswith(SEP):
        buf += sock.recv(65536)
    return buf[:-1].decode(errors="replace").strip()


s = socket.create_connection(("127.0.0.1", 50001), timeout=10)
rates, accs = [], []
for _ in range(windows):
    tcl(s, "rp2350.cm0 write_memory 0x400C800C 32 {0 0}")
    t0 = time.time()
    time.sleep(secs)
    vals = tcl(s, "rp2350.cm0 read_memory 0x400C800C 32 2").split()
    dt = time.time() - t0
    hit, acc = int(vals[0], 16), int(vals[1], 16)
    if acc == 0xFFFFFFFF:
        print("saturated; shorten the window")
    rates.append(100.0 * hit / acc if acc else 0.0)
    accs.append(acc / dt / 1e6)
mean = sum(rates) / len(rates)
sd = (sum((r - mean) ** 2 for r in rates) / max(len(rates) - 1, 1)) ** 0.5
print(f"{tag}: hit {mean:.2f}% (sd {sd:.2f}, min {min(rates):.2f}, max {max(rates):.2f}) "
      f"over {windows}x{secs:.0f}s; accesses {sum(accs) / len(accs):.1f} M/s; "
      f"misses {sum(a * (100 - r) / 100 for a, r in zip(accs, rates)) / len(accs):.2f} M/s")
