--[[
  Scripting performance workload: a Lua flight mode run at 50 Hz, with every
  binding method looked up once into a local.

  Each run reads attitude, rates, accelerations, baro, battery, RC, ESC
  telemetry and motor outputs, runs an angle and altitude-rate controller in
  Lua, commands the vehicle when it is in GUIDED_NOGPS or the registered
  custom mode, and logs one LPRF message. Sections are timed with micros();
  every 10 s a summary goes to the GCS:
    LP n <runs> per <mean>/<max> ms tot <mean>/<min>/<max> us | sen ctl out log <mean> us
  Bench-safe: the commanded climb rate is never positive, so a landed copter
  stays at ground idle.
--]]

local RATE_HZ = 50
local PERIOD_MS = 1000 // RATE_HZ
local MODE_GUIDED_NOGPS = 20
local MODE_CUSTOM = 101
local REPORT_MS = 10000

local custom = vehicle:register_custom_mode(MODE_CUSTOM, "Lua Perf", "LPRF")
gcs:send_text(6, string.format("LP: custom mode %s", custom and "registered" or "not registered"))

local ANGLE_MAX = Parameter("ATC_ANGLE_MAX")
local PILOT_Y_RATE = Parameter("PILOT_Y_RATE")
local PILOT_SPD_DN = Parameter("PILOT_SPD_DN")
local ch_roll = rc:get_channel(math.floor(param:get("RCMAP_ROLL")))
local ch_pitch = rc:get_channel(math.floor(param:get("RCMAP_PITCH")))
local ch_thr = rc:get_channel(math.floor(param:get("RCMAP_THROTTLE")))
local ch_yaw = rc:get_channel(math.floor(param:get("RCMAP_YAW")))
local MOTOR_FN = {33, 34, 35, 36}

-- every binding method used per run, looked up once
local v3 = Vector3f()
local V3_X, V3_Y, V3_Z = v3.x, v3.y, v3.z
local GET_MODE, LIKELY_FLYING, SET_TARGET = vehicle.get_mode, vehicle.get_likely_flying, vehicle.set_target_angle_and_climbrate
local IS_ARMED = arming.is_armed
local ROLL, PITCH, YAW = ahrs.get_roll_rad, ahrs.get_pitch_rad, ahrs.get_yaw_rad
local GYRO, VEL_NED, AHRS_HEALTHY = ahrs.get_gyro, ahrs.get_velocity_NED, ahrs.healthy
local GET_ACCEL = ins.get_accel
local ALTITUDE = baro.get_altitude
local VOLTAGE, CURRENT = battery.voltage, battery.current_amps
local NORM_INPUT = ch_roll.norm_input
local RPM = esc_telem.get_rpm
local OUTPUT_PWM = SRV_Channels.get_output_pwm
local PARAM_GET = ANGLE_MAX.get
local NAMED_FLOAT = gcs.send_named_float
local LOG_WRITE = logger.write
local MICROS, MILLIS = micros, millis
local u32 = micros()
local TOINT = u32.toint

-- PI controller state
local function make_pi(kp, ki, imax)
    return {kp = kp, ki = ki, imax = imax, i = 0.0}
end
local function pi_update(c, err, dt)
    c.i = math.max(-c.imax, math.min(c.imax, c.i + err * c.ki * dt))
    return err * c.kp + c.i
end
local pi_roll = make_pi(4.5, 0.5, 10.0)
local pi_pitch = make_pi(4.5, 0.5, 10.0)
local pi_yaw = make_pi(3.0, 0.1, 20.0)
local pi_alt = make_pi(1.0, 0.2, 1.0)

local function expo(x, e)
    return (1.0 - e) * x + e * x * x * x
end

local function wrap_180(a)
    while a > 180.0 do a = a - 360.0 end
    while a < -180.0 do a = a + 360.0 end
    return a
end

local S = {}            -- sensor readings, reused every run
local yaw_target_deg = nil
local alt_target_m = nil
local last_run_us = nil

-- statistics over a report window
local n, per_sum, per_max = 0, 0, 0
local tot_sum, tot_min, tot_max = 0, 1e9, 0
local sec = {0, 0, 0, 0}
local window_start_ms = millis():toint()

-- cost of one timing point, subtracted from every section
local function now_us()
    return TOINT(MICROS())
end
local overhead_us = 1e9
for _ = 1, 20 do
    local a = now_us()
    local b = now_us()
    overhead_us = math.min(overhead_us, b - a)
end

local function read_sensors()
    S.mode = GET_MODE(vehicle)
    S.armed = IS_ARMED(arming)
    S.flying = LIKELY_FLYING(vehicle)
    S.roll = math.deg(ROLL(ahrs))
    S.pitch = math.deg(PITCH(ahrs))
    S.yaw = math.deg(YAW(ahrs))
    local g = GYRO(ahrs)
    S.gx, S.gy, S.gz = V3_X(g), V3_Y(g), V3_Z(g)
    local a = GET_ACCEL(ins, 0)
    S.az = V3_Z(a)
    local v = VEL_NED(ahrs)
    S.vz = v and V3_Z(v) or 0.0
    S.healthy = AHRS_HEALTHY(ahrs)
    S.alt = ALTITUDE(baro)
    S.volt = VOLTAGE(battery, 0)
    S.amps = CURRENT(battery, 0) or 0.0
    S.rc_r = NORM_INPUT(ch_roll)
    S.rc_p = NORM_INPUT(ch_pitch)
    S.rc_t = NORM_INPUT(ch_thr)
    S.rc_y = NORM_INPUT(ch_yaw)
    local rpm_sum, pwm_sum = 0.0, 0
    for i = 1, 4 do
        rpm_sum = rpm_sum + (RPM(esc_telem, i - 1) or 0.0)
        pwm_sum = pwm_sum + (OUTPUT_PWM(SRV_Channels, MOTOR_FN[i]) or 0)
    end
    S.rpm = rpm_sum * 0.25
    S.pwm = pwm_sum * 0.25
end

local out = {roll = 0.0, pitch = 0.0, yaw = 0.0, climb = 0.0}

local function control(dt)
    local angle_max = PARAM_GET(ANGLE_MAX)
    local yaw_rate_max = PARAM_GET(PILOT_Y_RATE)
    local climb_max = PARAM_GET(PILOT_SPD_DN)
    if climb_max <= 0 then climb_max = 1.5 end

    if yaw_target_deg == nil then yaw_target_deg = S.yaw end
    if alt_target_m == nil then alt_target_m = S.alt end

    -- pilot sticks to earth-frame lean angles, rotated by heading as a position mode would
    local cy, sy = math.cos(math.rad(S.yaw)), math.sin(math.rad(S.yaw))
    local fwd = -expo(S.rc_p, 0.3) * angle_max
    local rgt = expo(S.rc_r, 0.3) * angle_max
    local north = fwd * cy - rgt * sy
    local east = fwd * sy + rgt * cy
    local want_roll = -north * sy + east * cy
    local want_pitch = -(north * cy + east * sy)

    yaw_target_deg = wrap_180(yaw_target_deg + expo(S.rc_y, 0.2) * yaw_rate_max * dt)
    alt_target_m = alt_target_m + S.rc_t * climb_max * dt

    out.roll = math.max(-angle_max, math.min(angle_max, want_roll + 0.01 * pi_update(pi_roll, want_roll - S.roll, dt)))
    out.pitch = math.max(-angle_max, math.min(angle_max, want_pitch + 0.01 * pi_update(pi_pitch, want_pitch - S.pitch, dt)))
    out.yaw = wrap_180(yaw_target_deg + 0.01 * pi_update(pi_yaw, wrap_180(yaw_target_deg - S.yaw), dt))
    -- never climb: bench-safe
    out.climb = math.min(0.0, math.max(-climb_max, pi_update(pi_alt, alt_target_m - S.alt, dt) - 0.1 * S.vz))
end

local function output()
    if S.mode == MODE_GUIDED_NOGPS or S.mode == MODE_CUSTOM then
        SET_TARGET(vehicle, out.roll, out.pitch, out.yaw, out.climb, false, 0.0)
    else
        yaw_target_deg, alt_target_m = nil, nil
    end
    if n % 5 == 0 then
        NAMED_FLOAT(gcs, "LP_ALT", S.alt)
    end
end

local function log()
    LOG_WRITE(logger, "LPRF", "Rd,Pd,Yd,Cr,Alt,Gz,Az,Rpm,Pwm,V", "ffffffffff",
                 out.roll, out.pitch, out.yaw, out.climb, S.alt, S.gz, S.az, S.rpm, S.pwm, S.volt)
end

local function report(now_ms)
    if n > 0 then
        gcs:send_text(6, string.format("LPC n %d per %.1f/%d ms tot %.0f/%d/%d us | sen %.0f ctl %.0f out %.0f log %.0f us",
            n, per_sum / math.max(1, n - 1) * 0.001, per_max // 1000, tot_sum / n, tot_min, tot_max,
            sec[1] / n, sec[2] / n, sec[3] / n, sec[4] / n))
    end
    n, per_sum, per_max = 0, 0, 0
    tot_sum, tot_min, tot_max = 0, 1e9, 0
    sec = {0, 0, 0, 0}
    window_start_ms = now_ms
end

local function update()
    local t0 = now_us()
    local dt = PERIOD_MS * 0.001
    if last_run_us ~= nil then
        local period = t0 - last_run_us
        dt = period * 1.0e-6
        per_sum = per_sum + period
        per_max = math.max(per_max, period)
    end
    last_run_us = t0

    read_sensors()
    local t1 = now_us()
    control(dt)
    local t2 = now_us()
    output()
    local t3 = now_us()
    log()
    local t4 = now_us()

    sec[1] = sec[1] + (t1 - t0 - overhead_us)
    sec[2] = sec[2] + (t2 - t1 - overhead_us)
    sec[3] = sec[3] + (t3 - t2 - overhead_us)
    sec[4] = sec[4] + (t4 - t3 - overhead_us)
    local tot = t4 - t0 - overhead_us
    tot_sum = tot_sum + tot
    tot_min = math.min(tot_min, tot)
    tot_max = math.max(tot_max, tot)
    n = n + 1

    local now_ms = TOINT(MILLIS())
    if now_ms - window_start_ms >= REPORT_MS then
        report(now_ms)
    end
    return update, PERIOD_MS
end

gcs:send_text(6, string.format("LPC: %d Hz, timing point %d us", RATE_HZ, overhead_us))
return update, PERIOD_MS
