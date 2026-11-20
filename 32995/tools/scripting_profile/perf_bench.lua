--[[
  Per-call cost of Lua bindings and VM operations on this board.

  One entry is measured per run: REPEATS timed batches of N calls, wrapped in
  a closure called from a loop. The minimum batch is the cost without
  preemption (the scripting thread has the lowest priority, so every other
  thread interrupts it); the median shows what preemption and GC add. The
  empty closure's cost is subtracted from every entry. Results go to the GCS
  one line a run and to /APM/perf_bench.txt.
--]]

local N = 40
local REPEATS = 9
local OUT = "/APM/perf_bench.txt"

local function now_us()
    return micros():toint()
end

local vec = Vector3f()
vec:x(1.0); vec:y(2.0); vec:z(3.0)
local vec2 = Vector3f()
local p_angle = Parameter("ATC_ANGLE_MAX")
local ch_roll = rc:get_channel(1)
local loc = Location()
local t = {}
local x = 1.2345

local entries = {
    {"empty closure", function() end},
    {"lua arith 4 ops", function() x = x * 1.0001 + 0.5 - 0.25 / 3.0 end},
    {"math.sin", function() x = math.sin(x) end},
    {"table write+read", function() t[1] = x; x = t[1] end},
    {"string.format %.2f", function() local _ = string.format("%.2f", x) end},
    {"millis()", function() millis() end},
    {"micros():toint()", function() micros():toint() end},
    {"uint32 sub :toint()", function() local _ = (micros() - millis()):toint() end},
    {"arming:is_armed", function() arming:is_armed() end},
    {"vehicle:get_mode", function() vehicle:get_mode() end},
    {"vehicle:get_likely_flying", function() vehicle:get_likely_flying() end},
    {"ahrs:get_roll_rad", function() ahrs:get_roll_rad() end},
    {"ahrs:healthy", function() ahrs:healthy() end},
    {"ahrs:get_gyro (Vector3f)", function() ahrs:get_gyro() end},
    {"ahrs:get_quaternion", function() ahrs:get_quaternion() end},
    {"ahrs:get_velocity_NED", function() ahrs:get_velocity_NED() end},
    {"ahrs:get_position", function() ahrs:get_position() end},
    {"ins:get_accel(0)", function() ins:get_accel(0) end},
    {"Vector3f:x()", function() vec:x() end},
    {"Vector3f()", function() Vector3f() end},
    {"Vector3f + Vector3f", function() local _ = vec + vec2 end},
    {"Location()", function() Location() end},
    {"loc:lat()", function() loc:lat() end},
    {"baro:get_altitude", function() baro:get_altitude() end},
    {"battery:voltage(0)", function() battery:voltage(0) end},
    {"esc_telem:get_rpm(0)", function() esc_telem:get_rpm(0) end},
    {"SRV:get_output_pwm(33)", function() SRV_Channels:get_output_pwm(33) end},
    {"rc_ch:norm_input", function() ch_roll:norm_input() end},
    {"Parameter:get", function() p_angle:get() end},
    {"param:get(name)", function() param:get("ATC_ANGLE_MAX") end},
    {"set_target_angle_climb", function() vehicle:set_target_angle_and_climbrate(0, 0, 0, 0, false, 0) end},
    {"logger:write 4 floats", function() logger:write("LPRB", "a,b,c,d", "ffff", x, x, x, x) end},
}

local results = {}
local idx = 1
local empty_min, empty_med = 0.0, 0.0

local function measure(fn)
    local batches = {}
    for r = 1, REPEATS do
        local t0 = now_us()
        for _ = 1, N do
            fn()
        end
        batches[r] = (now_us() - t0) / N
    end
    table.sort(batches)
    return batches[1], batches[(REPEATS + 1) // 2]
end

local function finish()
    local f = io.open(OUT, "w")
    if f then
        f:write(string.format("# N=%d REPEATS=%d, us per call, empty closure subtracted (min %.2f med %.2f)\n",
                              N, REPEATS, empty_min, empty_med))
        for _, r in ipairs(results) do
            f:write(string.format("%-28s min %7.2f  med %7.2f\n", r[1], r[2], r[3]))
        end
        f:close()
    end
    gcs:send_text(6, "LB: done, " .. #results .. " entries in " .. OUT)
end

local function update()
    local e = entries[idx]
    local mn, md = measure(e[2])
    if idx == 1 then
        empty_min, empty_med = mn, md
    else
        mn, md = mn - empty_min, md - empty_med
        results[#results + 1] = {e[1], mn, md}
        gcs:send_text(6, string.format("LB %s min %.2f med %.2f us", e[1], mn, md))
    end
    idx = idx + 1
    if idx > #entries then
        finish()
        return
    end
    return update, 200
end

gcs:send_text(6, "LB: start")
return update, 3000
