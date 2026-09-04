# Throwaway A/B harness methods, added to Tools/autotest/arducopter.py for the
# 2026-09-04 runs and reverted afterwards. Register them on a tests1* list.
# AB_DZ and AB_GEFF are read from the environment so one harness serves every run.

    def ABGndEffectTakeoff(self):
        '''A/B harness: ground effect spool-up and takeoff (throwaway)'''
        import os
        self.set_parameters({
            "SIM_BARO_GEFF_M": float(os.environ.get("AB_GEFF", "5")),
            "EK3_GND_EFF_DZ": float(os.environ.get("AB_DZ", "4")),
            "DISARM_DELAY": 0,
        })
        self.change_mode("ALT_HOLD")
        self.wait_ready_to_arm()
        self.arm_vehicle()
        try:
            self.delay_sim_time(10, "idle in ground effect")
            self.set_rc(3, 1700)
            self.wait_altitude(3.0, 6.0, relative=True, timeout=40)
            self.set_rc(3, 1500)
            self.delay_sim_time(12, "hover above the ground effect model")
        finally:
            self.disarm_vehicle(force=True)

    def ABGndEffectPersistBaro(self):
        '''A/B harness: persistently failed baro in ground effect (throwaway)'''
        import os
        self.set_parameters({
            "SIM_BARO_GEFF_M": float(os.environ.get("AB_GEFF", "30")),
            "EK3_GND_EFF_DZ": float(os.environ.get("AB_DZ", "4")),
            "DISARM_DELAY": 0,
        })
        self.change_mode("ALT_HOLD")
        self.wait_ready_to_arm()
        self.arm_vehicle()
        try:
            self.delay_sim_time(45, "armed at idle with a failed baro")
        finally:
            self.disarm_vehicle(force=True)

