--[[
  Bench source of ESC RPM for the notch A/B, on a board with no motors.

  Sweeps four motors around 224 Hz, the median of the hard flight (log 15),
  so the harmonic notch centres cross the 400 Hz where newlib's sinf and cosf
  take their range reduction, and change at every update as they do in flight.
  Updates at about 80 Hz, the rate the ESCs reported in that flight.
--]]

local BASE_HZ = 224
local SWEEP_HZ = 60
local SWEEP_PERIOD_S = 8
local OFFSET_HZ = {0, 3.1, -4.2, 5.3}
local PERIOD_MS = 12

gcs:send_text(6, "notch_ab: RPM source running")

local function update()
    local t = millis():tofloat() * 0.001
    local f = BASE_HZ + SWEEP_HZ * math.sin(2 * math.pi * t / SWEEP_PERIOD_S)
    for i = 1, 4 do
        esc_telem:update_rpm(i - 1, (f + OFFSET_HZ[i]) * 60, 0)
    end
    return update, PERIOD_MS
end

return update, 1000
