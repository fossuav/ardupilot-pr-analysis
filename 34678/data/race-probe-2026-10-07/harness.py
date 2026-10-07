# Throwaway autotest method used on 2026-10-07 to look for the rate-thread
# ordering race described in 34678/README.md. Not part of the PR.
#
# To re-run: paste the method into the Copter test class in
# Tools/autotest/arducopter.py, add `self.ZZRaceProbe,` to a tests2* list,
# build SITL copter with the one-loop grace removed (in
# ArduCopter/land_detector.cpp change `takeoff_missed_count > 1` to
# `takeoff_missed_count > 0`), then run test.Copter.ZZRaceProbe.
# It stops at the first punch that raises an internal error.

    def ZZRaceProbe(self):
        '''throwaway: rate thread airmode throttle punch from zero'''
        self.set_parameters({"FSTRATE_ENABLE": 1, "ACRO_OPTIONS": 1})
        self.reboot_sitl()
        self.change_mode('ACRO')
        self.wait_ready_to_arm()
        for i in range(40):
            self.set_rc(3, 1000)
            self.arm_vehicle()
            self.delay_sim_time(1, "spool up")
            self.set_rc(3, 1900)
            self.delay_sim_time(0.2, "punch")
            self.set_rc(3, 1000)
            self.disarm_vehicle(force=True)
            self.delay_sim_time(2, "settle")
            m = self.assert_receive_message('SYS_STATUS')
            self.progress("PROBE punch %u errors_count4=%u" % (i, m.errors_count4))
            if m.errors_count4:
                break
