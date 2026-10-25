# AP_OSD: answer MSP DisplayPort requests from the OSD thread

**Open as [#34882](https://github.com/ArduPilot/ardupilot/pull/34882)**,
opened 2026-10-25 from `andyp1per/pr-osd-displayport-script-replies` at
`93244134b6`, two commits on master `e96bd9053e`. Record written
2026-10-25.

## Why

Operator report, 2026-10-25 (tier 1, not logged): on SFD-O4, flying the
SFD beta with the PR OSD applet (`ap_lua/sfd_pr_osd.lua`) drawing the OSD,
the DJI O4 never saw the vehicle arm and the goggles stayed in low power,
while the OSD itself showed. It started when the applet was enabled.

The O4 polls MSP_STATUS for the arm bit (bit 0 of the flight mode flags).
On MSP DisplayPort the backend read and answered those polls in
`flush()`. Any `osd:` call from a script, getters included, takes the
scripting override (`scripting_get_backend()`), the OSD thread stops
drawing and flushing, and the script's own `flush()` runs on the
scripting thread. On ChibiOS (and ESP32) only the thread that last called
`begin()` on a uart can read it - the OSD thread, through
`osd_thread_run_once()` - so `available()` reports 0 to the scripting
thread and the polls are never answered. Writes have no owner check, so
the OSD still shows. Derived from the source (`UARTDriver::_read()` and
`_available()` owner checks); the operator report is the only hardware
evidence so far.

The override came in with `b269581dcc` (#32045) and is on master only;
the SFD beta carries it. It is not #34809's doing: the override answered
from the script thread from the start.

## Change

- `3249b048cc` AP_OSD: new backend hook `osd_thread_update()`, called by
  the OSD thread on every update whether or not a script holds the
  override; DisplayPort's servicing (`process_incoming_data()`,
  `process_outgoing_data()`) moves into it from `flush()`, which now only
  draws. Without a script nothing changes but the order within a cycle
  (draw, then service).
- `93244134b6` autotest `ScriptingOSDDisplayPortReplies`.

## Evidence

SITL (tier 2), master `e96bd9053e` plus the change, 2026-10-25:

| case | result |
|---|---|
| the change | passes, about 15 s |
| new hook not called | fails: 0 MSP_STATUS replies in 3 s |
| master unfixed | **passes**: SITL's uart has no owner check, so the script's `flush()` answers |
| the change, script stops drawing after 5 s | fails: "the script drew 0 times in 3 s" |

So the test guards the new servicing path and the script's hold on the
OSD; it cannot see the original bug, which needs a uart with ChibiOS's
owner rule. `MSPDisplayPortVTXConfig` and `MSPVTXConfig` pass;
`ScriptingOSD` skips without SFML, as on master.

Before the fix, a probe on the SFD beta without a script (2026-10-25,
`5b70a27117`) read the arm bit 0 disarmed, 1 armed and 0 again, with the
operator's `MSP_OPTIONS` 8 and `VTX_*` settings - which is what pointed at
the script rather than the arm bit.

On the SFD beta (refresh11 topup2, `a2d130878c` + `59386e92ba`, pushed
2026-10-25) the same six MSP/OSD tests pass. **Bench test on the O4
owed**: arm with the applet running and check the goggles leave low power.

## Measured and rejected

| change | argument for | why rejected |
|---|---|---|
| Test at `SIM_SPEEDUP` 1 throughout, set as a parameter before the restart | Faster than real time no reply got through, with or without a script | Works (60 s), but boot and arming checks then run in real time too; `context_set_speedup(1)` after `wait_ready_to_arm` keeps the speedup in step with the harness and cuts it to about 15 s |
| Rely on the "script running" STATUSTEXT to show the script holds the OSD | Simple | Sent before the first `osd:` call; a script that failed afterwards would hand the OSD back after the 2 s override timeout and the normal OSD would answer. Each window now needs the script's own write-string frames (Codex and the reviewer agent, both should-fix) |

The no-reply finding first looked like a defect in the change: master's
`c621b8fe4e` (2026-08-05, not in 4.7) drops an MSP reply that does not
fit in the transmit buffer, and faster than real time the test client
cannot drain the redraws, so on master no reply got through even with
scripting off (with a script: 8151 DisplayPort frames, 0 replies in 3 s).
The SFD beta,
without `c621b8fe4e`, answered at full speed. Whether redraws can starve
replies the same way at 115200 baud on hardware is not measured.

## Review before opening

A reviewer agent and Codex (cold reads of each commit and the whole
diff): nothing in the C++. Folded in: the test proves the script is
drawing in each window; MSP connects after `wait_ready_to_arm`; real time
only for the polling; a one-line comment that the servicing relies on
`_sem` (a reply is three uart writes and a script's frame must not be
split); commit message names ESP32, the getters, and `available()`.
Left: making SITL's uart enforce the owner rule, which would let a test
see this class of bug (separate change); the null `_backends[0]` with
`OSD_TYPE` 0 and `OSD_TYPE2` set, pre-existing and covered by #34497.

"Checked by a human programmer" is left for the author.

## Reproduce

```sh
# in an ArduPilot checkout at 93244134b6
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py test.Copter.ScriptingOSDDisplayPortReplies
```

The bug itself needs hardware: an MSP DisplayPort VTX that polls
MSP_STATUS (a DJI O4), `SERIALn_PROTOCOL` 42, `OSD_TYPE` 5, and any script
that calls an `osd:` method.
