def rep(p, pairs):
    s = open(p).read()
    for o, n in pairs:
        assert s.count(o) == 1, (p, o[:70])
        s = s.replace(o, n)
    open(p, 'w').write(s)
rep('libraries/AC_AttitudeControl/AC_AttitudeControl_Multi.cpp', [
("    ang_vel_body += _rate_modifiers.sysid_ang_vel_body_rads;\n",
 "    ang_vel_body += _rate_modifiers.sysid_ang_vel_body_rads;\n    AP::logger().Write(\"TSID\", \"TimeUS,S\", \"Qf\", AP_HAL::micros64(), degrees(_rate_modifiers.sysid_ang_vel_body_rads.x));\n"),
('#include "AC_AttitudeControl_Multi.h"', '#include "AC_AttitudeControl_Multi.h"\n#include <AP_Logger/AP_Logger.h>'),
])
rep('Tools/autotest/arducopter.py', [
("    def test_gyro_fft_harmonic(self, averaging):",
'''    def TmpSysIdLag(self):
        """temporary sysid lag probe"""
        self.set_parameters({
            "AHRS_EKF_TYPE": 10,
            "EK2_ENABLE": 0,
            "EK3_ENABLE": 0,
            "LOG_DISARMED": 0,
            "FSTRATE_ENABLE": 3,
            "FSTRATE_DIV": 1,
            "SCHED_LOOP_RATE": 400,
            "SID_AXIS": 7,
            "SID_MAGNITUDE": 10,
            "SID_F_START_HZ": 0.5,
            "SID_F_STOP_HZ": 5,
            "SID_T_FADE_IN": 1,
            "SID_T_REC": 6,
            "SID_T_FADE_OUT": 1,
        })
        self.reboot_sitl()
        self.takeoff(10, mode="ALT_HOLD")
        self.change_mode('STABILIZE')
        self.set_rc(3, 1500)
        self.change_mode(25)
        self.delay_sim_time(9, "let the chirp run")
        self.change_mode('ALT_HOLD')
        self.do_RTL()

    def test_gyro_fft_harmonic(self, averaging):'''),
("            self.ThrottleGainBoostRateThread,\n", "            self.ThrottleGainBoostRateThread,\n            self.TmpSysIdLag,\n"),
])
