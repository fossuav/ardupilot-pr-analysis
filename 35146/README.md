# PR #35146 - EKF3 stops aiding at once on a source set with no horizontal source

Analysis archive for [ArduPilot/ardupilot#35146](https://github.com/ArduPilot/ardupilot/pull/35146).

Opened 2026-11-12 at `f7dc1426d7`, three commits on master `eec26aee01`,
branch `pr-ekf3-no-horiz-source`. From the SFD beta's refresh15 topup2
(`75a0d0e5a2`, `7f7108a9ef`, test `959baa8c4a`), where it was carried
in the #33484 area; a standalone PR by decision, as it needs nothing
from #33484. Unflown.

## What it does

A source set with nothing to measure the horizontal position or
velocity (`AP_NavEKF_Source::haveHorizPosVelSource()` false) ends
absolute and relative aiding in the same update as the switch. Before,
the EKF dead reckoned on it as on a dropout: 15 s in absolute aiding,
5 s in relative aiding. Absolute aiding carries on where air data can
carry dead reckoning: while the wind states are estimated, or airspeed
or drag was fused in the last 7 s (`minTestTime_ms`).

The helper commit is the same patch (patch-id `680cf4c4679f`) as
#32514's first new commit of 2026-11-12, which moves
`has_horiz_pos_vel_source()` onto it.

## Flight evidence that motivated it (tier 1, from the SFD record)

On the throw quad's logs 15-16 (2026-11-12, topup1), held still in the
hand after arming on THROW_SRC_INI's set with nothing horizontal, the
EKF velocity was over 1 m/s out 4-7 s after arming and 5-9 m/s by
12-13 s; log15's first throw braked on it and struck the ground, and on
log16's first throw the 15 s timeout fell at the release (`../33484/`,
`../32475/`). Replay against topup1 on the 4.7-based beta: 352 of 355
logs unchanged; two throw flights stop aiding at the switch into throw,
throws within 0.1 m/s; a flight switched to a set with nothing stops
aiding at the switch instead of 5 s later.

## SITL, 2026-11-12 (tier 2)

| test | with | without |
|---|---|---|
| EK3_NoHorizontalSourceStopsAiding, stop after the switch from the GPS set / from a flow set, timed from the log (EV 87 to "stopped aiding") | 0.00 s / 0.00 s | master 14.97 s / 4.96 s; relative branch reverted 0.00 s / 4.93 s |
| EK3NoHorizontalSourceDeadReckons, plane with ARSPD_USE 0, 20 s on the empty set | no stop | exemption by recent air data only: "stopped aiding" 20 ms after the switch |

The first version of the copter test used 2 s statustext waits, which
passed on a mutant whose stop came 4.9 s after the switch: timing from
the log replaced them.

## Review rounds (2026-11-12)

- Round 1 (Claude reviewer, Codex cold read): must-fix, planes with no
  airspeed sensor lost synthetic airspeed dead reckoning, as that
  fusion starts only once the wind is no longer observable, about 7 s
  after a switch, and the exemption tested recent air data fusion.
  Fixed with the wind state exemption. Should-fix: the helper's comment
  said "fuses" for a configured source (reworded; GPS velocity with
  POSXY not GPS, and flow with EK3_FLOW_USE not 1, still count, the old
  conservative direction); Replay evidence labelled as 4.7; a relative
  aiding leg added; comments trimmed.
- Round 2: must-fix, a QuadPlane's assist turns fly forward off, and
  with it the wind states, so the stop fired mid-assist and could not
  be undone on that set. Recent air data fusion was added back beside
  the wind states. Untested in SITL. Messages corrected: relative aiding
  does fuse air data, but its timeout never counted it; the Replay
  counts; entering no aiding still zeroes the velocity and takes the
  height from the baro, now at the switch.
- Not raised as code: a three-position switch whose middle is such a
  set now costs that stop whenever it rests there; stated in the PR.

## 2026-11-13: flown at every switch into THROW (tier 1), the stop keeps its height (tiers 1b, 2)

Flown on the SFD beta's refresh16 topup1, the throw quad's logs 17-19:
every switch into THROW printed "EKF3 IMU0 stopped aiding" within 4 ms,
before arming (seven switches). The reviewed `c47b3cf03e` has flown.

AP-Review at `f7dc1426d7`: the stop goes through the AID_NONE entry,
which sets the height from the raw baro, where height fusion takes out
the baro's offset from the height source in use and, with
`EK3_OGN_HGT_MASK` bits 0 and 2, adds the GPS datum correction. A copter
in ALT_HOLD on GPS height with the baro 5 m off dropped 3.4 m at a 3 s
switch to an empty set. First the commit #32768 carries, taking the
offset out of that height, was carried here (`1c0016f360`: 0.07 m
against 3.3 m); AP-Review then measured baro height with mask 5 and a
drifted baro still stepping 3.4 m (a 2.2 m drop). Replaced by keeping
the height at this PR's own stop, marked where the stop is made: the
stop at the switch, or when the air data that carried dead reckoning on
such a set stops. A stop on the loss of attitude aiding still resets.
A first version that skipped the reset whenever the set had no
horizontal source would also have changed a plane whose air data dead
reckoning on such a set later times out (a cold review), so it is
narrowed to the stop itself. The carried commit is dropped.

EK3_NoHorizontalSourceKeepsHeight (tier 2): within 0.00 m on GPS height
with the baro put 5 m off in flight, and 0.08 m on baro height corrected
to GPS after a 3 m drift; with the reset, 3.30 m and 1.87 m, each case
run on its own. The beta carries #32768's offset change, so there the
GPS case holds without this (0.07 m) and the drift case moves 1.80 m
against 0.09 m. Replay of 369 logs through the beta with and without
(tier 1b): 364 identical; the throw quad's logs 13-16 and one indoor
drop throw move, the EKF height by at most 0.32 m and its error to GPS
height by at most 0.03 m.

Heads: `f7dc1426d7`, `1c0016f360` (the carried commit), `314b2a8a31`
(the kept height, `7ce21209cd`, and its test).

## Open

- The kept height has not flown; the beta carries it from topup2.
- No QuadPlane or drag fusion test.
