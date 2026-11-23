# PR #35312 - EKF3 keeps a landed flow lane's velocity variance honest

Analysis archive for [ArduPilot/ardupilot#35312](https://github.com/ArduPilot/ardupilot/pull/35312).

Opened 2026-11-20 at `6b8a26e145`, branch `pr-flow-lockout-landed`,
stacked on #35307 (`80e1cb5824`): `78944cda59` (AP_NavEKF3) and
`6b8a26e145` (autotest). On by default, as a fix for a divergence.

## What it does

While a flow lane is armed, the vehicle reports it has landed, takeoff is
not detected, the range is current and reads within 0.1 m of the ground
clearance, the horizontal velocity variance is held at
`sq(MIN(EK3_NOAID_M_NSE, 1))` (the stationary zero velocity noise) or the
squared speed estimate if more, capped at 1e3. The velocity is never set.

## Why

On the ground the flow is scaled by the ground clearance and, before
takeoff detection, replaced by zero, which is fused at the flow's own
noise. A touchdown that leaves a few tenths of a m/s of error then
predicts several rad/s; one axis is rejected until disarm while an accel
bias walks the velocity away. Since #35105 a landed Copter is on the
ground while armed, which clears takeoff detection, so #33484's lockout
recovery does not run there.

## How the design got here

1. Letting the recovery reset while landed (first version): review found
   it opened on the bench (landed holds disarmed) and that the reset set
   the velocity from the landed flag alone, as the flow is already zeroed
   there: a fabricated measurement from a flight-state flag.
2. Raising the variance only while an axis was locked out: cleared 6 of 7
   replayed landed runaways, missed one whose AGL KF restart never
   confirmed under the beta's floor hold (gate required a Good range
   state) and whose error was already 7-12 m/s at landing (1 m/s variance
   too small), and made a hopping log worse in flight: once unlocked, the
   zero flow at 5 cm collapsed the variance to about 1 cm/s and the next
   liftoff rejected the real flow.
3. Final: hold the variance for as long as landed (not only in a
   lockout), accept any non-stale range, cover the speed estimate.

## Evidence

- SITL: two legs (AGL KF off and on), landed and armed, accel bias pulse
  3 m/s^2 then 0.3 residual. Without the change the axis is shut out and
  both cores reach 5.2 m/s in 12 s; with it the flow is never shut out
  and the velocity is back within 0.3 m/s 1.5 s after the pulse (peak
  0.91 m/s during it). The other 15 Copter flow tests pass.
- Fleet Replay (tier 1b, 423 logs, landed flag rebuilt from each log's EV
  LAND_COMPLETE/NOT_LANDED, since none carries RFRN Flags2): of 117 lanes
  landed and armed for over 3 s, 7 exceeded 0.5 m/s on the ground (worst
  15.3); with the change 0. GPS p95 lower on 7 cores, higher on 8, summed
  -1.2 m/s. One hopping log 2.86 -> 3.84 m/s p95: its flow lane is
  rejected through most hops in both builds, differences between hops.

### Superseded 2026-11-23 by a recount on distinct logs

The 423-log figure counted cached copies of the same flights, and it only holds
on a build carrying #32232. Recounted on 385 distinct logs, the landed flag
rebuilt from events, hold on against hold off, 93 lanes landed for over 3 s:

- With #32232 (the SFD 4.7 beta): 8 lanes over 0.5 m/s on the ground (worst
  15.3), 1 with the hold (0.75). GPS p95 lower on 4 cores, higher on 2, summed
  -13.8 m/s, -13.1 of it one flight.
- On this PR's own stack: the hold changes none of those lanes. In six of the
  seven logs the range finder is out of range low for the whole landed spell,
  so the range is stale and nothing is held. SITL's range finder reads the
  floor, so the autotest does not show this.

## Found along the way

- #35307 bug, fixed in `80e1cb5824`: a pending height source switch let
  the recovery scale by the baro's height for one update when the range
  finder came back as the height source (about one SITL run in five).
- Not covered here: a lane quality-latched into AID_NONE before landing
  drifts on the ground when idling motors keep onGroundNotMoving false.
- A range finder that reads below its minimum on the floor needs #32232's
  substitution; on master its range is stale and nothing is held.

## 2026-11-20: restacked, pushed `64196a8a82`

Carried onto #35307's `0fec57455e` with no change of its own. With
#33484's new-reading test, an assumed or held range now reads stale here
too, so nothing is held on one.

## 2026-11-23: first flight, log110 (boot 754), tier 1 and 1b

Flown on the SFD 4.7.3-beta3 build `b9b81e7703`, which carries this PR at
its 2026-11-20 head. An outdoor GPS and flow quad, flow on core 1, GPS
primary throughout. It landed in LOITER at about 0.6 m/s and sat armed for
12.7 s with the range finder out of range low.

An instrumented Replay, exact to 1.9e-6 m/s against the flight, shows the
hold ran on 235 of the 238 flow fusions while armed and landed. The other
three had a stale range. The landing did not need it. From LAND_COMPLETE
to disarm:

| Replay | speed median / max (m/s) | NI max |
|---|---|---|
| with the hold | 0.012 / 0.069 | 5 |
| hold removed | 0.003 / 0.076 | 7 |

So the code path has flown and did no harm, and its protection against a
touchdown error has not been exercised in flight.

## 2026-11-23: second flight, log111 (boot 756), tier 1 and 1b

The same build, this time with the flow lane primary. The hold ran on 188
of the 191 flow fusions from LAND_COMPLETE to disarm (11.0 s). Again the
landing did not need it: at most 0.030 m/s and NI 1 with the hold, 0.031
m/s and NI 2 with it removed in Replay.

## 2026-11-23: lift-off from armed, log112 (boot 759), tier 1 and 1b

The case this PR protects, flown on the flow lane: three lift-offs from
armed after 1.7-6.9 s on the ground, sticks centred, with at most 2.7 deg
of tilt and 0.09-0.30 m of drift by GPS. The hold ran on 356 of the 372
flow fusions on the ground across seven landed spells.

None of these touchdowns left the error the hold is for. With it removed
in Replay the landed speed changes by at most 0.011 m/s, and the flow
lane's velocity error in the 3 s after lift-off is 0.02-0.10 m/s lower on
six of the seven lift-offs (0.13-0.33 m/s against 0.20-0.42). So the
lift-off has flown clean with the hold, its protection is still not
exercised, and on these flights it costs a little at lift-off.

## 2026-11-23: AP-Review round 2 answered, pushed at `ab1cbb1a73`

On top of `0fec57455e` for #35307: `16ea0b4d9e` (builds with the range finder
compiled out), `8c1d9763ac` (each deferral reason has its own report timer) and
`4bcfc44274` (the both-axes leg leaves out the reset its own cleanup causes). For
this PR: `6926aa57d3` compares the range as the sensor read it with the ground
clearance, and `ab1cbb1a73` adds a leg with the sensor 0.15 m below the IMU, where
the flow is shut out without the fix.

EK3_FlowAxisLockoutRecovery 24 of 24 (21 of 24 before `4bcfc44274`, on the leg's
own cleanup). Five other flow and Replay tests pass, and the range-finder-off and
AGL-KF-off builds build. Replay of 385 distinct logs: no EKF state changes, 22
logs print more deferral messages. Left as it is: flow slower than 4 Hz gets no
lockout recovery, which is the behaviour without #33484.

## 2026-11-23 (later): the test fix moved to #33484, pushed `36fd5a2254`

Same tree as `ab1cbb1a73`. This PR's four commits are now `2dd57ed0b9`,
`9b39eb98b6`, `7d626bab2c` (was `6926aa57d3`) and `36fd5a2254` (was
`ab1cbb1a73`), on #35307's `186c96fa4a`. There `16ea0b4d9e` is now
`28f9a00d81` and `8c1d9763ac` is `186c96fa4a`; the leg fix `4bcfc44274` is
`255fe24724` on #33484.

The description was updated and posted the same day: four commits, the
recount on 385 distinct logs, and that real logs need #32232. The old line
about a run of one-second hops was removed, as the recount no longer shows
it. CI on this head had not finished when this was written.

Reply drafted and held at Andy's word, 2026-11-23, not posted:

> The build guard is in 28f9a00d81, and the range finder compiled out now builds. 7d626bab2c compares the range as the sensor read it with `RNGFND1_GNDCLR`: with a sensor 0.15 m below the IMU the new leg (36fd5a2254) has the flow shut out without it and holds with it. 186c96fa4a gives each deferral reason its own report timer, so "range stale" no longer hides "range restarted", and 255fe24724 stops the both-axes leg checking the reset its own cleanup causes: the lockout test passed 24 of 24. 385 distinct replayed logs show no change in any EKF state. Flow slower than 4 Hz is left as it is: it gets no lockout recovery, which is the behaviour without #33484.
