-- bench: a four-LED NeoPixel strip on the output with SERVOn_FUNCTION 94
local chan = SRV_Channels:find_channel(94)
if not chan then
  gcs:send_text(3, "buzzled: no output has function 94")
  return
end
chan = chan + 1
if not serialLED:set_num_neopixel(chan, 4) then
  gcs:send_text(3, "buzzled: set_num_neopixel failed")
  return
end
gcs:send_text(6, string.format("buzzled: strip on output %d", chan))
local function update()
  serialLED:set_RGB(chan, -1, 0, 0, 32)
  serialLED:send(chan)
  return update, 500
end
return update, 500
