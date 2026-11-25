# PR #34305 - uninitialised flow data read in the EKF3 terrain estimator

Analysis archive for [ArduPilot/ardupilot#34305](https://github.com/ArduPilot/ardupilot/pull/34305).
Branch `pr-ekf3-terrain-flow-gate` (andyp1per fork), base `master`, head
`fb25853f82` (2026-09-05). One commit, +8/-4.

Found while fixing a SIGFPE that #34292 had introduced two lines away. That
one was ours; this one is master's, and predates it.

## The bug

`ekf_ring_buffer::recall()` (`AP_NavEKF/EKF_Buffer.cpp:53`) only memcpys into
the caller's element `if (ret)`. On failure the caller's `of_elements` is left
untouched.

`NavEKF3_core::SelectFlowFusion()` declares `of_elements ofDataDelayed;` on the
stack, uninitialised, and calls `EstimateTerrainOffset(ofDataDelayed)` when
**either** flow **or** rangefinder data is available:

```cpp
if (((flowDataToFuse && (frontend->_flowUse == FLOW_USE_TERRAIN)) || rangeDataToFuse) && tiltOK) {
    EstimateTerrainOffset(ofDataDelayed);
}
```

Inside, `cantFuseFlowData` reaches
`MAX(ofDataDelayed.flowRadXY[0], flowRadXY[1]) > _maxFlowRate` with nothing
having established that a flow sample exists.

### Superseded 2026-11-24 by the dev-call review and a SITL A/B

The read is not uninitialised. `of_elements` holds its rates in `Vector2F`
and `Vector3F`, whose default constructors zero them (`AP_Math/vector2.h:50`),
so a failed recall leaves `flowRadXY` and `flowRadXYcomp` at zero. Master's
defect is deterministic: `cantFuseFlowData` comes out false on a plain
GPS-aided Plane above 5 m/s, and the estimator tests, and where the gate
passes fuses, a zero flow it never measured, with an innovation equal to the
whole predicted line-of-sight rate. The fix is unchanged; only its
explanation was wrong. The text above is left because the reachability
argument below it still holds.

## Reachability: it does not need a flow sensor

This is the part that is easy to get wrong, and I did get it wrong first time.
The read needs only a **rangefinder**:

- `EstimateTerrainOffset()` is entered on `rangeDataToFuse` alone.
- `EK3_FLOW_USE` defaults to **2** (`FLOW_USE_TERRAIN`) on Plane
  (`AP_NavEKF3.cpp`, the `APM_BUILD_ArduPlane` block), so the existing first
  disjunct does not short circuit. Copter, Rover, Sub and Heli default to 1 and
  escape entirely.
- `gpsIsInUse`, `PV_AidingMode != AID_RELATIVE` and `velHorizSq >= 25` are all
  satisfied by an ordinary GPS-aided plane above 5 m/s.

With no flow sensor fitted, `storedOF.recall()` never succeeds at all, so
`ofDataDelayed` is pure uninitialised stack on every call. A plane with a
rangefinder is exposed whenever the rangefinder is in range and the aircraft is
above 5 m/s: most of every takeoff and landing.

Note the pre-takeoff block above the call zeroes `flowRadXY`/`flowRadXYcomp`,
but only while `!takeOffDetected` and below 0.5 m, so it does not cover flight.

## Evidence

Tier 2, SITL. Whether an uninitialised read faults depends on the stack, so the
demonstration poisons the struct to remove that dependence:

```c
    of_elements ofDataDelayed;
    memset(&ofDataDelayed, 0xFF, sizeof(ofDataDelayed)); // 0xFFFFFFFF is a NaN
```

`Tools/autotest/autotest.py test.Plane.RangeFinder`, same build, one variable:

| `!flowDataToFuse` term | result |
|---|---|
| absent (master) | SITL dies. `_sig_fpe(int)` -> `EstimateTerrainOffset(of_elements const&, bool)` -> `SelectFlowFusion()` -> `UpdateFilter(bool)` |
| present (this PR) | passes |

Without the poison, `Plane.RangeFinder` and `Copter.OpticalFlowLimits` both
pass on the branch at `fb25853f82`.

SITL enables `FE_INVALID | FE_OVERFLOW | FE_DIVBYZERO`
(`AP_HAL_SITL/Scheduler.cpp:199-206`) and `>` is a signalling comparison, which
is why a NaN there is a crash rather than a wrong answer. **On hardware there
is no trap**, so the consequence is instead a fabricated flow rate fused into
the terrain estimate, or a spurious rejection of a good rangefinder update,
depending on what was on the stack. No flight log has been checked for
symptoms of that.

### Superseded 2026-11-24 by a SITL A/B

The `memset(0xFF)` demonstration shows what garbage would do, not what master
does: it overwrites the zeros the constructors had just written. Master's
actual behaviour, measured in `Plane.TerrainEstimatorWithoutFlowSensor`
(the RangeFinder test's 10 m mission and AUTO landing, no flow sensor):
557 of 661 XKF5 rows carry a terrain flow innovation (AFI wraps negative on
the ground roll, about 59 rad/s), and through the final approach the terrain
height reads up to 2.8 m above the measured range (38 rows more than 0.5 m
over). With the fix: 0 of 661, 0 rows, worst 0.08 m.

## Measured and rejected

| Change | Argument for | Why rejected |
|---|---|---|
| `of_elements ofDataDelayed {};` | Smallest possible diff, fixes the read wherever it happens, and the root playbook says stack locals need explicit init | Silences the fault and replaces it with a silent wrong measurement. `MAX(0,0) > _maxFlowRate` is false, so `cantFuseFlowData` comes out **false** where garbage would usually have made it true, and `EstimateTerrainOffset` then fuses an invented zero flow rate every time a rangefinder sample arrives without a flow one. Tried first on #34292's branch and reverted before it was pushed a second time. |

## The fix

Add `!flowDataToFuse` as the **first** term of the `||` chain, so it short
circuits before `flowRadXY` is touched, and pass `flowDataToFuse` into
`EstimateTerrainOffset()`.

No behaviour change when a flow sample exists: the added term is false and the
rest of the expression evaluates exactly as before. When there is no sample,
the only paths affected are ones that were reading indeterminate values.

`inhibitGndState` is unaffected either way. The guard is
`(!rangeDataToFuse && cantFuseFlowData) || activeHgtSource == RANGEFINDER`; in
the `rangeDataToFuse` case `!rangeDataToFuse` is false, and in the other case
we only got here because `flowDataToFuse` was true. So rangefinder fusion into
the terrain state still happens exactly as before.

## Relationship to #34292

Independent, and this one is not stacked on it. #34292 added a *second*
unconditional read of the same struct two lines earlier
(`ofDataDelayed.minHeight > 0.0f`) and crashed Copter the same way, because
its check ran before any `flowDataToFuse` gate. That was fixed on its own
branch by `ac2989470e`; see `../34292/README.md` under "The SIGFPE this PR
introduced, and the fix that was wrong".

The two share a lesson worth keeping: anything reading `ofDataDelayed`,
`rangeDataDelayed` and friends outside the matching `if (xDataToFuse)` block is
reading whatever `recall()` last left there.

## Reproduce

```
git checkout pr-ekf3-terrain-flow-gate
./waf configure --board sitl && ./waf plane
Tools/autotest/autotest.py test.Plane.RangeFinder
```

For the failing arm, drop the `!flowDataToFuse ||` term from `cantFuseFlowData`
in `AP_NavEKF3_OptFlowFusion.cpp` and add the `memset` line after the
`of_elements ofDataDelayed;` declaration, then rebuild and run the same test.
The stack trace appears in `dumpstack.sh_arduplane.<pid>.out` in the repo root.

## Open

- No autotest. Without the poison, whether the read faults is up to the stack,
  so a committed test would pass on broken code. Stated in the PR description
  rather than left for a reviewer to ask.
- Not reviewed by `/pr-review` before opening.
- No hardware or flight-log evidence that the silent (non-SITL) consequence has
  ever bitten anyone.

## 2026-11-24: mechanism corrected, test added, rebuilt on master

Prompted by the dev-call review of 2026-09-06 (head `fb25853f82`) and
rmackay9's inline comment of the same day asking for the comment to be one
line. Branch `sq/34305-1124f`, pushed 2026-11-24 with the description and a reply: `0f54502ee7` (the fix,
reworded, comment now rmackay9's "don't fuse flow data unless available")
and `babeeb2c04` (the test, with `EK3_FLOW_USE` pinned at 2 after a second cold read), on master `68b1a73ef2`.

- `Plane.TerrainEstimatorWithoutFlowSensor` asserts XKF5.AFI stays zero
  while XKF5.RI, written only by the estimator's range branch, shows it
  running (about 240 rows). Fails on master 3 of 3, passes 5 of 5. The
  first version counted rows with `rng > 0`, which a cold review rightly
  said would pass with the estimator not running at all.
- The bug has been there since 4.1.0: `15658362b5` made the buffer element a
  local.
- EKF2 has the same gap (`AP_NavEKF2_OptFlowFusion.cpp:78`), with the last
  sample rather than zeros once a flow sensor has been seen, as there
  `ofDataDelayed` is a member. Not changed; EKF2 is compiled out by default.

The Open items above about the missing autotest and the missing
`/pr-review` are closed by this round (quick review, Codex cold read and
audit: all five raised points closed).
