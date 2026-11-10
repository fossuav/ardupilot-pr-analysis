# PR #35077 - FLOW_HGT_MIN, rmackay9's cut-down #34292

Analysis archive for [ArduPilot/ardupilot#35077](https://github.com/ArduPilot/ardupilot/pull/35077).

Opened 2026-11-09 by rmackay9 as a cut-down version of #34292, with
andyp1per kept as the author. Head `11c3e8ca09`, six commits on master
`9bd17a6d0f`, 137 lines against #34292's 882. Not our branch: this record
is what our testing found on it and what was posted.

**Read `../34292/README.md` before changing the gate.** Its "Measured and
rejected" tables cover most of the obvious alternatives, and the landing
work below comes from its 2026-09-30 to 2026-10-03 rounds.

## What it keeps and drops, against #34292

Kept: `FLOW_HGT_MIN` in AP_OpticalFlow, sent with each flow sample through
AHRS and the DAL; EKF3 discards a sample below it once takeoff is detected,
and `readyToUseOptFlow()` refuses to start aiding while below. The
innovations are still computed for a discarded sample.

Done differently:

- The replay value rides in `ROFH`, after three explicit `uint8_t` spare
  fields so the format string describes the padding. That fixes the size
  mismatch (44 against 47) that made #34292 add `ROFM` (its 2026-10-11
  note), at 7 bytes more per flow sample in a replay log.
- The gate height is the EKF's height above ground (`terrainState` less
  the vertical position, or the AGL KF), as a slant range along the sensor
  axis with the sensor offset applied. #34292 used the range finder's
  vertical height at the vehicle origin. Both trades were measured on
  #34292 (2026-09-17, "HAGL against the carried range"): HAGL filters noise
  in a low hover (0% of samples under the floor in an 18 cm hover against
  35%) but leaves 1-2 cm of margin on the ground against 3-12 cm.

Dropped: zero flow at rest on the ground, the hold through a range finder
dropout and its 5 s bound, the floor 5 cm above the ground clearance at the
default (so `FLOW_HGT_MIN` 0 now does nothing, which is opt-in), the
withholding on the `EK3_FLOW_USE` 2 terrain path, the Rover and Replay
vehicle-class handling, and #34292's other tests.

## SITL, 2026-11-10 (tier 2)

Two worktrees of the PR head, built for SITL: the head as posted, and the
head plus the change below. Each was run from its own checkout (not the
`/autotest` runner, which tests the primary checkout), with matched terrain
tiles (one 0-byte placeholder in each). Flow-only copter, analog range
finder, `FLOW_HGT_MIN` 0.3, test `OpticalFlowFocusHeightLanding`:

| landing, then left armed on the ground | PR head | with the change | change without the zero (mutant) |
|---|---|---|---|
| LOITER with an origin | "stopped aiding", then "EKF Failsafe: changed to Land Mode" 5.8 s after touchdown (3 of 3) | aiding kept until DISARM_DELAY, 12.6-12.8 s (2 of 2) | aiding kept, 12.8 s |
| LOITER, `FLOW_HGT_MIN` 0 (control) | aiding kept, 12.6 s | aiding kept, 11.8 s | aiding kept, 11.8 s |
| ALT_HOLD, 2 rad/s `SIM_FLOW_OFS_X` on the ground, `RNGFND1_MIN` 0.2 / 0 | "stopped aiding", drift 0.10-0.13 / 0.12-0.13 m | aiding kept, drift 0.01 / 0.01-0.02 m | drift 2.61 / 2.39 m |

`OpticalFlowFocusHeight`, the PR's own test, passes on both builds.
#34292's record has the same mutant at 2.44 m.

A trap for anyone porting #34292's landing check: it counts XKF5
`FIX/FIY/NI` changes as fusions, which holds on #34292, where a discarded
sample never reaches `FuseOptFlow()`. This PR still computes and logs the
innovations of a discarded sample, so they change without fusion (56 in
the LOITER leg on the PR head). Here the legs are judged on "stopped
aiding", the failsafe and position drift instead.

## The change, branch `flow-hgt-min-on-ground`

andyp1per fork, `dded8ebc27`, four commits on the PR head, pushed
2026-11-10:

| commit | what |
|---|---|
| `818dcf4a9c` | AP_RangeFinder: add on_ground() for a reading taken on the ground |
| `550a676a61` | AP_DAL: give the range finder backend on_ground() |
| `7c952361d4` | AP_NavEKF3: fuse zero flow at rest on the ground below the focus height |
| `dded8ebc27` | autotest: check a landed vehicle left armed keeps flow aiding below FLOW_HGT_MIN |

In `FuseOptFlow()`, below the floor with the range finder reading the
vehicle as on the ground (within 5 cm of `RNGFNDx_GNDCLR`, or out of range
low), the sample is copied and zeroed instead of `really_fuse` being
cleared, and `readyToUseOptFlow()` allows aiding there. 50 lines added, 3
removed, in the library code. Copter and Replay build. It is #34292's
2026-10-03 `on_ground()` design without the rest reading.

## Before liftoff (tier 1 by inspection of flight logs, not raised)

`detectOptFlowTakeoff()` sets `takeOffDetected` 1 s after arming on any
gyro rate over 0.1 rad/s or a 0.1 m range rise, and with it this PR's gate.
The concern was that a vehicle sitting armed at idle would start the 5 s
aiding timeout on the ground. In nine takeoffs (six on the Q25 across two
boards, three on SFD-O4: logs 84, 87, 88) the gyro less the EKF's bias first
passed 0.1 rad/s 0.05-0.35 s before the land detector's NOT_LANDED, and
SFD-O4 sat armed 5-11 s on the ground at 0.03-0.05 rad/s. The flag sets at
liftoff, so this was not raised.

## Posted

- 2026-11-10 09:21Z,
  [comment 6763684407](https://github.com/ArduPilot/ardupilot/pull/35077#issuecomment-6763684407):
  the SITL table above, the change and its branch, the other "landed"
  signals #34292 tried and dropped (`onGroundNotMoving` reads moving with
  the motors spinning, height alone, the vehicle flags), and that a
  `FLOW_HGT_MIN` at or below `MAX(RNGFNDx_GNDCLR, 0.05)` has little or no
  effect because the EKF never reads the height below it.
- 2026-11-10 09:25Z,
  [comment 6763750901](https://github.com/ArduPilot/ardupilot/pull/35077#issuecomment-6763750901),
  marked lower priority: the gate's height is dead reckoning with no time
  bound once the range finder stops reporting. On #34292's carried range the
  same dead reckoning held flow off up to 31 s at 13 m real height in SITL
  (#34292, 2026-09-17), hence its 5 s bound. On master
  `getHeightControlLimit()` holds flow-only flight to 0.7 of the range
  finder's maximum less 1 m (derived from the source), so it needs the range
  finder to drop out in flight, or flow alongside GPS.

Not raised, judged fine: the `ROFH` padding, the slant range with the
sensor offset, gating on HAGL rather than the range, and no floor at the
default.

## The AGL KF height, 2026-11-10 (tier 1 source and logs, tier 2 SITL, not raised)

rmackay9 said, off GitHub, that the gate's height comes from the AGL KF
most of the time. Checked against the source, the release tags and the
logs on hand.

Source: the gate uses the AGL KF only with `EK3_OPTIONS` bit 3 set and the
filter valid, which means a range finder sample fused in the last 5 s.
Otherwise it uses `terrainState` less the vertical position, or the
terrain database with bit 2. Bit 3 defaults to 0, and no hwdef, default
parameter file or autotest sets it. The AGL KF reached master on
2026-05-12 (`306d55abad`) and is not in Copter-4.7.2. The wiki lists it
only under future changes.

Logs: parameters read from 3,529 logs, 458 of them flow-aided EKF3
flights. The 56 from firmware other than SFD's all have it off: only two,
4.8-dev builds, carried it, and both have `EK3_OPTIONS` 0. Every log with
it on is an SFD build, whose board default is `EK3_OPTIONS` 92. Older SFD
builds numbered the bits differently (4.7.0-beta6-SFD had the AGL KF at
bit 4), so their bit 3 is not counted.

Time valid, from `XKFA.Valid` in the 146 SFD logs with the current bit
layout (the fork's validity rule is master's 5 s one):

| vehicle | airborne | valid in the air | valid, armed on the ground after landing |
|---|---|---|---|
| Q25 / Q25v1, indoor, flow only | 5736 s | 100.0% | 100.0% (the range finder reads in range on the ground) |
| SFD-O4, outdoor, GPS and flow | 7778 s | 68.1% | 54.3% |

SFD-O4's gaps run to 226 s, almost all above the range finder's reach,
where it reports no data and the gate falls back to the default height.
So "most of the time" holds for the SFD vehicles flying indoors, not for
master's users. Nor does the AGL KF bound the stale height of the second
comment: 5 s after the range finder stops, the gate falls back to the
default height, which has no time bound.

SITL with `EK3_OPTIONS` 8, each run in a fresh worktree as above:

| test | PR head | with the change |
|---|---|---|
| `OpticalFlowFocusHeight` (the PR's) | passes: groundspeed held under 0.5 m/s for 15 s below the floor, 1.26 m/s with no floor, 0.85 m/s above it; the AGL KF valid in every sample of the three bad-flow hovers, at 1.98-2.11 m in a 2 m hover | not run |
| landing, LOITER, `FLOW_HGT_MIN` 0.3 | "stopped aiding" 8.5 s after touchdown, then "EKF Failsafe: changed to Land Mode"; the AGL KF valid throughout, 0.10 m on the ground | aiding kept, 12.8 s |
| landing, LOITER, `FLOW_HGT_MIN` 0 (control) | not reached (the test stops at the first failure) | aiding kept, 11.8 s |
| landing, ALT_HOLD, bad flow on the ground, `RNGFND1_MIN` 0.2 / 0 | not reached | drift 0.23 / 0.04 m, against 0.01 / 0.01-0.02 m with the AGL KF off |

The 0.23 m is the AGL KF coasting after touchdown, which #34457's coast
stop fixes. With `RNGFND1_MIN` 0.2 the sensor reads out of range low from
0.2 m down, so the filter predicts on the IMU alone. It read 0.48 m at
touchdown and climbed to 0.86 m over the next 4.6 s while the vehicle sat
on the ground. That is above the 0.3 m floor, so the gate passed the
2 rad/s bad flow, and the position walked up to 0.53 m. When the filter
went invalid, 5 s after its last range sample, the gate fell back to the
default height, below the floor. The zero flow then took over, and the
drift ended at 0.23 m. #34457 recorded the same coast on SFD-O4 landings
(0.16-1.14 m), but reproduced it only erratically in SITL; this leg
reproduces it on a 0.5 m/s landing. On the PR head's 2.4 m/s LOITER
landing, with the range finder in range, the AGL KF also lagged: 1.12 m
at touchdown, under 0.3 m about 3.5 s later (observed; the cause was not
checked).

Not raised: the PR's own test passes with the AGL KF on, and the one
difference, after touchdown, belongs with the landing change.

## Open

- rmackay9's answer.
- The landing change's test should run its legs with the AGL KF on as
  well as off, and once with #34457 to show the walk removed.
- No Replay against this head. log67 (`../REPLAY_LOGS.md`) is the flight
  that exposed the near-ground floor; its disarm path does not replay
  (#34292's row).
