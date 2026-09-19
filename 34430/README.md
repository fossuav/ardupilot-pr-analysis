# PR #34430 - AP_Relay: don't re-apply a relay pin's mode on every read

[ArduPilot/ardupilot#34430](https://github.com/ArduPilot/ardupilot/pull/34430),
branch `andyp1per/pr-relay-read-no-pinmode`, opened 2026-09-18 at
`31df8dcb47` on master `9165d22419`. One commit, AP_Relay only, +14/-1.

## What it does

Every relay read called `pinMode()` first, and `set()` reads before it
writes, so the mode was re-applied on every access - every output loop for
Rover's brushed-reverse relays, the ICE update rate, and the stream rate
whenever a GCS requests `RELAY_STATUS`. A per-pin `Bitmask<256>` now sets
the mode on a pin's first read only; writes keep master's `pinMode()` then
`write()`, and a write happens only when the commanded level differs from
what the pin reads.

Where it mattered, verified in the tree (derived from the source, not
measured): `GPIO_Sysfs` writes "out" on every `pinMode()`, which the kernel
ABI takes as output low, so on Navio2, PilotPi and the other sysfs boards a
read could switch an ON relay off; `GPIO_RPI_BCM` drops the pin to an input
and back. On ChibiOS STM32 re-applying an output mode never touched ODR, so
there it only saves writes.

It came out of #32995's RP2350 field testing, where two relays are the
video and 5V regulator enables; see
[../32995/field-test-2026-09-17-video.md](../32995/field-test-2026-09-17-video.md)
for the investigation, the three `/pr-review` rounds and the table of
rejected designs. The same patch is `6d2ba24fc3` on the RP2350 branch
(`33228ce5a8` since its 2026-09-19 rebase onto `368dc0c428`), which drops
its copy once this merges.

## Evidence

- SITL: Rover.ServoRelayEvents and Plane.TestRCRelay pass at `31df8dcb47`,
  but SITL only models pin modes on pins 0-7 and the relay pins are 13 and
  14, so they show behaviour unchanged rather than exercising the path.
- A throwaway run with the relays on SITL pins 5 and 6 and
  `RELAYn_DEFAULT` "no change" (SITL drops writes there until
  `pinMode(OUTPUT)`) shows the first command configures the pin, at
  `31df8dcb47`. The same run then fails a later `RELAY_STATUS.on == 0`
  assertion identically on master, because a never-commanded "no change"
  relay reports its pin's level - a harness assumption, not the change.
- Builds: SITL rover/plane, CubeOrange copter and RPI_UAVFC copter, 0
  warnings.
- **Owed:** a hardware test on a sysfs or BCM Pi board (Navio2, PilotPi)
  with a relay ON while `RELAY_STATUS` streams.

## Known and deliberate

Once a relay has used a pin, a read does not take it back if another
feature reconfigures it (Lua `gpio:pinMode`, AP_Button, an RPM pin); the
relay takes it back the next time it is asked for a level the pin does not
already read. A failed first `pinMode()` on sysfs is retried at that next
write, not on every read. Both only arise when two features share a pin.
