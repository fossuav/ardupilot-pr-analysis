# PR #34361 - EKF3: serve the terrain-database AGL from getHAGL()

Analysis archive for [ArduPilot/ardupilot#34361](https://github.com/ArduPilot/ardupilot/pull/34361).
Branch `ekf3-hagl-terrain-alt` (andyp1per fork), two commits, head
`87ba449393`, base master `4891432f35`. Opened 2026-09-10. Stacked on
#34360, `../34360/`, which corrects the same convention in `FuseOptFlow`.

Target: master `371990d846` (2026-09-05). `EK3_OPTIONS` bit 2
(`OptflowMayUseTerrainAlt`) and the whole SRTM path are already upstream,
so this is a gap in merged code, not a branch feature.

## Status (one line)

`getHAGL()` returns false when the only valid AGL the filter holds is the
terrain-database one, which silently degrades every caller of
`AP_AHRS::get_hagl()`; one measured consequence (log7, not committed,
2026-09-09); fix is three lines and not written.

## The problem

`AP_NavEKF3_Outputs.cpp:330`:

```cpp
bool NavEKF3_core::getHAGL(float &HAGL) const
{
    if (option_is_enabled(Option::AglKfForOptflow) && aglKfValid) {
        HAGL = aglKfH;
        return healthy();
    }
    HAGL = terrainState - outputDataNew.position.z - posOffsetNED.z;
    return !hgtTimeout && gndOffsetValid && healthy();
}
```

There are three sources of a height above ground in EKF3 and this function
knows about two. `FuseOptFlow` already prefers the SRTM terrain altitude
over `terrainState` when the latter has timed out
(`AP_NavEKF3_OptFlowFusion.cpp:378-381`), which is the whole point of bit
2 - flow keeps a correct scale height above rangefinder range. `getHAGL()`
does not, so the same filter reports "no height above ground" while it is
actively using one.

Measured consequence, on an outdoor BF_X quad with `EK3_OPTIONS=62`,
`TERRAIN_ENABLE=1` and 30 m terrain spacing: the rangefinder was out of
range high for 101 s continuous, the AGL KF timed out five seconds in, and
`ahrs.get_hagl()` returned false for the rest of it. Terrain coverage was
never in doubt - `TERR.Status=2`, 504 tiles loaded, `Pending=0`, `TerrH`
steady - and flow navigation held throughout on exactly that data
(`horiz_pos_rel` set in 100% of armed samples while `terrain_alt` was set
in 53.6%).

The consumer that noticed was `AP_GroundEffect`, which falls back to a
takeoff-relative height when `get_hagl()` fails and from there to a
horizontal-drift rule that asserts ground proximity unconditionally. That
latched `touchdown_expected` for 51 s in a 17.9 m hover and cost 5.6 m of
altitude on a lane with no vertical velocity source. Full chain in
`../new-groundeffect-touchdown-gate/` and `../32972/` finding 6.

The ground-effect side needs fixing on its own merits. This is the
cheaper root fix: with it, that flight takes the `height_is_agl` branch
and never reaches the drift fallback at all.

## The proposed change

Written 2026-09-09, see "Implemented" below. The shape proposed was:

```cpp
#if EK3_FEATURE_OPTFLOW_SRTM
    if (!gndOffsetValid && terrain_srtm_alt_valid) {
        HAGL = terrain_srtm_alt - outputDataNew.position.z - posOffsetNED.z;
        return !hgtTimeout && healthy();
    }
#endif
```

Two things to get right, both *derived from the source, not measured*:

- **Order.** The AGL KF and `terrainState` are measurements of the ground
  actually under the vehicle; the terrain database is a 30 m-posted model.
  The database is the fallback, never the preference, so it goes after
  `aglKfValid` and after `gndOffsetValid`, matching `FuseOptFlow`.
- **Do not serve the flat-ground assumption.** On branches carrying
  `EK3_OPTIONS` bit 5 (`OptflowAssumeFlatGnd`, #33585) there is a fourth
  path, and it is an assumption rather than a measurement. `getHAGL()`
  callers are entitled to a real height - `AP_GroundEffect` would use it
  to decide the vehicle is near the ground - so bit 5 must not reach here.
  Master does not have bit 5, so this only matters when the change is
  carried onto the SmallFastDrone branch.

`terrain_srtm_alt_valid` is refreshed inside `FuseOptFlow`, so on a
vehicle without optical flow it is never true and the change is a no-op.
That bounds the blast radius but is also a wart worth noting in review:
the validity of a terrain-database altitude has nothing to do with
optical flow.

## Validation

- **Not Replay, despite appearances.** `getHAGL()` has no consumer inside
  the EKF; every caller is vehicle code, which Replay does not run. Its
  inputs do come through the DAL (`RTER` carries the terrain altitude), so
  a Replay of the 2026-09-09 flight would compute the corrected value
  internally, but nothing in the replayed output reports it. Only an
  instrumented Replay build would show it, which is a debugging aid rather
  than evidence. Use SITL.
- **SITL A/B**: flow vehicle above rangefinder range with terrain data
  served, `EK3_OPTIONS` bit 2 set. Before: `get_hagl()` false. After:
  true, and the returned height tracks the terrain model. `../33585/`
  records that a test of this area failed once for serving no terrain
  data at all, so check the harness actually delivers tiles before
  believing a green run.
- **Autotest**: assert on the height, not on a downstream flag, and
  demonstrate it failing on unfixed code.

## Implemented 2026-09-09

`SmallFastDrone-4.7.1-beta` commit `b003fc6c4d`, on base `fd37f6f5fa`.
Both "things to get right" above hold: the branch sits after the AGL KF
and behind `!gndOffsetValid`, and it never consults `flatGroundAssumed()`
- confirmed by reading `flatGndAssumed`, which is a local in
`AP_NavEKF3_Control.cpp:856` and writes nothing that reaches here.

**One deviation from the proposed code, and it is the wart this file
already named.** The branch does not test `terrain_srtm_alt_valid`. That
flag is assigned only inside `FuseOptFlow`, which `SelectFlowFusion` calls
only when `flowDataToFuse && tiltOK`, so it freezes at its last value
whenever the flow tilt gate closes and is never set at all without a flow
sensor. `getHAGL()` has no flow-active gate of its own, unlike its sibling
`getHeightControlLimit()` which reads the same flag but only inside a
`useVelXYSource(OPTFLOW) && AID_RELATIVE && flowDataValid` guard. The
branch therefore ages the data against `terrain_srtm_alt_ms`, which
`writeTerrainData()` maintains independently of flow, using a named
`TERRAIN_SRTM_ALT_TIMEOUT_MS` (5000) that replaced the bare literal at the
`FuseOptFlow` site rather than adding a second one.

The blast radius is still bounded, but by a better thing. `terrain_srtm_alt`
only reaches the cores when `EK3_OPTIONS` bit 2 or bit 5 is set
(`AP_NavEKF3.cpp:1832`), so without either the timestamp stays 0, the
freshness test fails and the branch is a no-op. It is now opt-in on the
option bits rather than on whether flow happens to be fusing at that
instant. *Derived from the source, not measured.*

### SITL result

`EK3_GetHaglTerrainAlt` in `Tools/autotest/arducopter.py`. Flow vehicle,
`EK3_IMU_MASK=1`, `RNGFND1_MAX=8`, `TERRAIN_ENABLE=1`,
`EK3_OPTIONS = 1<<2` only - deliberately *not* the AGL KF bit, so the
terrain branch is what is under test rather than `aglKfValid`. It asserts
on `OPTICAL_FLOW.ground_distance`, which is `get_hagl()` passed straight
through at `GCS_Common.cpp:2948` and sent as zero when it returns false,
so this is the height itself and not a downstream flag.

Heeding `../33585/`: the test waits for `TERRAIN_REPORT` to show
`loaded > 0` and `pending == 0` before asserting anything, so a harness
that served no tiles fails as "terrain tiles were never delivered" rather
than as a wrong EKF answer.

Measured 2026-09-09, hovering above the rangefinder range:

| | `OPTICAL_FLOW.ground_distance` | relative altitude |
|---|---|---|
| base `fd37f6f5fa` | 0.000 m | 21.099 m |
| with `b003fc6c4d` | 20.698 m | 21.187 m |

Fails on the base commit with "getHAGL served no height above the
rangefinder range".

## Alternative placement considered

Folding this into #33585, which is open, already touches the same
`writeTerrainData` forwarding and is mid-review with rmackay9 on the
option-bit semantics. Rejected: bit 2 is upstream and this stands alone
against master, and #33585's review is delicate enough without gaining an
unrelated behaviour change. Reconsider if it turns out `getHAGL()` cannot
be changed without touching the bit 5 path.

## What is here

```
34361/
  README.md    <- this file
```

Written on `SmallFastDrone-4.7.1-beta` (`b003fc6c4d`) and ported to master
as `ekf3-hagl-terrain-alt` for the PR.

### The test moved to 60 m after the terrain was measured (2026-09-10)

The SITL numbers above were taken at 40 m above home. Sampling the terrain
at 25 m spacing afterwards found a ridge peaking at 185.8 m AMSL about 50 m
north of a 165.25 m home, so that leg had 19.5 m of margin over it rather
than the tens of metres assumed - a first sampling at 0 and 100 m had
aliased the ridge out entirely. The test now flies at 60 m, where the margin
is about 40 m and the range finder cannot come back into range mid-leg.
Re-run there, getHAGL reads 59.98, 149.10 and 220.33 m against a database
truth of 59.98, 149.09 and 220.32 m, and still reads 0.00 on unfixed code.
The 40 m numbers stand as taken; they are a different run, not a correction.

See `../34360/` for the full profile, and for why an offline tile reader
disagreed with what AP_Terrain itself reports.

## Related

- `../new-groundeffect-touchdown-gate/` - the consumer that exposed it.
- `../32972/` finding 6 - the measured cost.
- `../33585/` - bit 5 and the flat-ground path this must not serve.
- `../34360/` - the same convention in `FuseOptFlow`, opened 2026-09-10.
  This touches the adjacent line, so it stacks on that rather than racing it.
