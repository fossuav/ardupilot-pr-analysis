    def VALTLowHoverGroundEffect(self):
        '''a centre-stick VALT hover over the floor with rotor wash on the baro'''
        # Rotor wash corrupts the baro within a metre or two of the floor, by metres and in
        # either direction. VALT flies the EKF height, which is the baro here (the range finder
        # serves flow only), so whatever of that error reaches the EKF moves the vehicle; one
        # that reads high by more than it falls with height pulls the vehicle into the floor.
        # The wash is a Lua script on the baro glitch, so the same test runs on builds without
        # SIM_BARO_GEFF_M.
        wash_lua = """
-- rotor wash on the baro: SCR_USER1 metres of bias and SCR_USER2 metres of low-passed noise
-- at the floor, none from SCR_USER3 metres; it comes in over 2 s once the vehicle first
-- leaves the floor, as the arming datum reset would otherwise take it in as the zero
local n = 0
local gain = 0
-- SCR_USER5 seeds the noise, so a case can be repeated with a different wash
math.randomseed(math.floor(param:get('SCR_USER5') or 0))
function update()
    local mean = param:get('SCR_USER1') or 0
    local spread = param:get('SCR_USER2') or 0
    local top = param:get('SCR_USER3') or 1
    -- a baro-only case declares the range finder forward (0), which SITL still points down
    local h = rangefinder:distance_orient(math.floor(param:get('SCR_USER4') or 25))
    if not arming:is_armed() then
        gain = 0
    elseif gain > 0 or (h and h > 0.2) then
        gain = math.min(1, gain + 0.01)
    end
    local err = 0
    if h then
        n = 0.9 * n + 0.1 * (math.random() * 2 - 1) * 3
        err = gain * (mean + spread * n) * math.max(0, 1 - h / top)
    end
    param:set('SIM_BARO_GLITCH', err)
    param:set('SIM_BAR2_GLITCH', err)
    return update, 20
end
return update()
"""
        # wash bias and noise at the floor (m), height it fades to zero at (m), baro-only (no
        # range finder or flow for the EKF), and any further parameters
        cases = (
            (1.5, 0.0, 1.0, False, {}),
            (-1.5, 0.0, 1.0, False, {}),
            (0.5, 2.0, 2.0, False, {}),
        )
        results = []
        for (mean_m, spread_m, top_m, baro_only, extra) in cases:
            self.start_subtest("baro wash %+.1f m bias, %.1f m spread, to %.1f m%s %s" % (
                mean_m, spread_m, top_m, " baro-only" if baro_only else "", extra))
            self.context_push()
            results.append(self.valt_low_hover(mean_m, spread_m, top_m, baro_only, extra, wash_lua))
            self.context_pop()
            self.reboot_sitl()
        for r in results:
            self.progress("VALTLOW %s" % r)

    def valt_low_hover(self, mean_m, spread_m, top_m, baro_only, extra, wash_lua):
        '''VALTLowHoverGroundEffect with one wash model'''
        params = {
            "SIM_TERRAIN": 0,
            "EK3_RNG_USE_HGT": -1,
            "VALT_POS_EXPO": 5,
            "SCR_ENABLE": 1,
            "SCR_USER1": mean_m,
            "SCR_USER2": spread_m,
            "SCR_USER3": top_m,
            "SCR_USER4": 0 if baro_only else 25,
        }
        if baro_only:
            # GPS keeps the horizontal; nothing but the baro observes the vertical
            params.update({"EK3_SRC1_POSZ": 1, "EK3_SRC1_VELZ": 0})
        else:
            params.update({"SIM_FLOW_ENABLE": 1, "FLOW_TYPE": 10})
        # the ground effect parameters were renamed between 4.7.0 and 4.7.2
        try:
            self.get_parameter("GNDEFF_ALT", attempts=2)
            params.update({"GNDEFF_ALT": 1, "GNDEFF_TMO": 3})
        except Exception:
            params.update({"GND_EFFECT_COMP": 1, "TKOFF_GNDEFF_ALT": 1, "TKOFF_GNDEFF_TMO": 3})
        self.set_parameters(params)
        if not baro_only:
            self.configure_EKFs_to_use_optical_flow_instead_of_GPS()
        self.set_analog_rangefinder_parameters()
        if baro_only:
            # the EKF and Copter read only a downward range finder; the wash script reads this one
            self.set_parameter("RNGFND1_ORIENT", 0)
        # after the range finder's own, so a case can change its minimum range
        self.set_parameters(extra)
        self.install_script_content_context("baro_wash.lua", wash_lua)
        self.reboot_sitl()
        self.wait_ready_to_arm(require_absolute=False)
        self.change_mode(29)  # VALT
        self.set_rc(3, 1000)
        ground_amsl = self.get_altitude(altitude_source="SIM_STATE.alt")
        self.arm_vehicle()
        arm_us = int(self.get_sim_time() * 1e6)
        # climb to about 0.4 m on the range finder, then centre the stick
        self.set_rc(3, 1650)
        tstart = self.get_sim_time()
        while self.get_sim_time_cached() - tstart < 20:
            if baro_only:
                if self.get_altitude(altitude_source="SIM_STATE.alt") - ground_amsl >= 0.4:
                    break
            elif self.poll_message('RANGEFINDER').distance >= 0.4:
                break
        self.set_rc(3, 1500)
        hold0_us = int(self.get_sim_time() * 1e6)
        self.delay_sim_time(60, "centre-stick hover low over the floor")
        hold1_us = int(self.get_sim_time() * 1e6)
        self.set_rc(3, 1000)
        self.delay_sim_time(8, "descend")
        self.disarm_vehicle(force=True)

        dfreader = self.dfreader_for_current_onboard_log()
        ground_alt = None
        true_h = []
        ekf_err = []
        ekf_alt = None
        prev = None
        vz = []
        flags = [0, 0, 0]
        while True:
            m = dfreader.recv_match(type=['SIM', 'CTUN', 'XKF4'])
            if m is None:
                break
            t = m.TimeUS
            mtype = m.get_type()
            if mtype == 'SIM':
                if t <= arm_us or ground_alt is None:
                    ground_alt = m.Alt
                if hold0_us + 5e6 <= t <= hold1_us:
                    h = m.Alt - ground_alt
                    true_h.append(h)
                    if ekf_alt is not None:
                        ekf_err.append(ekf_alt - h)
                    if prev is not None and t > prev[0]:
                        vz.append((h - prev[1]) / ((t - prev[0]) * 1e-6))
                    prev = (t, h)
            elif mtype == 'CTUN':
                ekf_alt = m.Alt
            elif mtype == 'XKF4' and m.C == 0 and hold0_us + 5e6 <= t <= hold1_us:
                flags[0] += 1
                if m.SS & 2048:
                    flags[1] += 1
                if m.SS & 4096:
                    flags[2] += 1
        n = len(true_h)
        floor = len([x for x in true_h if x < 0.15])
        srt = sorted(true_h)
        rms_err = math.sqrt(sum(x * x for x in ekf_err) / max(1, len(ekf_err)))
        rms_vz = math.sqrt(sum(x * x for x in vz) / max(1, len(vz)))
        return ("wash %+.1f/%.1f m to %.1f m%s %s: true height min %.2f p10 %.2f median %.2f max %.2f, "
                "on the floor (<0.15 m) %.0f%%, vertical speed rms %.2f m/s, EKF height error rms %.2f m, "
                "takeoff_expected %.0f%% touchdown_expected %.0f%%" % (
                    mean_m, spread_m, top_m, " baro-only" if baro_only else "", extra,
                    srt[0], srt[n // 10], srt[n // 2], srt[-1], 100.0 * floor / max(1, n),
                    rms_vz, rms_err, 100.0 * flags[1] / max(1, flags[0]), 100.0 * flags[2] / max(1, flags[0])))

