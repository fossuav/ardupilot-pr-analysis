# EKF3: select the lane that runs the source set being asked for

**Not yet opened.** Rename this directory to the PR number when it is, and move
the row in the root README with it.

Three commits on `SmallFastDrone-4.7.1-beta`, to be lifted onto master:
`3294e6418a` (AP_NavEKF, a public accessor), `2cee4deebb` (AP_NavEKF3, the
behaviour), `c718acdedb` (autotest). A master PR: `SRC_PER_CORE` came in with
`f172c2fd03`, which the SFD base carries as merged upstream. Numbers below were
taken at `c718acdedb`.

## Summary

With `EK3_SRC_OPTIONS` bit 3 (`SRC_PER_CORE`), each core is pinned to the source
set with its own index - `AP_NavEKF_Source::getActiveSourceSet()` returns the
core index and never reads `active_source_set` for cores 0-2. Selecting a source
set therefore reached no core at all, while the RC switch, the Lua binding and
`MAV_CMD_SET_EKF_SOURCE_SET` all reported success and logged
`EK3_SOURCES_SET_TO_*`.

The request now selects the lane that runs that set. `EK3_PRIMARY` is set rather
than `switchLane()` called, so it goes through the path that already exists:
immediate under `ManualLaneSwitch`, and the documented preference without it. It
is not saved, because a switch selects for this flight and should not rewrite the
boot lane. `UpdateFilter()` falls back to lane 0 when `EK3_PRIMARY` has no core,
which is the safe direction but reads exactly like the set having been taken up,
so a set with no lane warns.

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

- **`EK3_PRIMARY`'s `@Description`.** It says the parameter applies on startup
  and while disarmed. Finding 2 shows it moving the lane in flight, which is
  pre-existing behaviour this PR now exposes through a switch. Update the text
  and re-run the parameter metadata check.
- Build across vehicles. AP_NavEKF3 is shared with Plane, Rover, Sub and Heli;
  only Copter has been built at `c718acdedb`.

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
