#!/usr/bin/env python3
"""Turn EK3HardLandingRearm's mechanism checks into PROBE progress lines (scratch only).

The reset-message check and the three "refuses arming" checks become reports, and
each arm logs the EKF's vz, so every leg's outcome is measured on a build without
#34942's EKF changes. The climb check in fly_and_land is left as it is: that is the
outcome the A/B is about, and it stops the run where it fails.
usage: probe_test.py <tree>
"""
import sys

p = sys.argv[1] + "/Tools/autotest/arducopter.py"
s = open(p).read()


def sub(old, new, count=1):
    global s
    assert s.count(old) == count, (old, s.count(old))
    s = s.replace(old, new)


sub("""            reset_before_arm = any(reset_text in x.text for x in self.context_collection('STATUSTEXT'))
            self.arm_vehicle()
""", """            reset_before_arm = any(reset_text in x.text for x in self.context_collection('STATUSTEXT'))
            vz = self.assert_receive_message('LOCAL_POSITION_NED', timeout=5).vz
            self.progress("PROBE: arming with vz %.2f m/s, reset before arm %s" % (vz, reset_before_arm))
            self.arm_vehicle()
""")
sub("""            if not reset_before_arm:
                raise NotAchievedException("no vertical velocity reset before the re-arm")
""", """            if not reset_before_arm:
                self.progress("PROBE: no vertical velocity reset before the re-arm")
""")
sub("""        self.wait_ekf_flags(0, mavutil.mavlink.ESTIMATOR_ATTITUDE, timeout=3)
        self.assert_arm_failure("height error", ignore_prearm_failures=ignore)
""", """        try:
            self.wait_ekf_flags(0, mavutil.mavlink.ESTIMATOR_ATTITUDE, timeout=3)
            self.assert_arm_failure("height error", ignore_prearm_failures=ignore)
            self.progress("PROBE: refused on the height error")
        except Exception as e:
            self.progress("PROBE: not refused on the height error: %s" % e)
            if self.armed():
                self.disarm_vehicle(force=True)
""", count=2)
sub("""        self.arm_vehicle()
        if self.get_rangefinder_distance() < 1.0:
            raise NotAchievedException("armed only once on the ground")
""", """        self.arm_vehicle()
        self.progress("PROBE: falling re-arm accepted at %.2f m" % self.get_rangefinder_distance())
""")
open(p, "w").write(s)
print("probe test written", p)
