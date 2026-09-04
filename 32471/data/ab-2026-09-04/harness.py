"""Throwaway autotest methods used for the PR #32471 A/B runs, 2026-09-04.

Added to a scratch worktree's Tools/autotest/arducopter.py and registered on
tests1c, never committed to the firmware tree. Both are driven by environment
variables so one binary covers every arm of the A/B.

  VRF_LEARN=2 VRF_SIM=0.15 VRF_PRE=0.15 \
    Tools/autotest/autotest.py test.Copter.VRFArmTransient
  PLAT_Z=-1.0 VRF_LEARN=4 OGNM=2.0 \
    Tools/autotest/autotest.py test.Copter.PlatformAccelProbe

The shipped tests derived from these are VibrationRectificationBiasLearning
and AccelBiasMovingPlatform.
"""


def VRFArmTransient(self):
    '''A/B the VRF feature against a motors-on-only accel offset'''
    import os as _os
    learn = int(_os.environ.get("VRF_LEARN", "3"))
    vrf = float(_os.environ.get("VRF_SIM", "0.15"))
    pre = float(_os.environ.get("VRF_PRE", "0.15"))
    self.context_push()
    self.set_parameters({
        "ACC_ZBIAS_LEARN": learn,
        "SIM_ACC_VRF_Z": vrf,
        "SIM_ACC1_BIAS_Z": 0,
        "INS_ACC_VRFB_Z": pre,
        "INS_ACC2_VRFB_Z": pre,
        "INS_ACC3_VRFB_Z": pre,
        "LOG_DISARMED": 1,
    })
    self.reboot_sitl()
    self.wait_ready_to_arm()
    self.delay_sim_time(60, "settle disarmed")
    try:
        self.takeoff(10, mode='LOITER')
        self.delay_sim_time(40, "hover after arm")
    finally:
        self.land_and_disarm()
    self.context_pop()
    self.reboot_sitl()


def PlatformAccelProbe(self):
    '''probe: platform acceleration vs the movement check'''
    import os as _os
    self.set_parameters({
        "SIM_PLAT_ACC_Z": float(_os.environ.get("PLAT_Z", "-1.0")),
        "ACC_ZBIAS_LEARN": int(_os.environ.get("VRF_LEARN", "0")),
        "EK3_OGNM_TEST_SF": float(_os.environ.get("OGNM", "2.0")),
        "INS_ACC_VRFB_Z": 0,
        "LOG_DISARMED": 1,
    })
    self.reboot_sitl()
    self.wait_ready_to_arm()
    self.delay_sim_time(90, "sit on the accelerating platform")
    self.takeoff(10, mode='LOITER')
    self.delay_sim_time(20, "hover clear of the platform")
    self.land_and_disarm()
    self.reboot_sitl()
