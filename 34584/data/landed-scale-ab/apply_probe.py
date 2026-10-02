def rep(p, pairs):
    s = open(p).read()
    for o, n in pairs:
        assert s.count(o) == 1, (p, o[:70])
        s = s.replace(o, n)
    open(p, 'w').write(s)
rep('libraries/AC_AttitudeControl/AC_AttitudeControl_Multi.cpp', [
("    ang_vel_body += _rate_modifiers.sysid_ang_vel_body_rads;\n",
 "    ang_vel_body += _rate_modifiers.sysid_ang_vel_body_rads;\n    AP::logger().Write(\"TPDS\", \"TimeUS,PD\", \"Qf\", AP_HAL::micros64(), _rate_modifiers.pd_scale.x);\n"),
('#include "AC_AttitudeControl_Multi.h"', '#include "AC_AttitudeControl_Multi.h"\n#include <AP_Logger/AP_Logger.h>'),
])
rep('Tools/autotest/arducopter.py', [
("    def test_gyro_fft_harmonic(self, averaging):",
'''    def TmpScaleRace(self):
        """temporary scale reset race probe"""
        self.set_parameters({
            "AHRS_EKF_TYPE": 10,
            "EK2_ENABLE": 0,
            "EK3_ENABLE": 0,
            "LOG_DISARMED": 0,
            "FSTRATE_ENABLE": 3,
            "FSTRATE_DIV": 1,
            "SCHED_LOOP_RATE": 400,
            "ATC_LAND_R_MULT": 0.5,
        })
        self.reboot_sitl()
        self.change_mode('STABILIZE')
        self.wait_ready_to_arm()
        self.arm_vehicle()
        self.delay_sim_time(10, "sit landed with landed gain reduction active")
        self.disarm_vehicle()

    def test_gyro_fft_harmonic(self, averaging):'''),
("            self.ThrottleGainBoostRateThread,\n", "            self.ThrottleGainBoostRateThread,\n            self.TmpScaleRace,\n"),
])
