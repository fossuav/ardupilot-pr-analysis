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

## Open

- Flight on the SFD beta with the reviewed version (the beta carries the
  topup2 version, which exempts only recent air data fusion).
- No QuadPlane or drag fusion test.
