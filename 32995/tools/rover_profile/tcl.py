#!/usr/bin/env python3
"""OpenOCD TCL helper for the RPI_UAVFC bench (port 50001).

  tcl.py cmd "TCL COMMAND"...   run commands, print replies
  tcl.py dhcsr                  both cores' DHCSR (halted / lockup bits)
  tcl.py verify BIN BASE        compare flash at BASE with BIN at several offsets
  tcl.py release                poll off, clear C_DEBUGEN on both cores, shutdown
"""
import socket
import sys

SEP = b"\x1a"
DHCSR = 0xE000EDF0


def tcl(sock, cmd):
    sock.sendall(cmd.encode() + SEP)
    buf = b""
    while not buf.endswith(SEP):
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    return buf[:-1].decode(errors="replace").strip()


def main():
    s = socket.create_connection(("127.0.0.1", 50001), timeout=15)
    op = sys.argv[1]
    if op == "cmd":
        for c in sys.argv[2:]:
            print(f"> {c}\n{tcl(s, c)}")
    elif op == "dhcsr":
        for core in (0, 1):
            v = int(tcl(s, f"rp2350.cm{core} read_memory {DHCSR:#x} 32 1").split()[0], 16)
            print(f"core{core} DHCSR {v:#010x} halted={(v >> 17) & 1} lockup={(v >> 19) & 1} "
                  f"C_DEBUGEN={v & 1}")
    elif op == "verify":
        data = open(sys.argv[2], "rb").read()
        base = int(sys.argv[3], 0)
        bad = 0
        for off in (0, 0x400, 0x10000, 0x40000, 0x80000, 0x100000, len(data) - 256):
            off &= ~3
            n = min(64, (len(data) - off) // 4)
            words = [int(w, 16) for w in tcl(s, f"rp2350.cm0 read_memory {base + off:#x} 32 {n}").split()]
            want = [int.from_bytes(data[off + 4 * i:off + 4 * i + 4], "little") for i in range(n)]
            ok = words == want
            bad += not ok
            print(f"  {base + off:#x}: {n} words {'match' if ok else 'DIFFER'}")
        print("flash matches the image" if not bad else f"{bad} regions differ")
    elif op == "release":
        print(tcl(s, "poll off"))
        for core in (0, 1):
            tcl(s, f"rp2350.cm{core} write_memory {DHCSR:#x} 32 {{0xA05F0000}}")
            print(f"core{core} DHCSR now {tcl(s, f'rp2350.cm{core} read_memory {DHCSR:#x} 32 1')}")
        try:
            s.sendall(b"shutdown" + SEP)
        except OSError:
            pass
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
