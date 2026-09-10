#!/usr/bin/env python3
"""Resolve a flight log named in REPLAY_LOGS.md to a path on this machine.

Log file names are stable - a log is never renamed - but where they sit
differs per machine, and bare names collide (log66.bin exists under several
campaigns). So a log is identified here by its name plus a fingerprint taken
from its own contents, and this finds it by searching the roots in
AP_LOG_ROOTS (colon-separated) and confirming the fingerprint.

    export AP_LOG_ROOTS=<log-root>:<support-root>
    ./find_log.py log7.bin --acc-id 3408138 --bootcnt 517
    ./find_log.py log308.bin                 # no fingerprint: lists candidates

--replayable also reports whether the log carries the Replay records (RFRH),
which is what decides if it can be run through build/sitl/tool/Replay at all.

Exit 0 when exactly one log matches, 2 when none, 3 when several.
"""
import argparse
import os
import sys


def roots():
    env = os.environ.get("AP_LOG_ROOTS", "")
    out = [p for p in env.split(":") if p.strip()]
    if not out:
        sys.stderr.write("AP_LOG_ROOTS is not set; set it to the "
                         "colon-separated roots your logs live under\n")
    return out


def candidates(name):
    hits = []
    for root in roots():
        for dirpath, _dirnames, filenames in os.walk(root):
            if name in filenames:
                hits.append(os.path.join(dirpath, name))
    return sorted(hits)


def fingerprint(path, want_replay=False):
    """Read the identifying parameters, and optionally look for Replay records.

    Stops as soon as it has what it needs; a flight log is large and the
    parameters are all near the front.
    """
    from pymavlink import mavutil
    mlog = mavutil.mavlink_connection(path)
    wanted = ("INS_ACC_ID", "STAT_BOOTCNT", "STAT_FLTTIME")
    found = {}
    replay = False
    scanned = 0
    types = ["PARM", "RFRH"] if want_replay else ["PARM"]
    while scanned < 400000:
        msg = mlog.recv_match(type=types)
        if msg is None:
            break
        scanned += 1
        if msg.get_type() == "RFRH":
            replay = True
            if len(found) == len(wanted):
                break
            continue
        if msg.Name in wanted:
            found[msg.Name] = msg.Value
            if len(found) == len(wanted) and not want_replay:
                break
    return found, replay


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="log file name, e.g. log7.bin")
    ap.add_argument("--acc-id", type=float, help="expected INS_ACC_ID")
    ap.add_argument("--bootcnt", type=float, help="expected STAT_BOOTCNT")
    ap.add_argument("--replayable", action="store_true",
                    help="also report whether the log carries Replay records")
    args = ap.parse_args()

    hits = candidates(args.name)
    if not hits:
        print("no %s under AP_LOG_ROOTS" % args.name)
        return 2

    if args.acc_id is None and args.bootcnt is None:
        for h in hits:
            print(h)
        if len(hits) > 1:
            print("\n%d candidates and no fingerprint given; pass --acc-id/--bootcnt"
                  % len(hits))
            return 3
        return 0

    matched = []
    for h in hits:
        fp, replay = fingerprint(h, args.replayable)
        ok = True
        if args.acc_id is not None and fp.get("INS_ACC_ID") != args.acc_id:
            ok = False
        if args.bootcnt is not None and fp.get("STAT_BOOTCNT") != args.bootcnt:
            ok = False
        if ok:
            matched.append((h, fp, replay))
        else:
            print("  rejected %s (INS_ACC_ID=%s STAT_BOOTCNT=%s)"
                  % (h, fp.get("INS_ACC_ID"), fp.get("STAT_BOOTCNT")))

    if not matched:
        print("no candidate matched the fingerprint")
        return 2
    for h, fp, replay in matched:
        line = h
        if args.replayable:
            line += "   replayable=%s" % ("yes" if replay else "NO")
        print(line)
    return 0 if len(matched) == 1 else 3


if __name__ == "__main__":
    sys.exit(main())
