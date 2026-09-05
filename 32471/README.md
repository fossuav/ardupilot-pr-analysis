# PR #32471 - hover Z-bias learning for vibration rectification (EKF3 / Copter)

Analysis archive for [ArduPilot/ardupilot#32471](https://github.com/ArduPilot/ardupilot/pull/32471).
Branch `pr-vrf-core` (andyp1per fork), base `master`, approved. Real-flight
numbers inline; no real-flight logs committed. SITL A/B logs and plots added
2026-09-04. Partial: the fleet-wide VRFB history (the frozen-correction /
ground-effect conflict) is not yet here.

> **Read this before changing the code.** Three changes that look obviously right
> from reading the source alone have been measured here and are worse. They are
> listed under "Measured and rejected" below. A 2026-09-04 review pass reasoned
> its way into two of them from the code and had to be reverted; the PR body now
> carries the same list so a reviewer meets it without finding this file.

## Status (one line)

Approved. This records how the vibration rectification bias was measured
independently on two airframes, the one way the learning was seen to go wrong
(a drifting height reference during the learning hover), and - since
2026-09-04 - the first SITL measurement of what the feature is actually worth,
which needed two new simulator capabilities to exist at all.

## The problem

Vibration rectifies into a DC offset on AccZ when motors run. Without a
vertical velocity source (indoor, no GPS) the EKF integrates it into
altitude drift. No stationary calibration can see it: AP_TempCalibration
learns only with !armed && is_still. The PR learns the bias in stable hover
and applies it as a frozen correction from the next boot (`INS_ACC_VRFB_Z`).

## Key findings

### Measuring the bias independently

Indoor 5-inch quad, log197 (not committed): raw IMU AccZ with motors at idle
(VibeZ ~0.2 m/s^2) against a 50 s hover (VibeZ ~3.2), regressed on IMU
temperature to separate the constant term from thermal drift: VRF
+0.089 m/s^2, thermal coefficient -0.045 m/s^2/C, R^2 0.82. An 18 s hover
(log198) gave +0.048. Positive VRF makes AccZ less negative, the EKF reads
it as downward acceleration, and altitude drifts down. Best estimate +0.09,
a useful pre-load for `INS_ACC_VRFB_Z` and a check on what the learning
converges to.

A 5-inch baro-only indoor quad (not committed): near-level quiet hover
against motors-off at matched temperature (33.3 vs 32.1 C), AccZ -9.8298 vs
-9.9190, a +0.089 m/s^2 shift. Same number on a different airframe.

### The learning is only as good as its height reference

On log198 the learned value converged to -0.066, the wrong sign. The DPS310
cooled 8.5 C in 54 s of hover from prop airflow, drifting the baro
~0.015 m/s (~0.6 m), and an upside-down thermal calibration was adding
+0.359 m/s^2 on top of the +0.089 real bias; the EKF absorbed 69% of the
total into its Z bias (-0.510 -> -0.201). The learner is not gated on the
barometer being trustworthy: it samples in a hover where the EKF Z bias
absorbs whatever the vertical channel cannot explain. On the baro-only quad
the `TCAL_BARO_EXP` correction alone moved the baro +0.41 to +0.66 m per
flight as the board prop-cooled (a ramp, the shape a bias state tracks
worst), so a VRFB learned there freezes a thermal artefact into every later
flight (mechanism only; that vehicle had learning off). Learn only against a
reference that does not drift over the learning window - a rangefinder, or
a baro with the thermal error removed - and zero the stored value after any
change to the IMU calibration so it re-learns. The order applied in the
field was baro TCAL off first, then re-learn.

### INS_ACC_VRFB_Z stores the total hover Z bias, not the on/off difference

`Attitude.cpp` writes totalBias = currentBiasZ + frozenCorrection, in the
EKF's sign convention. On the baro-only quad the stored value was -0.083
with a measured hover total of -0.023, and `XKF2.AZ` sat at +0.04 to +0.05
in flight making up the difference. The pair lands about right; neither
number is the rectification offset on its own. The parameter description
("bias learned during hover to compensate for vibration rectification")
will be read as the difference. Say "total".

### Range against clamp (fixed 2026-09-04)

The parameter range was +/-0.5, the EKF clamp `MAX_HOVER_BIAS_CORRECTION` 0.6,
and a true value of ~0.57 was measured on one airframe (the reason the clamp
was raised from 0.3). A fourth number, +/-0.3, survived in the `AP_NavEKF3.h`
comment from before that change. Now one named constant `HOVER_Z_BIAS_LIM` at
0.6, with `@Range` and the comment agreeing. The description gap above
("say total") is fixed in the same pass.

## Measured in SITL, 2026-09-04

Neither half of this could be simulated before. `SIM_ACCn_BIAS` is present at
rest, so it is the one case where the correction can only double-count; the
motor vibration in `SIM_VIB_MOT_MAX` is a zero-mean sinusoid and nothing in the
SITL accel path clips it, so no rectification comes out of it either. The PR's
own autotest used `SIM_ACC1_BIAS_Z` and passed with the correction entirely
absent. Two additions fix that:

- `SIM_ACC_VRF` - a motors-on-only accel offset. With `SIM_ACC_VRF_Z = 0.15`,
  IMU0 `AccZ` reads -9.8174 disarmed and -9.6686 in hover, a +0.149 m/s^2 shift
  the EKF then learns as `XKF2.AZ` +0.114.
- `SIM_PLAT_ACC` - the acceleration felt by a vehicle resting on a moving
  platform, applied while on the ground only. It has to go in the sensor model,
  not the physics: `Aircraft::smooth_sensors()` drives reported acceleration
  towards what the vehicle's own trajectory implies and cancels an offset
  injected into `accel_body` within its 0.1 s time constant.

### The feature is worth about 3x, against the mechanism it is named for

![height error](plots/ab_vrf_height_error.png)

![worst error](plots/ab_summary_worst_error.png)

Worst |EKF height - truth| over the 35 s after arming, 10 m climb, correct
value preloaded. Two runs each where shown:

| `ACC_ZBIAS_LEARN` | height error | `XKF2.AZ` range |
|---|---|---|
| 0 (off) | 0.609 / 0.612 m | 0.10 |
| 2 (use) | **0.196 / 0.195 m** | 0.01 |
| 3 (learn+use) | 0.193 m | 0.00 |
| 6 (use+inhibit) | 0.713 / 0.476 m | 0.46 |
| 7 (all bits) | 0.711 / 0.476 m | 0.47 |

(Measured 2026-09-04 on code that still carried the ground-effect Z-bias
inhibit. Re-measured without it 2026-09-05, below.)

`=2` and `=3` are indistinguishable, so the 0.196 m is the price of *applying*
the correction, not of learning it. `=6` and `=7` are also indistinguishable,
so the extra 0.5 m is bit 2 alone - learning first and then pinning does not
avoid it.

Measured against a static bias instead the same feature *costs* 0.64 m against
0.036 m with it off. Both numbers are real and they measure different
mechanisms; a test that injects a static bias measures only the harm.

### Bit 2 is about moving platforms, not the motors-off bias

![platform accel bias](plots/ab_platform_accel_bias.png)

`updateMovementCheck()` compares `|accel| - GRAVITY_MSS` against `accel_limit`
1.0 - a **magnitude**, so direction is invisible - and the rate-of-change terms
are zero for a steady acceleration. With `SIM_PLAT_ACC_Z = -1.0` and 60 s
disarmed, `onGroundNotMoving` stayed true for 100% of the period:

| | `XKF2.AZ` at arm | height error | climb (10 m demanded) |
|---|---|---|---|
| bit 2 clear | **-0.9900** | 4.479 m | 10.44 |
| bit 2 set | +0.0000 | 1.632 m | 9.67 |

-0.99 m/s^2 of invented bias, 10% of g, carried into a flight where the
platform is gone.

Upstream already intends to cover this - `AP_NavEKF3_core.cpp:1187`
(`is_bias_observable`, "on ground and moving (e.g. carried or on a boat)")
is untouched by this PR and fires correctly once the movement check can see
the acceleration: at `EK3_OGNM_TEST_SF = 0.5` the platform run learns +0.0000
with bit 2 clear.

But the threshold cannot be tuned to do both. From `logm2_log4` (real flight,
not committed), 514 pre-arm XKFM samples, counting those able to latch
`onGroundNotMoving`: 0/514 at SF 0.5, 0/514 at 1.0, 11/514 at 1.25, 14/514 at
the default 2.0. Detecting 1 m/s^2 needs SF < 1.0. The binding term is not the
accelerometer (`ALR` peaked at 0.012) but `GDR`, the gyro rate-of-change metric
- median 0.777, p90 1.055, max 1.398. And a threshold too low to latch switches
off the synthetic zero-velocity fusion entirely, which is what learns the gyro
bias before flight, where bit 2 gates only states 13-15. **Bit 2 is the
surgical instrument; `OGNM_TEST_SF` is the blunt one.** Its description now
says so.

### Measured and rejected

Three changes a code-only reading suggests, each measured worse. Do not
reintroduce any of them without redoing the A/B in `data/ab-2026-09-04/`.

| Change | Argument for it | Measured |
|---|---|---|
| Route the four covariance gates off `accelBiasLearningInhibited()` onto `inhibitDelVelBiasStates` (`cb5026417f`) | `ConstrainVariances` zeroes the accel-bias cross-covariances that `Kfusion` reads, so learning cannot restart after the inhibit clears | `=6` **0.713/0.476 m** with it, **0.448 m** without; `XKF2.AZ` range 0.46 vs 0.01 |
| Freeze P during the inhibit instead (withhold only the process noise) | avoids both the collapse and the inflation | **0.905/0.882 m**, oscillation intact - worse than either |
| Inhibit Z accel-bias learning in ground effect | the AccZ offset there is not the hover value, and a downwash-corrupted baro drives the bias wrong | at `=2`, present vs removed: **0.203 / 0.201 m** with no simulated ground effect, **0.169 / 0.168 m** with `SIM_BARO_GEFF_M=1.0`. Removed 2026-09-05 |
| Store the motors-on delta in `INS_ACC_VRFB_Z` instead of the total | the static bias is otherwise applied twice at arm | the stored value is a total across the whole fleet; changing it silently reinterprets every one. The arm-time double count is real and belongs to bit 2: `XKF2.AZ` at arm +0.130 clear vs 0.000 set |

`logjk4`'s proposal to gate the frozen correction on ground effect is also
measured worse - 0.644/0.656 m becomes 0.760 m - and targets the
never-leaves-ground-effect regime, a different case. Lowering
`EK3_OGNM_TEST_SF` instead of using bit 2 does not work either: 0/514 pre-arm
samples can latch below SF 1.25, and the binding term is `GDR` (median 0.777,
p90 1.055) not the accelerometer (`ALR` peak 0.012).

**`cb5026417f` still exists on `pr-acro-bias-inhibit` (#32473)** as
`361da5d064`, with a commit message that argues the collapse mechanism
convincingly. If #32473 merges after this PR the measured-worse behaviour
returns. See `../32473/README.md`.

#### The detail on cb5026417f

It routed four `CovariancePrediction` gates off `accelBiasLearningInhibited()`
so the accel-bias covariance stays alive while bit 2 holds the inhibit. Written
against the SITL subtest; no hardware evidence for the collapse it fixes. The
cost is that P[15][15] inflates across the whole disarmed period and the state
is released at arm into the takeoff transient: `=6` goes 0.713/0.476 m with it
to **0.448 m** reverted, and the `XKF2.AZ` range 0.46 -> 0.01. `=2` is
unchanged at 0.196 either way, confirming the revert is a no-op whenever the
vehicle flag is clear. Withholding only the process noise (freezing P rather
than letting it collapse) is worse still at 0.905/0.882 m with the oscillation
intact, so the instability is in the zeroing and reset gates.

Second arm, 2026-09-04: applying the change also fails the shipped
`AccelBiasMovingPlatform` autotest at 3.9 m against its 2.5 m gate, where the
branch as shipped passes at 1.632 m. The VRF and platform arms agree, and a
plain `test.Copter.AccelBiasMovingPlatform` run catches it without the harness.

### Bit 2's cost, mostly recovered (2026-09-05, shipped as `9b852c9464`)

Bit 2 costs 0.467 m against `=2`'s 0.201 m even with `cb5026417f` gone (0.448
against 0.196 as first measured). It protects the arm-time state and degrades
the correction it is protecting.

The mechanism, from tridge's 2026-09-05 review and confirmed against the
source: while the vehicle inhibit is held, the block at
`AP_NavEKF3_core.cpp:1189-1208` that saves and restores `dvelBiasAxisVarPrev`
sits inside `if (!accelBiasLearningInhibited())` and is skipped entirely, while
`ConstrainVariances` floors P[13..15] at `minSafeStateVar*10`. On release only
`dvelBiasAxisInhibit[index]` gates the restore, and for Z on the ground, level
and not moving, `is_bias_observable` is true, so that flag was never set and no
restore fires. X and Y do recover. Process noise alone would take hours.

His fix is distinct from both rejected alternatives: a bounded one-shot
re-initialisation on the falling edge of the frontend inhibit, using the values
`AP_NavEKF3_Control.cpp:166-170` already uses when the states are first
activated.

```cpp
const bool vehicleInhibit = frontend->getInhibitAccelBiasLearning();
if (prevVehicleInhibitAccelBias && !vehicleInhibit && !inhibitDelVelBiasStates) {
    P[13][13] = sq(ACCEL_BIAS_LIM_SCALER * frontend->_accBiasLim * dtEkfAvg);
    P[14][14] = P[13][13];
    P[15][15] = P[13][13];
}
prevVehicleInhibitAccelBias = vehicleInhibit;
```

Measured with the harness on `d951df4f82` plus that change. Three runs per side
on the arm that matters, so the separation can be read against the noise:

| arm | shipped | with the re-init |
|---|---|---|
| `=6` VRF | 0.467 / 0.473 / 0.472 m | **0.285 / 0.284 / 0.284 m** |
| `=7` VRF | 0.471 m | 0.285 m |
| `=2` VRF | 0.201 m | 0.203 / 0.208 m |
| platform bit 2 clear, `XKF2.AZ` at arm | -0.9900 | -0.9900 |
| platform bit 2 set, `XKF2.AZ` at arm | +0.0000 | +0.0000 |
| platform bit 2 set, height error | 0.176 / 0.176 m | 0.164 / 0.176 m |

The `=6` separation is 0.187 m against a within-arm spread of 0.006 m, about
thirty times the run-to-run noise. `=2` overlaps its own spread across the day
(0.199 to 0.208), which is what a no-op looks like: with bit 2 clear the
inhibit never engages, so the falling edge never fires.

It recovers 0.182 m of the 0.266 m penalty, is a no-op when bit 2 is clear, and
leaves the platform protection - the entire point of bit 2 - bit-identical.

**It converges rather than oscillating, which is what separates it from
`cb5026417f`.** Sampling `XKF2.AZ` after arm: shipped `=6` is pinned at -0.010
with a spread of 0.000 over the last 15 s, because the state cannot move at
all. With the re-init it dips to -0.120 and returns, settling at a spread of
0.010 - the same as `=3`, which has no inhibit. `cb5026417f` ranged 0.46 and
oscillated over 1 m/s^2 while measuring worse.

`AccelBiasMovingPlatform`, `VibrationRectificationBiasLearning`, `Replay` and
the four EK3 accel-bias tests all pass with it applied. That test is the cheap
check this file prescribes for any change in this area, and it is the one that
fails `cb5026417f` at 3.9 m.

Shipped as `9b852c9464` after the repeat runs above. SITL only: the two
previous attempts on this exact problem were both confident code arguments that
measured worse, so a flight is still what would settle it, and this entry
should be revisited when one is available. What tipped it was that the shape
moved as well as the number - a pinned state (spread 0.000) becoming one that
settles where the uninhibited case settles (0.010) - and that the platform
protection, which is the entire purpose of bit 2, is bit-identical either side.

Bit 2 still costs 0.284 m against `=2`'s 0.201 m. Reduced, not resolved.

## What is here

```
32471/
  README.md                       <- this file
  plots/
    make_plots.py                 regenerates all three from data/
    ab_vrf_height_error.png       height error vs time, 3 configs
    ab_platform_accel_bias.png    XKF2.AZ across arming, bit 2 clear vs set
    ab_summary_worst_error.png    worst height error by config
  data/ab-2026-09-04/
    harness.py                    the throwaway autotest probes
    install_harness.py            paste them into a checkout, and take them out
    metrics.py                    read the numbers back out of the logs
    vrf_off.BIN                   ACC_ZBIAS_LEARN=0, SIM_ACC_VRF_Z=0.15
    vrf_use.BIN                   ACC_ZBIAS_LEARN=2, same
    vrf_use_inhibit.BIN           ACC_ZBIAS_LEARN=6, same
    plat_bit2_clear.BIN           ACC_ZBIAS_LEARN=0, SIM_PLAT_ACC_Z=-1.0
    plat_bit2_set.BIN             ACC_ZBIAS_LEARN=4, same
```

The three scripts are the A/B instrument and are reusable for later runs, even
though they live in the 2026-09-04 directory with the first data they produced.
Run an arm with:

```
python3 32471/data/ab-2026-09-04/install_harness.py /path/to/ardupilot
cd /path/to/ardupilot && ./waf copter
VRF_LEARN=6 VRF_SIM=0.15 VRF_PRE=0.15 \
    Tools/autotest/autotest.py --no-configure test.Copter.VRFArmTransient
cp "$(ls -S logs/*.BIN | head -1)" /tmp/arm_6.BIN
python3 32471/data/ab-2026-09-04/install_harness.py /path/to/ardupilot --revert
python3 32471/data/ab-2026-09-04/metrics.py /tmp/arm_6.BIN
```

Each script's docstring carries the gotchas that cost time: the flight log is
the largest BIN not the last, autotest wipes logs/ between steps, PARM must be
read first-wins because context_pop logs its restores, and delay_sim_time needs
a reason argument.

SITL logs only. Real-flight numbers are quoted inline; those logs are not
committed.

## Reproduce

```
git checkout pr-vrf-core
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.VibrationRectificationBiasLearning
```

`VibrationRectificationBiasLearning` was rewritten 2026-09-04 to use
`SIM_ACC_VRF_Z` and to assert the height improvement via
`assert_ekfs_match_sim_state(max_pos_d_err_m=0.35)`; verified to fail when the
correction is disabled, which the previous version did not.
`AccelBiasMovingPlatform` is new and asserts the bias stays near zero on an
accelerating platform; verified to fail with bit 2 neutered.

To regenerate the plots:

```
cd 32471/plots && python3 make_plots.py
```

A negative test for the wrong-sign case would add `SIM_BARO_DRIFT` during
the learning hover and assert the stored bias is not accepted; it does not
exist yet. The thermal contamination itself has no SITL model (the SITL
baro has no temperature term).

## Review pass, 2026-09-04

Landed on top of the measured work above, after a `/pr-review` of the stack:

- The vehicle's accel-bias learning inhibit now reaches Replay. It was a plain
  frontend bool, so a replayed acro segment learned bias the aircraft did not.
  Added a DAL event pair following `setTerrainHgtStable`, plus the Replay
  dispatch - an event rather than an RFRN bit because the flags byte is full.
- The frozen correction is read from the DAL at the point of use rather than
  pushed in from the vehicle. Only the boot-time load was DAL-visible before, so
  a second arm in the same boot replayed with the wrong correction - which
  `logtc5_2` flew. Landed as a three-commit forwarder dance because the removal
  crosses AP_NavEKF3/AP_AHRS/Copter.
- `INS_ACC*_VRFB_Z` is now `#if APM_BUILD_COPTER_OR_HELI`. The `{Copter}` tag was
  documentation only, so the parameter shipped on Plane, Rover, Sub and Blimp as
  a dead settable knob. Verified: the string is in `arducopter`, absent from
  `arduplane`.
- The parameter is written once on disarm instead of every 100 Hz learning step.
  It made RISJ a per-frame replay message for nothing; EKF3 reads it once.
- `AccelBiasMovingPlatform` grew the positive control this file's own numbers
  imply - it now measures -0.990 m/s/s with bit 2 clear before asserting 0.000
  with it set, so a broken stimulus fails instead of passing.
- The four AHRS accessors no longer gate on `active_EKF_type()`, which could
  swallow a one-shot write during a transient EKF3 fault.

Two changes from that pass were reverted after reading this file: see "Measured
and rejected".

## Review round, 2026-09-05

tridge's automated pass at head `84ddc625b8` raised five findings plus six
smaller ones. Branch head after this round: `d951df4f82`, 27 commits, force
pushed. Every finding was re-derived from source before acting on it.

### Landed

- **`ACC_ZBIAS_LEARN=1` grew the stored value by its own value every flight.**
  `AP_AHRS::get_hover_z_bias_correction()` returned the stored parameter with
  no check of the enable flag, while the EKF applies it only when enabled. The
  learner adds it back to recover the total, so with bit 0 set and bit 1 clear
  it added back a correction that was never applied: `s(n+1) = b_true + s(n)`,
  reaching the 0.6 clamp in seven flights on the measured 0.089. Gated at the
  accessor. **This cannot move any number in this file**: every configuration
  ever measured or flown here is 0, 2, 3, 4, 6 or 7, and the fix is a no-op
  whenever bit 1 is set. It also restores the "stores the total" invariant this
  file defends, which until now held only when bit 1 happened to be set.
- **`RISJ` mis-parsed every pre-existing log.** The PR had added
  `accel_vrf_bias_z` ahead of `instance`. Replay copies the on-disk record into
  the compiled struct, so an older 9-byte record is not truncated but
  misaligned: the old instance byte lands in the low byte of the new float and
  `instance` reads 0, so IMU 1 and 2 overwrite IMU 0. Appending after
  `instance` does not work either - the struct is not packed, so a trailing
  float pads `offsetof(_end)` to 16 against a 13-byte format string, which is
  the "Log structures invalid" trap. Fixed by moving the value to its own
  `RISK` message, following `97b5b0448a` which split `RISJ` out of `RISI` for
  the same reason, and matching what #34292 did with `ROFM` beside `ROFH`.
- **`updateMovementCheck()`** compared `raw - residual` once a correction was
  applied. Reachable only between arm and liftoff, where the displacement is up
  to 0.6 against an `accel_limit` of 1.0. A strict no-op for the platform
  numbers in this file, which are measured disarmed.
- Smaller: the accel-bias inhibit DAL event is written on change instead of at
  1 Hz forever while disarmed; the hover bias is saved after `motors->armed(false)`;
  `rot_ned_to_body` renamed to match what `rotation_matrix()` returns; the INS
  header no longer pulled into everything that includes `AP_NavEKF3.h`.

### The ground-effect Z-bias inhibit was removed

It went through three states in one afternoon - narrowed to a baro height
observation, then held behind the feature flag, then deleted - because each
step made the next question answerable.

The deciding measurement is the inhibit present against removed entirely, at
`ACC_ZBIAS_LEARN=2`, worst |EKF height - truth| over 35 s:

| | inhibit present | removed |
|---|---|---|
| `SIM_BARO_GEFF_M=0` | 0.203 m | 0.201 m |
| `SIM_BARO_GEFF_M=1.0` | 0.169 m | 0.168 m |

1-2 mm, with the baro under-reading by a full metre in ground effect. Once the
correction is applied the bias state has little left to absorb. Its only
measurable effect was on a vehicle *not* using the feature - 0.604 m against
0.650 m - which is a default behaviour change for every EKF3 user, reached
through `takeoff_expected` that Plane sets on the takeoff roll. That is a
separable improvement for its own PR, and it is the one thing this PR now does
*not* do: there is no behaviour change at default settings at all.

### Re-measured without the gate, 2026-09-05

Same probe as 2026-09-04, on `d951df4f82`. Single runs.

| `ACC_ZBIAS_LEARN` | height error | `XKF2.AZ` range |
|---|---|---|
| 0 (off) | 0.653 m | 0.11 |
| 2 (use) | **0.201 m** | 0.02 |
| 3 (learn+use) | 0.206 m | 0.02 |
| 6 (use+inhibit) | **0.467 m** | 0.02 |
| 7 (all bits) | 0.471 m | 0.02 |

With `SIM_BARO_GEFF_M=1.0`, `=0` is 0.650 m and `=2` is 0.168 m: the
correction is worth the same whether or not the baro is corrupted near the
ground.

**This settles the stale `=6` row.** The 0.713/0.476 above was measured with
`cb5026417f` applied; "Still open" quoted 0.448 without it. On current code
`=6` is 0.467 m with an `XKF2.AZ` range of 0.02, confirming the post-drop
value. The tension itself is unchanged: bit 2 costs 0.467 m against 0.201 m.

### Corrections to this file and to claims made during the round

- **The five BINs in `data/ab-2026-09-04/` contain no replay messages.** They
  carry the `RISJ` *format* but zero `RISJ`/`RISI`/`RFRN` records, because that
  harness ran without `LOG_REPLAY=1`. They are fine for the plots, which decode
  by FMT through pymavlink, but they cannot be replayed and they are not
  examples of the misparse above.
- **SITL does model baro ground effect.** `SIM_BARO_GEFF_M`, added by
  `cbe1af2800` and already on this PR's base, makes the baro under-read by up
  to that many metres while the throttle is up, decaying to zero at 2 m AGL. It
  defaults to 0, which is why the 2026-09-04 A/B never exercised it. An
  in-session claim that SITL had no such model was wrong.
- **The EXTNAV/BEACON regression is not a property of the blanket gate.** It
  belonged to `learnZBias`, an SFD-branch design with a `switch` whose
  `default: false` meant "inhibit for the whole flight" on those sources.
  `git log --all -S learnZBias` finds nothing in the ArduPilot tree: it never
  landed here. `cab18be57b`'s commit message describes that history, and it was
  read during this round as describing what its own diff removes.

### `RISK` does not hit the #34292 `IFCHANGED` trap

`../34292/README.md` records that `AP_DAL::WriteLogMessage` returns early when
`!logging_started` without setting the `_end` retry flag, so a record written
only on change can be dropped forever - measured there as `ROFM=1` in one log
and `ROFM=0` in the next log of the same power cycle. That fix is on #34292's
branch, not on this base.

`RISK` escapes it for the same reason `RISJ` does: it is written from
`AP_DAL_InertialSensor::start_frame()` (`AP_DAL.cpp:93`), inside the
`force_write` bracket set at `:46` and cleared at `:120`. That file is explicit
that reasoning about `IFCHANGED` is what failed, so it was counted rather than
argued. Two flights in one power cycle with a log download between them to
force `stop_logging()`:

```
feature on   log 3: RISJ=3 RISK=3  {0:0.15, 1:0.15, 2:0.0}
             log14: RISJ=3 RISK=3  {0:0.15, 1:0.15, 2:0.0}
at default   log 3: RISJ=3 RISK=3  {0:0.0,  1:0.0,  2:0.0}
             log11: RISJ=3 RISK=3  {0:0.0,  1:0.0,  2:0.0}
```

### History

Squashed from 38 commits to 27, each fix folded into the commit that
introduced the problem, content verified byte-identical across the rebase
(`git diff` between the pre- and post-squash heads is empty). Every commit
builds `arducopter`. Two commits do not build the `Replay` tool: adding a value
to `AP_DAL::Event` breaks Replay's exhaustive switch immediately, and the
handler cannot land until `NavEKF3::setInhibitAccelBiasLearning` exists, which
needs the enum. Closing that window entirely would put two modules in one
commit. It was 18 commits wide before this round.

## Branches and people

- `pr-vrf-core` - the PR branch, `9b852c9464` as of 2026-09-05. Depends on #32396.
- Author: @andyp1per. Approved, then reworked by the 2026-09-04 review pass.
- Distinct from #34209 (XY bias in unaided flight) and #32473 (acro
  inhibit), which still carries `cb5026417f`.
