# EKF3: select the lane that runs the source set being asked for

**Not yet opened.** Rename this directory to the PR number when it is, and move
the row in the root README with it.

Ten commits on `andyp1per/pr-srcset-selects-lane`, which want squashing to four
before the PR is opened: `952292212e` (AP_NavEKF, a public accessor),
`d7d232da5a` + `b3141460e1` (AP_NavEKF3, the behaviour), `869228bb9c` (the
`EK3_PRIMARY` description), `98ec335615` (AP_AHRS), `b4afcc05e7` (RC_Channel),
`68660971d1` (GCS_MAVLink), `7486dc2840` + `48e5f44df7` (autotest),
`76627aedf4` (a comment trim). A master PR: `SRC_PER_CORE` and
`ManualLaneSwitch` are both upstream, confirmed by `git grep` against
`upstream/master`. Numbers below were taken at `48e5f44df7` unless another
commit is named.

## Summary

With `EK3_SRC_OPTIONS` bit 3 (`SRC_PER_CORE`), each core is pinned to the source
set with its own index - `AP_NavEKF_Source::getActiveSourceSet()` returns the
core index and never reads `active_source_set` for cores 0-2. Selecting a source
set therefore reached no core at all, while the RC switch, the Lua binding and
`MAV_CMD_SET_EKF_SOURCE_SET` all reported success and logged
`EK3_SOURCES_SET_TO_*`.

The request now selects the lane that runs that set, **for the operator-driven
callers only** - the RC switch and `MAV_CMD_SET_EKF_SOURCE_SET`. `EK3_PRIMARY` is
set rather than `switchLane()` called, so it goes through the path that already
exists. It is not saved, because a switch selects for this flight and should not
rewrite the boot lane.

Two claims this file made until 2026-09-21 were wrong and are corrected in
section 4: `EK3_PRIMARY` is **not** a preference the filter leans towards while
armed without `ManualLaneSwitch` - it is inert - and lane 0 is **not** the safe
direction for a set with no lane.

## Conclusion

Flown before and after on the same airframe with the same switch action. The
change is small, tested both ways, and has one objection to answer in the PR
description rather than in code.

## Key findings

### 1. The control lied, for four minutes (tier 1, SFD-O4 log11)

A flight flown to test the optical flow lane selected source set 2 three times
(and set 3 once) before arming, and then flew **four minutes entirely on GPS**.
Core 0 held `AID=0` and `PI=0` across all three selections and for all 2320
in-flight samples, with GPS at 26 satellites and HDop 0.55 throughout.

**`XKFS.SS` is the field that settles it** - it logs the source set each core
actually ran, and held 0 and 1 per core for all 3059 samples. Nothing else in the
log contradicted the statustexts.

### 2. After the change (tier 1, SFD-O4 log14, firmware `5adc2ea0`)

```
46.5055  Using EKF Source Set 2
46.5101  EKF3 lane switch 1        <- 4.6 ms later
46.5103  EKF primary changed:1
```

`XKF4.PI` is 1 for all 1240 in-flight samples. Core 1, the relative-aiding flow
lane, then flew the vehicle for 126 s in LOITER with core 0 on GPS alongside as
standby: no aiding stop, no flow velocity reset, no failsafe, `XKF4.SP` peak
0.06. `plots/srcset_lane_before_after.png` is log11 against log14.

It also confirms, in flight, that `EK3_PRIMARY` moves the lane while **armed**.
The parameter's own documentation describes it as a startup and disarmed
preference; the `ManualLaneSwitch` branch of `UpdateFilter()` sits before the
armed check.

### 3. What the flow lane did once it was flying (context, not a claim about this change)

Against GPS the lane held velocity to 0.26 m/s RMS at a 0.94 speed ratio. The
pilot flew out to 40.4 m and landed 1.3 m from the start. The relative position
estimate drifted 1.3 m at 30 s, 2.9 at 61, 5.1 at 91 and **11.4 m at 122 s**,
which is the roughly 6 % speed under-read integrated. That under-read agrees
three ways on this airframe (0.88 forward-axis from log9's flow calibration, 0.92
to 0.98 by height on log11, 0.94 on the lane that flew) and is a sensor
calibration matter, not this PR's.

#### Superseded 2026-09-21 by the log15 calibration

The under-read is now measured per axis on a flight flown for it - log15, 5644
usable samples, 3265 forward and 2352 strafe, range finder Good 99.5 %, mean
height 9.47 m with 4 % near the 15 m cap so no truncation bias:

| axis | flow/ideal | corr | cross-axis | was | fitted |
|---|---|---|---|---|---|
| X (sideways) | 0.97 | 0.99 | 1 % | `FLOW_FXSCALER` -88 | -60 |
| Y (forward) | 0.90 | 0.99 | 3 % | `FLOW_FYSCALER` -148 | -50 |

The sensor-rate check passes on both axes (+1.00 and +0.99, corr 0.99 and 0.98),
so the node's output rate and `FLOW_ORIENT_YAW` are right and no `FLOW_HF_RATEF`
correction is wanted; cross-axis at 1 % and 3 % against a 15 % threshold rules
out a rotated flow frame.

`flow/ideal` is ambiguous between flow scale and height, and both halves are
closed here. A height error scales **both** axes equally, so the seven-point gap
between X and Y can only be flow scale. And the height itself checks out
independently: `dRFND/dt` against GPS-Doppler climb rate gives slope 0.965,
intercept +0.01 m/s, corr 0.993 over 952 samples, with the residual consistent
with the 1 s differentiation baseline attenuating a changing climb rate.

The finding above is left in place because the three numbers in it are what made
the deficit credible before a flight was flown for it, and because the 0.94 it
records is the figure for **this** flight - log14 flew the old scalers. Any
re-measurement of the drift has to be on a flight flown with the fitted values,
which is a different measurement, not a correction of this one.

**Verified on log16**, flown with the fitted values. The flow lane's speed ratio
against GPS is **1.002** (n=493) where log14 on the old scalers read 0.935
(n=507): the systematic under-read is gone. Velocity error RMS reads 0.26 m/s on
log14 and 0.36 on log16, which is not a regression and not comparable - log16 was
flown faster and with more tilt (199 of 493 moving samples near level, against
381 of 446 on log15) - so the ratio is the calibration number and the RMS is not.

The helper reported X cross-axis at 20 % on log16 against 1 % on log15, which
reads as a rotated flow frame and is not one. Each sample is assigned to
whichever body axis its motion dominates, and log16 flew its middle six legs at
34 to 55 degrees off the nose, so those land in one axis' bucket while carrying
most of their motion on the other. Binning the off-axis flow by course relative
to the nose separates it: within 20 degrees of 0, 90 and 180 the leakage is 5-7 %
on **both** flights, and only the 25-65 degree buckets are high. An orientation
error also cannot appear between two sorties twenty minutes apart with nothing
touched. The helper's further suggestions from that fit, FXSCALER -40 and
FYSCALER -65, are chasing two points on a contaminated axis assignment and should
be ignored.

### 4. What the review changed (tier 1b, SITL A/B)

Three defects, two found independently by a cold Codex pass and a whole-diff
reviewer, one by the caller survey.

**A set with no lane moved the lane.** The warning did not `return`, so
`_primary_core` was left holding an index with no core, which `UpdateFilter()`
(`:965`) and `InitialiseFilterBootstrap()` (`:878`) both clamp to **0**. The
earlier claim that this "falls back to lane 0, which is the safe direction" was
reasoning, not measurement, and it was wrong: lane 0 is arbitrary, and reaching
it discards the lane the vehicle was on. Measured by removing the fix and
re-running `EK3_SourceSetSelectsLane`:

```
EKF3 lane switch 1             <- set 2 selected lane 1, correct
EKF3 source set 3 has no lane  <- the warning says nothing happened
EKF3 lane switch 0             <- the lane moved anyway
EK3_PRIMARY = 2                <- naming a core that does not exist
```

The fix returns before the write. The test asserts `EK3_PRIMARY` directly and
counts lane switches, and fails as above without it.

**Armed without `EK3_OPTIONS` bit 1 the selection is inert.** `_primary_core`
reaches `primary` by exactly two routes: the `ManualLaneSwitch` branch
(`:967-973`), which runs whatever the arm state, and the disarmed force (`:1028`,
gated on `!armed` and `core[user_primary].healthy()`). So the feature works on
the ground either way and in flight only with bit 1 - which is the case an RC
switch exists for. It now warns rather than reporting success, and the
`EK3_PRIMARY` description says so.

The motivating flight is unaffected: **SFD-O4 log14 flew `EK3_OPTIONS` = 62**,
which carries bit 1, with `EK3_IMU_MASK` 3, `EK3_PRIMARY` 0 and
`EK3_SRC_OPTIONS` 8. Checked rather than assumed, because the commit message's
causal story depends on it.

**Lua no longer moves the lane.** `ahrs:set_posvelyaw_source_set()` is used by the
shipped `ahrs-source-extnav-optflow.lua` applet and three examples to switch sets
*automatically on sensor health*. Under `SRC_PER_CORE` that would have become
automatic lane switching, handing position and yaw discontinuities to the
position controller, from a script that only asked for sources. The intent is now
a defaulted parameter taken from the caller, so RC and MAVLink select a lane and
Lua and Replay do not.

Replay taking the default is deliberate and costs nothing measurable: the DAL
event records the set, not the caller, so it cannot distinguish them, and
`frontend->primary` has no effect on filter maths - its only consumers are
`XKF4.PI` and the primary-only logging gates. Passing `true` there would instead
break `check_replay.py` on any pre-change log from a bit-3 vehicle, which
compares base core *N* to replay core *N*+100 and would raise `KeyError` on a
core the base never logged. The faithful alternative, new `AP_DAL::Event` values
that record the intent, is noted for a maintainer rather than taken here.

## The objection this PR has to meet

Source sets and cores are orthogonal concepts and should stay that way; the EKF3
playbook says so in as many words. This change ties them together.

The answer is that `SRC_PER_CORE` is the one configuration where the code has
already made them identical - core *i* is permanently set *i*+1 - so a request
naming a set has no other meaning available to it.

The alternative, **measured and rejected**: leave the behaviour alone and
document that the switch does nothing under this option. That keeps the concepts
clean and keeps a control that silently lies, which is what cost log11's sortie.

## Still owed

- ~~`EK3_PRIMARY`'s `@Description`~~ - done at `869228bb9c`, corrected at
  `b3141460e1` to say that the parameter selects the lane while armed **only**
  under `EK3_OPTIONS` bit 1. `param_parse.py` renders the new text; its one error
  is a pre-existing duplicate in an unrelated Lua driver.
- **Squash to four commits and reword `d7d232da5a`.** Its body still says
  "the documented preference without it" and calls lane 0 "the safe direction",
  both corrected above, and reads `XKFS.SS` as the tell when under `SRC_PER_CORE`
  that field is just the core index. Needs a grant covering history rewriting.
- Build across vehicles. AP_NavEKF3 is shared with Plane, Rover, Sub and Heli;
  only Copter has been built.

## Tests

`EK3_SourceSetSelectsLane` (`c718acdedb`) flies the `EK3_PerCoreLogging`
configuration - GPS on core 0, VICON on core 1, `ManualLaneSwitch` set - and
asserts the lane follows the set both ways and that a set with no core warns
rather than reporting success.

**It fails without the change**, on the first wait, never seeing a lane switch.
Verified by removing the hunk, rebuilding and re-running.

Nine source-set tests pass with it: the new one plus `EK3_PerCoreLogging`,
`EKF3SRCPerCore`, `EKFSource`, `EKFSourceSetFailsafe`,
`MAV_CMD_SET_EKF_SOURCE_SET`, `EK3_NoGPSLeakWhenNotSource`,
`ThrowDropSourceSwitch`, `ThrowAbortRestoresSourceSet`.

## Consequences for a `SRC_PER_CORE` vehicle, for the PR description

Derived from the source, not measured, except where a log is named:

- A core can only fall back to flow if **its own** set names flow for velocity:
  `readyToUseOptFlow()` tests `useVelXYSource(OPTFLOW, core_index)`. With SRC1
  GPS-only and SRC2 flow-only, no lane can make the AID_ABSOLUTE to AID_RELATIVE
  transition on GPS loss - core 0 goes AID_NONE instead. Reaching that transition
  needs one set holding `POSXY=GPS` **and** `VELXY=OPTFLOW`.
- Combined with `ManualLaneSwitch` there is no automatic escape either, so
  denying GPS with the `GPS_DISABLE` RC option leaves such a vehicle
  dead-reckoning on lane 0 rather than moving to a healthy flow lane.
- RC aux function 103 (`EKF_LANE_SWITCH`) is a no-op under `ManualLaneSwitch`:
  `checkLaneSwitch()` returns immediately.

## File map

| Path | What |
|---|---|
| `plots/srcset_lane_before_after.png` | log11 (before) against log14 (after) |
| `plots/make_plots.py` | regenerates it |

No `data/`: both inputs are real flights and this repo is public. The logs are
named above and resolved by `find_log.py`.

## Reproduce

```sh
export AP_LOG_ROOTS=<wherever SFD-O4 lives>
cd plots && ./make_plots.py
```

For the test:

```sh
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py test.Copter.EK3_SourceSetSelectsLane
```
