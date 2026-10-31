#!/usr/bin/env python3
"""Add a throwaway ProbeStaticYawSet2 test to a scratch tree's arducopter.py:
boot still, switch to source set 2 (no yaw source) for 60 s, back to set 1 for
10 s. Registered first in tests1e. Scratch trees only.
usage: insert_set2_probe.py <tree>
"""
import sys

p = sys.argv[1] + "/Tools/autotest/arducopter.py"
s = open(p).read()
method = '''    def ProbeStaticYawSet2(self):
        \'\'\'scratch probe: 60 s on a source set with no yaw source while still\'\'\'
        self.wait_ready_to_arm()
        self.delay_sim_time(10, "settle on set 1")
        self.run_cmd(mavutil.mavlink.MAV_CMD_SET_EKF_SOURCE_SET, 2)
        self.delay_sim_time(60, "still on set 2")
        self.run_cmd(mavutil.mavlink.MAV_CMD_SET_EKF_SOURCE_SET, 1)
        self.delay_sim_time(10, "back on set 1")

'''
anchor = "    def MAV_CMD_SET_EKF_SOURCE_SET(self):\n"
assert s.count(anchor) == 1
s = s.replace(anchor, method + anchor)
reg = "            self.MAV_CMD_SET_EKF_SOURCE_SET,\n"
assert s.count(reg) == 1
s = s.replace(reg, reg + "            self.ProbeStaticYawSet2,\n")
open(p, "w").write(s)
print("probe inserted", p)
