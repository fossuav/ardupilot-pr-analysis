# PR #34360 - EKF3: fix the sign of the SRTM height used for flow scaling

Analysis archive for [ArduPilot/ardupilot#34360](https://github.com/ArduPilot/ardupilot/pull/34360).
Extracted from #33585. Branch `ekf3-srtm-flow-scale-sign` (andyp1per fork),
three commits, head `affdf29bf1`, base master `4891432f35`. Opened
2026-09-10. It now carries a second master defect in the same expression:
`terrain_srtm_alt_ms` is never-written-zero for the first five seconds of
uptime, so the age test passes against a terrain altitude the core has not
received. That guard previously existed only inside #33585; moving it here
makes this the complete "the SRTM path on master is wrong" PR and lets
#33585 drop it.

## Status (one line)

`FuseOptFlow` differences an up-positive terrain database height against a
down-positive position state, so above the rangefinder range with
`EK3_OPTIONS` bit 2 the optical flow scale height is wrong by 2 x the
terrain elevation relative to the origin, and over ground below the origin
it collapses to `rngOnGnd` and flow is rejected outright.

## Why it is its own PR

The defect is master's, not #33585's - `../33585/` recorded that on
2026-09-07 - but it was only ever fixed inside #33585, a large PR that has
been through seven review rounds on unrelated ground. Three things follow:

- #33585's own preferred path is the terrain database ("terrain-where-covered
  with flat ground as the fallback", after `a874302eee` widened
  `writeTerrainData()` to bit 2 or bit 5). That path runs on this expression.
- `../34361/` reached the same expression independently
  and had to get the convention right to serve `getHAGL()`.
- Anyone setting bit 2 on master today is affected, with no fix in sight
  until #33585 merges.

## The defect

`AP_NavEKF3_OptFlowFusion.cpp`, master:

```cpp
heightAboveGndEst = MAX((terrain_srtm_alt - pd), rngOnGnd);
```

`terrain_srtm_alt` is height above the EKF origin, **positive up**:
`AP_AHRS::writeTerrainAMSL()` computes `alt_amsl_m - origin.alt` and the core
stores it verbatim. `pd` is `position.z`, **positive down**. The neighbouring
default is right because `terrainState` is itself a D coordinate
(`position.z + rngOnGnd`), so one variable's two branches were being
differenced in opposite conventions. Correct form: `(-pd) - terrain_srtm_alt`.

The error is 2 x `terrain_srtm_alt`, which is why it is invisible at CMAC,
where the origin sits on the terrain, and why no existing test caught it.

## Measured 2026-09-10

This is the measurement `../33585/` asked for and could not get: "the branch
needs gndOffsetValid false with terrain still valid, and a SITL probe here
did not reach it". Reaching it needs the rangefinder out of range **and**
terrain coverage, which is what the Kalaupapa run does.

SITL, `--home KalaupapaCliffs`, `RNGFND1_MAX=8`, `EK3_OPTIONS` bit 2,
terrain enabled, holding 40 m above an origin the ground falls to 160 m
below (true AGL 200.32 m, terrain 5.02 m AMSL against a 165.25 m origin).
GPS navigates, so flow is not fused into velocity and both builds fly the
same trajectory - only the scale height differs.

| | master | corrected |
|---|---|---|
| peak flow innovation | 31.833 rad/s | 0.148 rad/s |
| peak innovation consistency ratio (`XKF5.NI`, 100x, capped 255) | 255 | 3 |

255 is the logged ceiling, so the true ratio is at least 2.55: flow at that
geometry is rejected outright.

### Superseded 2026-09-10 by a review of the measurement itself

Two things above are wrong and are left in place because the numbers were
really taken and the errors are worth not repeating.

**The innovation figures are int16 aliasing artefacts.** `XKF5` logs
`flowInnov` as `(int16_t)(1000 * innov)`, so anything past +/-32.767 rad/s
wraps. The geometry described - about 10 m/s over a range clamped to
`rngOnGnd` = 0.1 m - predicts roughly 100 rad/s, and 97.369 aliases onto
+31.833. The consistency ratio is the robust statement and it is unaffected:
it saturates its own 255 cap. Do not quote the innovation from this path.

**The run was at 40 m and the window was the whole log.** Both were changed
after measuring the terrain properly, below.

**A correction to `../33585/`, which recorded that the forwarding's effect
"is on the flow scale height above the range, which no log field exposes".**
No field carries the scale height itself, but `XKF5.NI` carries the
consistency ratio it drives, and that discriminates 3 against 255. The
autotest below reads it.

## The terrain at KalaupapaCliffs is not a simple drop (2026-09-10)

Sampled through the vehicle's own `TERRAIN_REPORT` at 25 m spacing, which is
what the code reads, rather than from an offline tile reader:

| north (m) | 0 | 25 | 50 | 75 | 100 | 150 | 200 | 300 | 400 |
|---|---|---|---|---|---|---|---|---|---|
| terrain AMSL | 165.4 | 175.6 | **185.8** | 179.1 | 159.7 | 120.7 | 76.1 | 14.2 | 5.0 |

Home is 165.25 m. There is a ridge peaking at 185.8 m about 50 m north
before the ground falls away. A first pass sampled only 0 and 100 m, read
165.4 and 159.7, and concluded the profile fell monotonically - the sample
spacing aliased the ridge out. At the original 40 m test altitude the margin
over it is 19.5 m, which is thin and would put the range finder back in
range if it were any lower. The run is now at 60 m.

An independent review put the ridge at 202 m and home terrain at 184 m,
from an offline reader. Those magnitudes are about 16-20 m high against what
the flight code itself reports, but the shape was right and the concern was
real. Prefer the in-flight numbers; the offline reader disagrees with
AP_Terrain's own grid.

## The signal lives in the traverse, not the hover (2026-09-10)

The scale height reaches the innovation only through vehicle velocity:
`losPred = relVelSensor / range`. Over a stationary hold `relVelSensor` is
near zero, so the innovation is near zero whatever the range is. Measured
over a 15 s hold at the end of the leg, both the correct and the inverted
build read a ratio of 0. The original whole-log maximum only worked because
the traverse happened to be inside it.

## What this test cannot show (2026-09-10)

With `EK3_OPTIONS` cleared the SRTM branch is skipped and `terrainState -
pd` supplies the scale height. Frozen at the takeoff reading, that is about
60 m against a true 220 m - 3.7x low - and it measures a ratio of **3**,
well inside the gate.

| configuration | traverse peak ratio |
|---|---|
| sign inverted | 255 |
| bit 2 cleared, feature unused | 3 |
| bit 2 set, sign correct | 0 |

So the test discriminates the sign decisively and does **not** prove the
database rather than the terrain offset state supplied the height. A
suggested negative leg - assert the ratio saturates with the option cleared
- is refuted by that 3: it would fail. Recorded rather than papered over
with a leg that would pass for another reason, the same way `../33585/`
handled its uncoverable forwarding case.

## What did not change, and why

Both carried over from #33585's rounds five to seven; do not re-open them.

- **The collapse to `rngOnGnd` is pre-existing and is not closed.** The old
  expression could go negative too, over ground further below the origin
  than the vehicle is above it. The sign fix moves which geometry triggers
  it. A round-five guard that kept the terrain estimator's height where the
  corrected value came out low was **withdrawn in round six**: the premise
  was false, and it fell through to a `terrainState` the enclosing condition
  has already declared stale.
- **`terrain_srtm_alt_ms` reading fresh at zero** is real and is fixed in
  #33585, not here. `../34361/` guards its own use.

## Validation

- **SITL A/B**: above, trajectory-controlled.
- **Autotest**: `EK3_OptflowTerrainScaleHeight`. Flies the cliffs, waits for
  `EKF_POS_VERT_AGL` to go clear so the database and not the terrain offset
  state is supplying the height, checks tiles actually loaded, and asserts
  the consistency ratio stays under 50. Measured 3 fixed, 255 unfixed, so it
  fails on master. `N21W157.hgt.zip` is in `Tools/autotest/tilecache/srtm`,
  so it runs on CI.
- **Not Replay.** Replay re-runs the estimator on recorded data, and no
  real flight in the archive has terrain enabled over relief with the
  rangefinder out of range.

## What is here

```
34360/
  README.md    <- this file
```

Code on branch `ekf3-srtm-flow-scale-sign` (`98934eb97e` plus its autotest),
cherry-picked from #33585's `535cfca48f` with round seven's message and the
measurement added.

## Related

- `../33585/` - where the defect was found and first fixed, and the rounds
  that settled what not to change.
- `../34361/` - the same convention in `getHAGL()`, opened 2026-09-10.
  Touches the adjacent line, so it stacks on this rather than racing it.
