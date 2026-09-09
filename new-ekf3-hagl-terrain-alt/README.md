# NEW PR (not opened) - EKF3: serve the terrain-database AGL from getHAGL()

Prospective PR against master. Nothing implemented and no PR opened as of
2026-09-09.

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

Not written. Add the SRTM branch between the two that exist, mirroring
what `FuseOptFlow` already does:

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

## Alternative placement considered

Folding this into #33585, which is open, already touches the same
`writeTerrainData` forwarding and is mid-review with rmackay9 on the
option-bit semantics. Rejected: bit 2 is upstream and this stands alone
against master, and #33585's review is delicate enough without gaining an
unrelated behaviour change. Reconsider if it turns out `getHAGL()` cannot
be changed without touching the bit 5 path.

## What is here

```
new-ekf3-hagl-terrain-alt/
  README.md    <- this file
```

## Related

- `../new-groundeffect-touchdown-gate/` - the consumer that exposed it.
- `../32972/` finding 6 - the measured cost.
- `../33585/` - bit 5 and the flat-ground path this must not serve.
