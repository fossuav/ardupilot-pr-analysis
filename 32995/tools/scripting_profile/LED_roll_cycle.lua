--[[
  LED_roll.lua on four NeoPixels, running for 15 s and stopped for 15 s in
  turn, so that one flight log compares the two under the same conditions.
  Each change of state writes an LEDC record (On is 1 or 0). The strip is
  dark while stopped. Needs SERVOn_FUNCTION 94 on the LED output.

  The work done while running is LED_roll.lua's, unchanged but for the LED
  count and NeoPixel in place of ProfiLED, to match the bench figures.
--]]

local num_leds = 4
local CYCLE_MS = 15000
local STOPPED_POLL_MS = 250

local chan = SRV_Channels:find_channel(94)

if not chan then
    gcs:send_text(6, "LEDs: channel not set")
    return
end

-- find_channel returns 0 to 15, convert to 1 to 16
chan = chan + 1

gcs:send_text(6, "LEDs: chan=" .. tostring(chan))

if not serialLED:set_num_neopixel(chan, num_leds) then
    gcs:send_text(3, "LEDs: NeoPixel setup failed")
    return
end

-- constrain a value between limits
function constrain(v, vmin, vmax)
   if v < vmin then
      v = vmin
   end
   if v > vmax then
      v = vmax
   end
   return v
end

--[[
Table of colors on a rainbow, red first
--]]
local rainbow = {
  { 255, 0, 0 },
  { 255, 127, 0 },
  { 255, 255, 0 },
  { 0,   255, 0 },
  { 0,   0,   255 },
  { 75,  0,   130 },
  { 143, 0,   255 },
}

--[[
Function to set a LED to a color on a classic rainbow spectrum, with v=0 giving red
--]]
local function set_Rainbow(channel, led, v)
  local num_rows = #rainbow
  local row = math.floor(constrain(v * (num_rows-1)+1, 1, num_rows-1))
  local v0 = (row-1) / (num_rows-1)
  local v1 = row / (num_rows-1)
  local p = (v - v0) / (v1 - v0)
  r = math.floor(rainbow[row][1] + p * (rainbow[row+1][1] - rainbow[row][1]))
  g = math.floor(rainbow[row][2] + p * (rainbow[row+1][2] - rainbow[row][2]))
  b = math.floor(rainbow[row][3] + p * (rainbow[row+1][3] - rainbow[row][3]))
  serialLED:set_RGB(channel, led, r, g, b)
end

-- turn the strip off for the stopped half of the cycle
local function blank_LEDs()
  for led = 0, num_leds-1 do
    serialLED:set_RGB(chan, led, 0, 0, 0)
  end
  serialLED:send(chan)
end

local was_running = nil

--[[
We will set the colour of the LEDs based on roll of the aircraft
--]]
function update_LEDs()
  local running = (millis():toint() // CYCLE_MS) % 2 == 0
  if running ~= was_running then
    was_running = running
    logger:write("LEDC", "On", "B", running and 1 or 0)
    if not running then
      blank_LEDs()
    end
  end
  if not running then
    return update_LEDs, STOPPED_POLL_MS
  end

  local roll = constrain(ahrs:get_roll_rad(), math.rad(-60), math.rad(60))

  for led = 0, num_leds-1 do
    local v  = constrain(0.5 + 0.5 * math.sin(roll * (led - num_leds/2) / (num_leds/2)), 0, 1)
    set_Rainbow(chan, led, v)
  end
  serialLED:send(chan)

  return update_LEDs, 20 -- run at 50Hz
end

return update_LEDs, 1000
