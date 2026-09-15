# Temporary probe tests used on 2026-09-15 (never committed to the PR).
# Paste into class AutoTestCopter in Tools/autotest/arducopter.py, register
# them in tests1d, and run through autotest.py as test.Copter.<name>.

    # PROBE-BEGIN (temporary, never committed)
    def ProbeFlowAidingVelocity(self):
        '''probe: velocity across the ABS->REL transition while moving'''
        self.set_parameters({
            "SIM_FLOW_ENABLE": 1,
            "FLOW_TYPE": 10,
            "SIM_TERRAIN": 0,
            "EK3_SRC2_POSXY": 0,
            "EK3_SRC2_VELXY": 5,
            "EK3_SRC2_POSZ": 1,
            "EK3_SRC2_VELZ": 0,
            "EK3_SRC2_YAW": 1,
            "RC8_OPTION": 90,
            "LOG_REPLAY": 1,
            "LOG_DISARMED": 1,
            "LOG_DARM_RATEMAX": 0,
            "LOG_FILE_RATEMAX": 0,
        })
        self.set_analog_rangefinder_parameters()
        self.set_rc(8, 1000)
        self.reboot_sitl()
        self.wait_sensor_state(mavutil.mavlink.MAV_SYS_STATUS_LOGGING, True, True, True)
        self.progress("PROBE LOG %s" % self.current_onboard_log_filepath())
        self.takeoff(8, mode='LOITER')
        self.set_rc(8, 1500)
        self.progress("PROBE switched to flow at %.1f" % self.get_sim_time())
        self.delay_sim_time(6)
        self.set_rc(2, 1300)
        self.delay_sim_time(10)
        self.set_rc(2, 1500)
        self.delay_sim_time(5)
        self.set_rc(8, 1000)
        self.delay_sim_time(2)
        self.do_RTL()
        self.reboot_sitl(force=True)

    def ProbeFlowAidingGpsGlitch(self):
        '''probe: sustained GPS position rejection while flow velocity fuses'''
        self.set_parameters({
            "SIM_FLOW_ENABLE": 1,
            "FLOW_TYPE": 10,
            "SIM_TERRAIN": 0,
            "EK3_SRC_OPTIONS": 1,
            "EK3_SRC2_POSXY": 0,
            "EK3_SRC2_VELXY": 5,
            "EK3_SRC2_POSZ": 1,
            "EK3_SRC2_VELZ": 0,
            "EK3_SRC2_YAW": 1,
            "LOG_DISARMED": 1,
        })
        self.set_analog_rangefinder_parameters()
        self.reboot_sitl()
        self.wait_sensor_state(mavutil.mavlink.MAV_SYS_STATUS_LOGGING, True, True, True)
        self.progress("PROBE LOG %s" % self.current_onboard_log_filepath())
        self.takeoff(8, mode='LOITER')
        self.change_mode('ALT_HOLD')
        self.delay_sim_time(10)
        self.progress("PROBE glitch start at %.1f" % self.get_sim_time())
        for i in range(12):
            self.set_parameter("SIM_GPS1_GLTCH_X", 0.00045 * (i + 1))
            self.delay_sim_time(5)
        self.set_parameter("SIM_GPS1_GLTCH_X", 0)
        self.progress("PROBE glitch end at %.1f" % self.get_sim_time())
        self.delay_sim_time(30)
        self.change_mode('LAND')
        self.wait_disarmed(timeout=120)
        self.reboot_sitl(force=True)
    def ProbeFlowAidingGpsDead(self):
        '''probe: GPS stops delivering while flow velocity fuses'''
        self.set_parameters({
            "SIM_FLOW_ENABLE": 1,
            "FLOW_TYPE": 10,
            "SIM_TERRAIN": 0,
            "EK3_SRC_OPTIONS": 1,
            "EK3_SRC2_POSXY": 0,
            "EK3_SRC2_VELXY": 5,
            "EK3_SRC2_POSZ": 1,
            "EK3_SRC2_VELZ": 0,
            "EK3_SRC2_YAW": 1,
            "LOG_DISARMED": 1,
        })
        self.set_analog_rangefinder_parameters()
        self.reboot_sitl()
        self.wait_sensor_state(mavutil.mavlink.MAV_SYS_STATUS_LOGGING, True, True, True)
        self.progress("PROBE LOG %s" % self.current_onboard_log_filepath())
        self.takeoff(8, mode='LOITER')
        self.change_mode('ALT_HOLD')
        self.delay_sim_time(10)
        self.progress("PROBE gps off at %.1f" % self.get_sim_time())
        self.set_parameter("SIM_GPS1_ENABLE", 0)
        self.delay_sim_time(25)
        self.set_parameter("SIM_GPS1_ENABLE", 1)
        self.progress("PROBE gps on at %.1f" % self.get_sim_time())
        self.delay_sim_time(15)
        self.change_mode('LAND')
        self.wait_disarmed(timeout=120)
        self.reboot_sitl(force=True)
