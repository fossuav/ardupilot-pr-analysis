# PR #33569 - EK3_FLOW_GAIN_H: configurable optical-flow nav gain detune height

Analysis archive for [ArduPilot/ardupilot#33569](https://github.com/ArduPilot/ardupilot/pull/33569).
Branch `pr-flow-gain-h` (andyp1per fork), base `master`, head `d5eacd52fd`,
one commit (squashed 2026-09-29). The flight evidence is the PR
description's (tier 1); no logs are committed here.

## Status (one line)

Open. One parameter replacing a hard-coded constant, default preserves
master's behaviour; the parameter-index reuse question is settled by how
`AP_Param::scan` loads records.

## The problem

With optical flow, `getEkfControlLimits` scales the navigation gain by
`4 / max(HAGL, 4)`, so the gain detunes above 4 m. The 4 is hard-coded. On
a vehicle that has to hold at height (the PR description reports drift
against hold at about 40 m) there is no way to move the knee.

## The conclusion and why

Replace the 4 with `EK3_FLOW_GAIN_H`, default 4, so the default is a no-op.
Values below 1 are treated as 1; `@Range 1 40`, fixed per peterbarker's
2026-06-26 review. EKF2 keeps its constant.

Rejected in the PR: a floor on the scaler instead of moving the knee. It
breaks the 1/HAGL shape at the top of the range.

## Key findings

### Parameter index 59 is reused safely

Index 59 was `GSF_DELAY`, an `AP_Int16` that was never in a stable release.
`AP_Param::scan` only loads a stored record whose type matches, so an old
`GSF_DELAY` value is not read as this `AP_Float` (derived from the source,
not measured). An earlier commit message claimed the opposite; that claim
was wrong and was corrected before the squash.

### Flight evidence

The drift against hold at about 40 m is quoted from the PR description
(tier 1, real flight); the logs are not named or committed here.

## What is here

```
33569/
  README.md    <- this file
```

## Reproduce

No SITL A/B is recorded here. The change is checked by building and by the
default being identical to master's constant:

```
git checkout pr-flow-gain-h
./waf configure --board sitl && ./waf copter
```

## Branches and people

- `pr-flow-gain-h` - the PR branch (one commit).
- Author: @andyp1per. Review: @peterbarker (2026-06-26, the range).
- Related: `../33318/agl_kf_speed_cap.md` discusses the scaler this makes
  tunable.
