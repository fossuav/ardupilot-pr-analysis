#!/usr/bin/env python3
"""headscan.py LOG: firmware, board and the height/ground effect parameters from a log's header"""
import os
import sys
from pymavlink import mavutil

WANT = ("RNGFND1_TYPE", "RNGFND1_ORIENT", "RNGFND1_MIN", "RNGFND1_MIN_CM", "EK3_RNG_USE_HGT", "EK3_OPTIONS",
        "EK3_GND_EFF_DZ", "EK3_SRC1_POSZ", "EK3_SRC1_VELXY", "TKOFF_GNDEFF_ALT", "TKOFF_GNDEFF_TMO",
        "GND_EFFECT_COMP", "GNDEFF_ALT", "GNDEFF_TMO", "BARO1_THST_SCALE", "BARO_THST_SCALE",
        "VALT_POS_EXPO", "EK3_ALT_M_NSE", "FLOW_TYPE", "STAT_BOOTCNT")
m = mavutil.mavlink_connection(sys.argv[1])
fw = []
p = {}
n = 0
while True:
    r = m.recv_match(type=["MSG", "PARM", "VER"])
    if r is None:
        break
    n += 1
    ty = r.get_type()
    if ty == "MSG" and len(fw) < 4 and ("V4." in r.Message or "H7" in r.Message or "ChibiOS" in r.Message):
        fw.append(r.Message)
    elif ty == "VER":
        fw.append("VER %s %s" % (getattr(r, "FWS", ""), getattr(r, "GH", "")))
    elif ty == "PARM" and r.Name in WANT and r.Name not in p:
        p[r.Name] = round(r.Value, 3)
    if n > 4000 and len(fw) >= 2:
        break
print(os.path.basename(sys.argv[1]))
print("  fw:", " | ".join(fw[:4]))
print("  ", p)
