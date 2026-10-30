# Flow lane: re-entering relative aiding zeroes a velocity that was right (EKF3, upstream)

Not a PR yet. Found 2026-10-30 on SFD-O4 log61 (3408138/639) and seen six
more times on log65 (3408138/646), both on the SmallFastDrone 4.7.2 beta
`52b1d36f`. Real-flight numbers inline; no logs committed.

## Status (one line)

Upstream behaviour, characterised on two real flights; both replay exactly
on the beta. No fix written. It is the root of the SFD-O4 Loiter that did
not stop (log61), with the terrain lookup in `../33585/` deciding which way
the velocity was wrong when the pilot switched.

## What happens

Flow is not fused past 45 deg of tilt (`tiltOK`, `DCM33FlowMin` 0.71). On a
flow-only lane (core 1 under `EK3_SRC_OPTIONS` 8) a sustained steep attitude
in acro therefore starves it of flow. After 5 s `flowFusionTimeout` takes it
from AID_RELATIVE to AID_NONE, `readyToUseOptFlow()` is still true, so the
next cycle puts it back into AID_RELATIVE, and the mode change calls
`ResetVelocity()`, which zeroes horizontal velocity whenever the mode is not
AID_ABSOLUTE (`AP_NavEKF3_Control.cpp` `setAidingMode()`,
`AP_NavEKF3_PosVelFusion.cpp` `ResetVelocity()`). Derived from the source;
the timings and speeds below are measured. In the log it is the pair
"EKF3 IMU1 stopped aiding" / "started relative aiding", 5-6 ms apart.

The velocity it discards was good. Five seconds on the IMU alone had kept it
within about 0.5 m/s of GPS:

| Log | Drop | GPS speed | Core 1 before | Core 1 after | Tilt over 45 deg in the 5 s before |
|---|---|---|---|---|---|
| log61 | 220.5 s | 18.6 m/s | 17.9 (220.0 s), 18.1 | 0.8 | from 215.7 s (innovations frozen) |
| log65 | 51.4 s | 18.7 | 18.9 | 0.3 | 100% |
| log65 | 113.4 s | 22.2 | 17.5 | 4.3 | 100% |
| log65 | 128.2 s | 18.5 | 39.2 (already wrong) | 0.7 | 100% |
| log65 | 144.9 s | 12.9 | 11.4 | 2.5 | 56% |

(Times are normalised to the first message, as `log_extract.py` prints them.
log65 also dropped at 78.0 s and stayed out for 4.6 s, re-entering at 82.6 s
with core 1 at 0.1 against GPS 18.2.)

## What repairs it, and when nothing can

Nothing re-anchors a zeroed flow velocity except #33484's single-axis
lockout reset, and that needs the AGL KF valid and a range sample within
500 ms. log65, mostly inside the range finder's reach, had three, each
repairing a velocity zeroed by a re-entry (`../33484/`, 2026-10-30): 4.7 to
18.9 m/s, 0.1 to 20.7, 1.7 to 16.1. Where no reset followed, core 1 stayed
wrong for 8 s or more (after 113.4 s: 4-8 m/s against 16-25).

log61 was above the 15 m range finder, so no reset could run. Core 1 ran
away to 37-48 m/s between two more drops (235.3 and 240.3 s), ended 200-340 m
from GPS, and read 0.3-0.9 m/s while flying at 13 m/s when the pilot
selected Loiter at 255.8 s. Loiter seeded its velocity I term from the
31 deg lean (6 m/s/s), saw no motion and held the lean as if into wind
(PIDE.I 6.0 rising to 8.9). Loiter on the GPS lane later stopped from
10.5 m/s in 1.8 s, so Loiter is not at fault.

## Prior art in the stack

#33568 already exempts one edge: it skips the velocity and position resets
on AID_ABSOLUTE -> AID_RELATIVE (`PV_AidingModePrev != AID_ABSOLUTE ||
PV_AidingMode != AID_RELATIVE`), because a GPS-to-flow fall back on a
moving vehicle stepped velocity 5.9 m/s (`../33568/`, 2026-09-15). The
re-entry here is the same mistake on the NONE -> RELATIVE edge.

## Fix to try (not written, not measured)

Keep horizontal velocity across a NONE -> RELATIVE re-entry when the lane
left RELATIVE moments ago, inflating its variance for the time spent on the
IMU alone rather than resetting it; or do not let the timeout fire while the
tilt gate is the only reason flow is not being fused. Which is better is a
measurement, not an argument.

## Replay

Both logs replay exactly on the beta (log61 core 1 to 0.1 m/s through
256 s; Replay built at smallfastdrone `0cb49e7dfb`, which is `52b1d36f` plus
an autotest commit). The A/B owed: the fix against the flown code on log61
(core 1 speed at the 255.8 s Loiter switch, GPS 13.4 m/s) and log65 (core 1
against GPS after each of the six drops). Recorded in `../REPLAY_LOGS.md`.

## Rule

Candidate, not queued: a reset replaces a state only with an estimate
better than the one it discards. Time since the last measurement alone is
not evidence the state is bad. Offered 2026-10-30, not yet confirmed.
