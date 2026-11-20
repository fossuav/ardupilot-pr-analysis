# PR 35311: AP_Scripting: cache binding method lookups

https://github.com/ArduPilot/ardupilot/pull/35311, opened 2026-11-20 from
andyp1per `pr-scripting-index-cache`, base upstream master `c69185e3ed`.
Two commits: `4cac649b36` (test), `2a61e3d551` (cache).

## What and why

Every `obj:method()` in a Lua script went through the type's `__index` C
function, a linear `strcmp` over the type's method names, on every call.
Each type's `__index` is now a table that caches what the index function
finds (hits only), with a shared metatable that calls the function on a
miss. Found by the 2026-11-20 RP2350 scripting profile in
[../32995/README.md](../32995/README.md) ("scripting CPU profile, a Lua
flight mode at 50 Hz" and its index-cache follow-up), where the name
search was 10% of a 50 Hz script's CPU.

## Measured (bench, RPI_UAVFC, `--enable-stats` builds of #32995's head)

Taken on the patch as first written (equivalent to `8d2bed31c4`), before
the review fixes; those touch only a name's first lookup (a
`luaL_checkstring`, a non-const key) and comments, not the hit path.
Not re-measured on the final code.

| | old | cache |
|---|---|---|
| Scripting thread, 50 Hz perf_mode.lua | 10.3% | 8.5% |
| run best / mean | 1.49 / 2.55 ms | 1.13 / 1.84 ms |
| name lookup (load_function + strcmp) | 1.20 points | 0.08 |
| Lua VM and API | 4.17 points | 3.65 |
| Lua heap in use | 27,364 B | 28,965 B |
| vehicle:get_mode / set_target_angle_and_climbrate | 14.8 / 26.0 us | 5.3 / 10.6 us |

Flash, MatekH743 copter: +432 B on that revision, +436 B on the final
`2a61e3d551`. No STM32 hardware measurement.

## Review

Full /pr-review 2026-11-20: verdict COMMENT, 0 must-fix, 3 should-fix,
2 notes, all fixed and folded in; round two (Codex audit) closed all
eight, and the re-review's one must-fix (CI's Lua language-server check
on `rc:get_channel()` maybe-nil) was fixed with `assert`. Details in
../32995/README.md. A cache that stores unknown names fails the new test
and keeps Rover.Scripting red.

## Local test caveat

Rover.Scripting's MAVLink step and Copter.LuaParamLockdown fail locally on
plain master as well (the system pymavlink is older than master's Lua
MAVLink module expects), so CI is the first full run of those. The
internal test, which carries the new check, reports before that step.

## Files

Workload, sampler, attributor and bench tools:
`../32995/tools/scripting_profile/` (perf_mode.lua, perf_mode_cached.lua,
perf_bench.lua, pcs.py, attrib.py, categ.py, xipctr.py, mav.py).
`index_cache.patch` there is the format-patch of both commits and
`index_cache_pr_body.md` the description as posted.
