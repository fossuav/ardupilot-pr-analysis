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
