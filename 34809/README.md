# AP_OSD: show a script's OSD writes in the same frame as the screen

**Open as [#34809](https://github.com/ArduPilot/ardupilot/pull/34809)**,
opened 2026-10-18 from `andyp1per/pr-osd-script-one-flush` at
`466ca4d393`, three commits on master `f48fabc426`. Record written
2026-10-18.

## Why

Found while writing the SFD demo applet that lists the PRs in play on the
OSD (`ap_lua/sfd_pr_osd.lua`). The Lua OSD override from #32045 has a
script call `osd:draw_screen()`, write its items and `osd:flush()`.
`draw_screen()` ran `AP_OSD::update_osd()`, which clears, draws and
flushes every backend, so each update sent the normal screen alone and
then the screen with the script's items. Over MSP DisplayPort in SITL,
half the frames lacked the script's items. Master was checked for a fix
first: none. The two later scripting-OSD commits (`32a139d534` OSD thread
semaphore, `f3594436f2` outgoing DisplayPort packets) do not touch it.

## Change

- `cb3c9538b8` AP_OSD: `update_osd(bool flush_scripting_backend = true)`;
  scripting's `draw_screen()` passes false, so `_backends[0]` (the one
  `scripting_get_backend()` returns) is left for the script's `flush()`.
  Other backends flush as before.
- `7cf21664ae` AP_Scripting: `docs.lua` says `draw_screen()` clears and
  draws, and `flush()` shows it.
- `466ca4d393` autotest `ScriptingOSDDrawScreen`.

## Evidence

SITL, tier 2. The test fails on master (48 of 96 frames in 5 s without
the script's text) and passes with the change (49 of 49; 48 of 48 on the
final head). `ScriptingOSD` skips without SFML, as on master.

## Review before opening

A reviewer agent and Codex (cold read): nothing blocking. Folded in: the
commit body says a VTX *can* show flicker (frames were counted, goggles
not tested); a script that never flushes also stops the MSP DisplayPort
heartbeat and port servicing while it holds the OSD (`flush()` does
both); docs say `draw_screen()` clears first; one comment at the
declaration. The API is in master only (not ArduPilot-4.7), so this is
framed as a fix to #32045.

Pre-existing, not in this PR: with `OSD_TYPE` 0 and `OSD_TYPE2` set,
`init()` leaves `_backends[0]` null with `_backend_count` 1 and
`osd_thread()` dereferences it. A separate fix.

## 2026-10-25: the port servicing never worked from a script

The review note above says a script that never flushes stops the
DisplayPort heartbeat and port servicing, because `flush()` does both.
That was only half right on hardware: when a script calls `flush()`, it
runs on the scripting thread, which cannot read the uart (ChibiOS and
ESP32 let only the thread that opened it read), so the VTX's requests
went unanswered even while the script flushed. A DJI O4 on SFD-O4 never
saw arming with `sfd_pr_osd.lua` running. Fixed separately as #34882,
which services the link from the OSD thread; see ../34882/README.md. The
two PRs touch different parts of `AP_OSD.cpp` and apply in either order.

## 2026-10-30: the heartbeat sentence reworded after #34882

The bot's round at `d65d3b4baa` (COMMENT, nothing blocking) caught the
AP_OSD commit body still saying a script that never flushes stops the
MSP DisplayPort heartbeat "and services the port". Since #34882 merged
(`623be5b208`), `osd_thread_update()` services the link on every OSD
loop and `flush()` only grabs and draws, so MSP replies keep going. The
body and the description's matching sentence now say only the
heartbeat stops. Rebuilt by cherry-pick as `r1030/34809` (`78cbd2824a`,
`2dd30935b9`, `ea1a881ad7`), tree identical to `d65d3b4baa`.

Pushed 2026-10-30 to andyp1per with a lease on the old head: `d65d3b4baa`
-> `ea1a881ad7`.
