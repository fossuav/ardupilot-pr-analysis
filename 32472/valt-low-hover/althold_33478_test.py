    def EK3_AglKfVelBaroWash(self):
        '''AGL KF velD fusion holds a low hover over a baro that reads high near the floor'''
        # Close to the floor rotor wash can make the baro read high, and higher the lower
        # the vehicle goes. With the baro the only height source the estimate rises with it,
        # so ALT_HOLD descends to hold its target and the error grows until the vehicle is
        # on the floor. EK3_OPTIONS bit 4 fuses the range finder aided AGL KF velocity as
        # velD, which the wash does not reach, so the estimate follows the vehicle. The wash
        # is a script on the baro glitch: a bias and low-passed noise at the floor, none
        # from 2 m, brought in over 2 s once the vehicle first leaves the floor so that the
        # arming height reset does not take it as the zero.
        wash_lua = """
local n = 0
local gain = 0
function update()
    local h = rangefinder:distance_orient(25)
    if not arming:is_armed() then
        gain = 0
    elseif gain > 0 or h > 0.2 then
        gain = math.min(1, gain + 0.01)
    end
    n = 0.9 * n + 0.1 * (math.random() * 2 - 1) * 3
    local err = gain * (0.5 + 2.0 * n) * math.max(0, 1 - h / 2)
    param:set('SIM_BARO_GLITCH', err)
    param:set('SIM_BAR2_GLITCH', err)
    return update, 20
end
return update()
"""
        self.set_parameters({
            "SIM_FLOW_ENABLE": 1,
            "FLOW_TYPE": 10,
            "SIM_TERRAIN": 0,       # a flat floor, so the range is the height
            "EK3_RNG_USE_HGT": -1,  # range finder must not become the height source
            "SURFTRAK_MODE": 0,     # hold the estimate, not the range
            "SCR_ENABLE": 1,
        })
        self.set_analog_rangefinder_parameters()
        self.configure_EKFs_to_use_optical_flow_instead_of_GPS()
        self.install_script_content_context("baro_wash.lua", wash_lua)

        agl_kf_veld = 1 << 4  # EK3_OPTIONS AglKfVelForVelD

        def fly_leg(options_value):
            '''hands-off ALT_HOLD hover at about 0.4 m; share of it on the floor, and whether velD was fused'''
            self.set_parameter("EK3_OPTIONS", options_value)
            self.reboot_sitl()
            self.wait_ready_to_arm(require_absolute=False)
            # takeoff() centres the stick at altitude_min - 1, so this hovers from 0.4 m;
            # coming down into the hover instead overshoots onto the floor
            self.takeoff(1.4, takeoff_throttle=1650, mode="ALT_HOLD", require_absolute=False)
            # the stop from the climb is not part of the hover
            t_start = self.get_sim_time() + 5
            # no event to wait for: the hold itself is the measurement
            self.delay_sim_time(60, reason="hands-off hover low over the floor")
            t_end = self.get_sim_time()
            self.disarm_vehicle(force=True)

            dfreader = self.dfreader_for_current_onboard_log()
            ground_alt = None
            armed = False
            n = floor = 0
            fused = False
            while True:
                m = dfreader.recv_match(type=["ARM", "SIM", "XKFA"])
                if m is None:
                    break
                mtype = m.get_type()
                if mtype == "ARM":
                    armed = m.ArmState == 1
                    continue
                if mtype == "SIM" and not armed:
                    ground_alt = m.Alt
                t = m.TimeUS * 1.0e-6
                if t < t_start or t > t_end:
                    continue
                if mtype == "SIM" and ground_alt is not None:
                    n += 1
                    if m.Alt - ground_alt < 0.15:
                        floor += 1
                elif mtype == "XKFA" and m.C == 0 and m.VFuse:
                    fused = True
            if n < 100:
                raise NotAchievedException("Only %u SIM samples in the hover" % n)
            return floor / n, fused

        # without the fusion the wash runs the estimate up and the hover down; this leg
        # shows the test reaches the failure it is guarding against
        self.start_subtest("Fusion off: the wash pulls a low hover onto the floor")
        on_floor, fused = fly_leg(0)
        self.progress("fusion off: on the floor for %.0f%% of the hover" % (100 * on_floor))
        if fused:
            raise NotAchievedException("AGL KF velocity was fused with the option disabled")
        if on_floor < 0.1:
            raise NotAchievedException(
                "Expected the wash to pull the hover onto the floor with fusion off (%.0f%%)" % (100 * on_floor))

        self.start_subtest("Fusion on: the low hover holds over the wash")
        on_floor, fused = fly_leg(agl_kf_veld)
        self.progress("fusion on: on the floor for %.0f%% of the hover" % (100 * on_floor))
        if not fused:
            raise NotAchievedException("AGL KF velocity was never fused during the hover")
        if on_floor > 0.05:
            raise NotAchievedException(
                "AGL KF velocity fusion did not hold the hover off the floor (%.0f%%)" % (100 * on_floor))

        self.reboot_sitl()

