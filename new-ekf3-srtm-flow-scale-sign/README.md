# NEW PR (not opened) - EKF3: fix the sign of the SRTM height used for flow scaling

Prospective PR against master, extracted from #33585. Branch
`ekf3-srtm-flow-scale-sign`, two commits, base master `4891432f35`
(2026-09-10). Written and measured 2026-09-10, not yet opened.

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
- `../new-ekf3-hagl-terrain-alt/` reached the same expression independently
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

**A correction to `../33585/`, which recorded that the forwarding's effect
"is on the flow scale height above the range, which no log field exposes".**
No field carries the scale height itself, but `XKF5.NI` carries the
consistency ratio it drives, and that discriminates 3 against 255. The
autotest below reads it.

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
  #33585, not here. `../new-ekf3-hagl-terrain-alt/` guards its own use.

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
new-ekf3-srtm-flow-scale-sign/
  README.md    <- this file
```

Code on branch `ekf3-srtm-flow-scale-sign` (`98934eb97e` plus its autotest),
cherry-picked from #33585's `535cfca48f` with round seven's message and the
measurement added.

## Related

- `../33585/` - where the defect was found and first fixed, and the rounds
  that settled what not to change.
- `../new-ekf3-hagl-terrain-alt/` - the same convention in `getHAGL()`.
  Touches the adjacent line, so it stacks on this rather than racing it.
