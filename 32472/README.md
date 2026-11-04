# PR #32472 - Ground effect altitude and timeout parameters (Copter / AP_GroundEffect)

Analysis archive for [ArduPilot/ardupilot#32472](https://github.com/ArduPilot/ardupilot/pull/32472).
Branch `pr-ground-effect`, base master, head `2f81d1bfc2`. Merged upstream
2026-09-01, and folded into `SmallFastDrone-4.7-base` as a result. No logs
committed; real-flight numbers are cited inline.

## Status (one line)

Fourteen commits, two autotests driven by the new SIM_BARO_GEFF_M, approved
with mechanical items pending; the parameters were flown for six months as
TKOFF_GNDEFF_ALT/TMO on the SmallFastDrone branches across eight airframes,
and two places where this design differs from what was flown are recorded
below.

## The problem

Copter's window releases at 0.5 m of EKF altitude, which strong
propwash airframes cross within a few hundred ms while the barometer is
still metres wrong: a BF_X indoor quad -5 m, a 5-inch baro-only quad -9 to
-11 m, a MatekH743 flow quad -6.15 m at motor start, a ducted quad 121 Pa
(10 m) on a ground throttle ramp at ThO 0.15 with the rangefinder at
0.04 m.

## The conclusion and why

Three decisions, each with flight evidence:

- HAGL for the release check. BF_X quad log204 (not committed,
  EK3_RNG_USE_HGT 3, AltHold): the EKF altitude read -2.3 m at a true
  1.2 m, so a release check on EKF altitude re-armed the window right
  after every 5 s timeout; the noise floor stayed on permanently, the
  terrain reset (#32553) never fired, and the EKF drifted 3.4 m while
  the baro was only 0.3-2 m off. Switching the check to the AGL KF
  height (log206) gave a stable 0.3 m terrain offset and a clean
  release. This PR does the same through ahrs.get_hagl().
- A minimum hold. The MatekH743 flow quad's log11 first applied TMO 3;
  the ducted quad went 3 -> 5 for a slow-spooling frame; log22 with TMO
  0 is the A/B (below).
- No re-latch of takeoff_expected on descent. What the flag reaches
  inside the filter is wider than the baro noise: on the SmallFastDrone
  build a dip below TKOFF_GNDEFF_ALT re-latched it and, through a
  zero-velocity fusion term gated on it (SmallFastDrone only; master
  never had the term), replaced a rangefinder-anchored velocity with
  "not moving" on every dip (5-inch baro-only quad, log41). Keeping the
  flag to "about to leave the ground" is right.

## Key finding: two things the flown design did that this one does not

1. The takeoff timer. The SmallFastDrone detector resets takeoff_time_ms
   while land_complete, so TMO and the 5 s cap count from the land
   detector clearing. This PR anchors it while !throttle_up &&
   land_complete, throttle_up = has_manual_throttle() && throttle > 0, so
   in Stabilize and Acro the 5 s cap counts from the first throttle.
   Airframes that sit at throttle longer than that before lifting exist:
   BF_X quad log196 7.9 s, ducted quad log21 4-9 s, MatekH743 flow quad
   3.7 s from arm to throttle. After the cap the EKF fuses a
   propwash-corrupted baro at full weight on the ground. Either anchor the
   timer on land_complete as flown, or say in the body that
   manual-throttle spool-ups longer than 5 s are uncovered. (Note that
   #32972's pre-liftoff anchor ends at the first throttle in these modes
   regardless; see ../32972/.)
2. The descent re-enable. BF_X quad log210, baro-only (no rangefinder, so
   no HAGL), re-enable disabled: hovering low with the normal K the baro
   read -2.66 m in ground effect, the controller descended to follow it,
   ground effect grew, and the vehicle was pulled onto the floor. With the
   re-enable and the noise floor the contamination is bounded (~1.65 m,
   log208). This PR replaces the re-enable with an altitude gate on
   touchdown_expected, which needs a demanded descent (velocity target
   below zero), so a low hover being pulled down at mid-stick is not
   covered. The body defers "tightening the EKF's response to
   touchdown_expected"; log210 is what that follow-up is for, on
   baro-only airframes specifically. The gate's own defects, found in
   flight on 2026-09-09, are `../34362/`. For rangefinder airframes the HAGL
   check makes a re-enable safe (log206) and the AGL-KF switch (#33359)
   removes most of the need.

## Field observations on GNDEFF_ALT from small indoor copters

- The threshold competes with the operating envelope. On a 5-inch indoor
  quad flying at 1.10 m mean (not committed), a 1.0 m threshold put 40%
  of airborne samples inside ground effect, so the 4x baro deweighting
  and the -0.5 m innovation floor (`XKF3.IPD` pinned at -0.5000) were the
  cruise condition; at 0.5 m it was 11%, and every dip re-entered it.
  Either flag deweights the baro the same way, so `GNDEFF_ALT` doubles as
  a floor on the useful hover band for such airframes.
- Without a rangefinder the gate is evaluated on the estimate it exists to
  protect. On a SkySakuraH743 baro-only quad (not committed) an EKF
  height over-read of 0.7-1.3 m had the gate open 34%, 8% and 94% of
  genuinely-low samples on three consecutive flights until the thrust
  scale was corrected (then 100%); with a payload the estimate never
  cleared 1.0 m and the gate latched for the whole flight. The HAGL path
  is the fix where a rangefinder exists.
- The HAGL path inherits an AGL KF dropout defect: with the rangefinder
  out of range low on the deck, `aglKfH` can ramp at ~0.4 m/s for up to
  5 s while the vehicle is motionless (`../33478/`, finding 3), which can
  release the takeoff window early or defeat `near_ground` at touchdown.
  Not observed in this PR's tests; a rangefinder-freshness check at
  `getHAGL()` would close it.

  **Observed 2026-09-09, by a different route (log7, SFD-O4).** Not the
  AGL KF ramping on the deck, and the failure is the opposite sign: the
  rangefinder went out of range **high** for 101 s continuous
  (`RNGFND1_MAX=15` on a vehicle that flies well above it), the AGL KF
  went invalid on its 5 s timeout, and `ahrs.get_hagl()` returned false
  outright. `near_ground` then came from the drift fallback, and the
  vehicle was 21.8 m from its takeoff point - 1.8 m past
  `AP_GROUNDEFFECT_TAKEOFF_DRIFT_NE_MAX_M` - so `near_ground` was
  asserted unconditionally **at 17.9 m**, in a stationary hover, for 51 s
  (`XKF4.SS` bit 12; 20.8% of the whole armed flight). `slow_horizontal`
  came free from hovering and `slow_descent` from `CTUN.DCRt` dithering
  to -0.0 m/s, since `descent_demanded` has no deadband.

  Corrected the same day, before any fix was written: `CTUN.DCRt` is the
  wrong field. It logs `get_vel_target_U_ms()`; `AP_GroundEffect` reads
  `get_vel_desired_U_ms()`, which is `-PSCD.DVD`. `CTUN.DCRt` was
  negative in only 24.1% of samples over the latch and would not have
  held the term. `-PSCD.DVD` was negative in **100.00% of 508 samples**,
  p50 -0.0000, max -0.0000, longest continuous run 50.8 s, matching the
  99.8% of XKF4 samples with bit 12 set. The term is not dither crossing
  zero: in a hover the desired vertical velocity settles to a small
  persistently negative residual and never reaches zero. A 0.05 m/s
  deadband removes 98.4% of it, against a real approach on the same
  flight at -0.504 m/s p50.

  The cost is on the EKF side and is measured: with `EK3_GND_EFF_DZ=-8`
  the flow-only lane's baro was deweighted to R = 64 m^2 and its
  innovation pinned at -0.5000, and its altitude ran away 5.6 m in 38 s
  against a flat baro. See `../32972/` finding 6, and `logs/log7_sfdo4.md`
  in the private analysis repo. The rangefinder-freshness check named
  above would not have caught this one; the drift fallback asserting
  proximity rather than merely distrusting `height_m` is the part that
  did it.
- Real amplitudes for `SIM_BARO_GEFF_M`: -9 to -11 m at spool-up, -16 to
  -21 m at touchdown (200-300 Pa in under a second), 2.4-3.8 m steps in the
  estimate. The SITL runs in the PR thread used 1 and 5 m.

## Also measured

- TMO 0 vs 3 on the ducted quad (log22 vs log21, not committed):
  post-compensation BARO.Alt std 39 -> 92 cm, alt-error std 11 ->
  17 cm, a 0.10 Hz mode the vehicle followed (84 cm rangefinder swing),
  two post-arm yaw resets. Confounded with a BARO_THST_FILT change in
  the same flight.
- Defaults vs flown: GNDEFF_ALT 0.5 here; the ducted frame runs 1.5, the
  5-inch baro-only quad went 1.0 -> 0.5 and found 11% of its indoor
  hover samples below 0.5 m. SIM_BARO_GEFF_M decays to zero at 2 m AGL,
  which is about the ducted case, not the small-quad one.

## What is here

```
32472/
  README.md    <- this file
  valt-low-hover/
    test_valt_low_hover.py  <- VALTLowHoverGroundEffect, for arducopter.py
                               (SFD; VALT, baro-only mode, seeded noise)
    althold_33478_test.py   <- EK3_AglKfVelBaroWash as tried on #33478
    timeline.py             <- per-second SITL flight timeline
    flagscan.py             <- flag share and baro error by range, a log
    contact.py              <- 10 Hz rows around a floor contact
    headscan.py             <- firmware and height parameters of a log
    lowhover.py             <- time low and floor contacts, a log
    washscan.py             <- baro minus range by range, a log
    holds.py                <- centre-stick holds, a log
    contacts.py             <- floor contacts with the stick before them
    sinkscan.py             <- unasked sinking near centre stick
    switch.py               <- what height the 4.7.0 re-latch follows
```

No logs committed.

## Reproduce

```
git checkout pr-ground-effect
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.TakeoffGroundEffectAlt,TouchdownGroundEffectAlt
```

Not yet built: the log210 pull-down (AltHold at mid-stick at 0.3-0.4 m
with SIM_BARO_GEFF_M 3 and no rangefinder; the injected error grows as
the vehicle descends, which is the feedback loop) and the Stabilize
5 s-cap case (see ../32972/).

The log210 pull-down was built on 2026-11-03, with a range finder for
flow and no range finder height; see the next section. To run it, insert
`valt-low-hover/test_valt_low_hover.py` into `arducopter.py` before
`GroundEffectCompensation_takeOffExpected`, register it after that test,
then `autotest.py --no-configure test.Copter.VALTLowHoverGroundEffect`.
It asserts nothing; it prints one VALTLOW line per wash case.

## 2026-11-03: the low hover pulled into the floor, on 4.7.2

tester B's 4-inch (SkySakuraH743, baro height, DroneCAN flow and a DroneCAN
range finder used for flow only, EK3_RNG_USE_HGT -1, VALT_POS_EXPO 5,
GNDEFF_ALT 1, GNDEFF_TMO 3) reported "sucked into the floor" at centre
stick in VALT on the SmallFastDrone 4.7.2 beta. Log 62 at 86-93 s is the
log210 case in the field (tier 1):

- Hovering at 0.27-0.30 m on the range finder with both flags clear
  (85.8-87.0 s), the baro read 0.0-0.9 m above the range finder and the
  EKF height rose from 0.10 to 0.65 m with it.
- VALT held its 0.58 m target and descended to follow; the lower it went
  the higher the baro read (+2.0 m at a range of 0.01 m). It reached the
  floor at 88.1 s with the EKF at 0.74 m.
- A contact step in the baro to -7.8 m took the EKF to -0.67 m. From
  89.2 s the EKF then climbed back up with the baro reading +1.5 to +2.0
  m and the pilot's small climb demand, to 1.3 m at 93.9 s and 2.26 m
  later. VALT held throttle at 0.10-0.14, and the range finder read under
  0.15 m from 88.1 to 99.6 s apart from brief readings of 0.19-0.27 m.

His 4.7.0 logs 47 and 48 were flown mostly above 2 m: 8 and 72 VALT
samples below 1 m, against 2843 and 2036 at 2 m or more. In VALT,
takeoff_expected was set in every sample below 1 m and in 5-75% between
1 and 2 m, so these logs do not show 4.7.0 holding a low hover. In logs 62
and 63 takeoff_expected is never set in VALT. touchdown_expected, which
needs a demanded descent, is set in 4-63% of the samples below 1 m,
depending on the range bin. See also ../34942/README.md.

SITL (tier 2), `VALTLowHoverGroundEffect`: SITL flow and analog range
finder, EK3_RNG_USE_HGT -1, VALT_POS_EXPO 5, GNDEFF_ALT 1/TMO 3 (on 4.7.0
GND_EFFECT_COMP 1, TKOFF_GNDEFF_ALT 1, TKOFF_GNDEFF_TMO 3). A Lua script
puts the wash on SIM_BARO_GLITCH and SIM_BAR2_GLITCH, as the 4.7.0 build
has no SIM_BARO_GEFF_M:

- a bias at the floor falling linearly to zero at a set height, plus
  optional low-passed noise;
- ramped in over 2 s once the vehicle first leaves the floor.

It climbs to 0.4 m on the range finder, centres the stick and holds for
60 s. The figures are the share of the last 55 s with the true height
under 0.15 m.

| Wash at the floor | 4.7.0 | 4.7.2 | A | B |
|---|---|---|---|---|
| +1.5 m, zero at 1 m | 48% | 100% | 39% | 47% |
| -1.5 m, zero at 1 m | 0% | 0% | 0% | 0% |
| +0.5 m and 0.8 m rms noise, zero at 2 m | 65% | 39% | 99% | 56% |

Builds and SITL binaries:

- 4.7.0 is a private branch `81abda3d5e` (`bc53e5f4`).
- 4.7.2 is refresh12 `f085ae566f` (`38999a35`).
- A is `f085ae566f` with VALT's 0.1 m/s clamp also applied while the
  range finder reads under 1 m (`d1c5cc91`).
- B is `f085ae566f` with AP_GroundEffect setting touchdown_expected while
  airborne with a HAGL under GNDEFF_ALT (`96c8f87b`).

Flag share over the hold: on 4.7.0 takeoff_expected 70-100%; on 4.7.2 and
A neither flag; on B touchdown_expected 66-100%.

Two earlier versions of the wash script are different measurements, not
corrections:

- Applied from arming, the error was absorbed by the arming datum reset
  and moved the target instead.
- Cut to zero below 0.15 m, it left the floor clean.

Neither put 4.7.2 on the floor.

What the runs show:

- The failure reproduces, with a baro error that grows faster than the
  height falls. 4.7.2 sinks within 4 s of centring the stick. It then
  stays on the floor at zero throttle for the rest of the hold, the EKF
  reading 1.1 m against a 0.45 m target, as in log 62.
- With no flag set, neither the clamp nor the EKF's baro deweighting is
  in force. This is the gap recorded above when the re-latch was dropped.
- 4.7.0 is not immune. Its re-latched takeoff_expected keeps the clamp on,
  so the sink runs at 0.07 m/s. On the floor the clamp drags the target
  up to the estimate until throttle builds and the vehicle lifts itself
  off, after about 23 s. It still spends about half the hold on the
  floor.
- Restoring the clamp alone (A) or the flags (B) gives back 4.7.0's result
  in the deterministic case. In the noisy case both are worse than 4.7.2
  (99% and 56% against 39%).

The mechanism is derived from the source and the timelines, not measured
on its own:

- The EKF's ground effect floor clips only innovations where the baro
  reads below the estimate, so a noisy baro that reads high ratchets the
  estimate upwards.
- With the correction limited to 0.1 m/s, a persistent error still runs
  the vehicle down. The clamp then holds it there, as the target is
  dragged with the estimate.

So the 0.1 m/s clamp is skipped on 4.7.2 in a low hover, but putting it
back is not the fix. Neither the clamp nor the flags keeps the vehicle off
the floor when the baro reads high near it: near the floor the EKF height
is the baro's, and the baro is what is wrong there. Not yet tried:

- a height source that is right near the floor (tester B's range finder, used
  for flow only, drops out at the floor itself);
- an EKF response to a baro reading high near the floor.

### Repeats and the negative dead zone, 2026-11-03

The noisy case does not repeat. Unmodified 4.7.2 (`38999a35`, flags never
set) gave 39%, 23%, 32%, 48% and 59% across five runs; the 59% run had
EK3_GND_EFF_DZ -8, which changes nothing without a flag. So in the table
above only A's 99% stands apart from 4.7.2 in the noisy case. The 4.7.0
and B figures there (65% and 56%) are within that scatter. The
deterministic case repeats: 100% and 99% on 4.7.2.

A negative EK3_GND_EFF_DZ raises the baro noise in ground effect to its
magnitude, in both directions, but only while a flag is set. Same test,
share of the hold on the floor, one run per cell unless listed:

| Build and settings | +1.5 m to 1 m | noisy, to 2 m |
|---|---|---|
| 4.7.2, DZ -8 | 99% | 59% |
| B, DZ -8 | 62% | 58% |
| B, DZ -8, EK3_OPTIONS 16 | 65% | 0, 0, 0% |
| 4.7.0, DZ -8 | 55% | 43% |
| 4.7.2, EK3_OPTIONS 16 | 100% | 0, 0, 0% |
| 4.7.2, EK3_OPTIONS 92 | 100% | 0, 22, 0% |
| 4.7.2, tester B's EK3_OPTIONS 10, RNGFND1_MIN 0.08 | 100% | 31, 65, 29% |
| 4.7.2, EK3_OPTIONS 26 (tester B's plus bit 4), RNGFND1_MIN 0.08 | 100% | 2, 0, 0% |

EK3_OPTIONS 16 is bit 4, the AGL KF vertical velocity fused as velD; 92 is
the SFD board default (bits 2, 3, 4, 6).

- The noisy case is held by bit 4, with or without the low hover flag
  and the negative dead zone: true height 0.28-0.56 m and EKF height error
  0.03-0.06 m rms on every bit 4 run but one. The negative dead zone with
  the flag and no bit 4 does not help (B, DZ -8), as with the baro
  deweighted nothing else holds the vertical.
- Nothing tried holds the deterministic case. A baro bias that stays 1.5 m
  high over the whole lower metre pulls even a deweighted baro's estimate
  up over a minute, and a velocity observation cannot remove a bias in
  height. Tester B's baro does not do that at hover height: between 0.25 and 1.0
  m on the range finder, baro minus range had medians -0.07 to -0.24 m and
  p90s up to +0.24 m in logs 62 and 63; his large errors are below 0.25 m.
  So the noisy case is the closer model of his flights.
- tester B flies without bit 4: EK3_OPTIONS 10 is bits 1 and 3. SkySakuraH743
  does not include sfd_defaults.parm, and on 4.7.0 velD fusion was bit 5,
  also off in his 10, so it is not what changed between his builds.
- SITL's analog range finder reads down to 0 m (RNGFND1_MIN 0). Tester B's has
  RNGFND1_MIN 0.08 and drops out at the floor, where the AGL KF velocity
  stops being fused. With his minimum and his EK3_OPTIONS the noisy case
  still sits on the floor (29-65%); adding bit 4 alone holds it (0-2%,
  EKF height error 0.04-0.09 m rms).

### Did it work before without a range finder? 2026-11-03

The flight record, with tester B's own logs scanned for the time spent low in
AltHold or VALT and for the baro against the range finder (tier 1):

- tester B's 4.6 logs (the VAlt comparison set, 4.6.3-SFD, March 2026; and an
  AltHold set from January and February 2026) flew baro height with EK3_GND_EFF_DZ -4 or +4 to +7. Near the floor
  their baro read 1-6 m low against its own value higher up. Low reads
  push the estimate down and VALT up, away from the floor, and the EKF's
  one-sided floor is built for that sign. The plain 4.6 log spent 17 s at
  centre stick under 0.6 m with no floor contact.
- The 4-inch reads the other way: under 0.25 m the baro was +0.2/+0.45 m
  median and +1.8/+1.9 m p90 above the range finder (logs 62 and 63),
  with low spikes at contact. High reads pull VALT into the floor, and
  nothing in the EKF or AP_GroundEffect handles that sign. Its 4.7.0 logs
  47 and 48 spent no time under 0.5 m, so there is no 4.7.0 low hover on
  this airframe to compare with.
- The reference the reference 4-inch quad, the same airframe type on the same 4.7.0 branch,
  settled onto the deck at mid-stick with the clamp and the corrected
  thrust scale, the estimate reading 0.16-0.60 m high on the way down
  (log81, the private analysis repo). Those logs
  are not on the primary machine; the figures are the note's.
- tester B's June 4-inch (tester B's June 4-inch, 4.7.0-beta6) used the range finder for
  height (EK3_RNG_USE_HGT 3, EK3_GND_EFF_DZ -8) and from log57 the AGL KF
  velocity (EK3_OPTIONS 56, bit 5 on that numbering), and flew mostly GPS
  modes.
- What 4.7.2 did drop is the low hover re-enable, which the record judged
  necessary for baro-only vehicles with a noise floor (log210; the
  "low-hover ground effect protection in AP_GroundEffect that holds
  without a range finder" owed in ../32553/README.md). In the SITL above
  it slows the sink and lets the vehicle lift itself off (48% against
  100%) but does not stop it. log210's baro is recorded as reading -2.66
  m low, the self-correcting sign, so how it pulled that vehicle down is
  not settled here; the log is not on this machine.

#### Superseded 2026-11-03 by logs 66 and 67

"There is no 4.7.0 low hover on this airframe to compare with" no longer
holds. Tester B flew logs 66 and 67 on 4.7.0 (`af47743e`) on the same board
(SkySakuraH743 `0040003B`, as for 47, 48, 62 and 63) after 62 and 63
(STAT_BOOTCNT 179 and 181 against 154 and 160), low, with the same
parameters (EK3_OPTIONS 10, EK3_GND_EFF_DZ 4, BARO1_THST_SCALE -255, THR_DZ
50, VALT_POS_EXPO 5). Floor contacts in VALT after liftoff (range under
0.10 m for 0.3 s or more), counting those from a stick within 80 of
centre over the 2 s before, and only those the vehicle then left:

| Log | Build | VALT under 0.6 m | contacts near centre | per min | GE flag before |
|---|---|---|---|---|---|
| 66 | 4.7.0 | 127 s | 5 (of 18) | 2.4 | 100% |
| 67 | 4.7.0 | 51 s | 1 (of 2) | 1.2 | 100% |
| 62 | 4.7.2 | 82 s | 11 (of 11) | 8.1 | 0-25% |
| 63 | 4.7.2 | 53 s | 10 (of 13) | 11.3 | 0-70% |

Together 2.0 per minute under 0.6 m on 4.7.0 against 9.3 on 4.7.2 (6
contacts in 178 s against 21 in 135 s). The other 12 in log 66 came with
the stick at 1363-1412, a demanded descent. The baro reads high near the
floor on both builds (p90 +1.1 and +2.0 m under 0.25 m in 66 and 67,
+1.8 and +1.9 m in 62 and 63), and the ground effect flags are set before
contact on 4.7.0 and mostly not on 4.7.2, as the re-latch predicts.

- So on this airframe 4.7.0 does hold a low hover better, as tester B said,
  and by about the margin the SITL test gives the re-latch (48% against
  100% of the hold on the floor). It is not free of it: log 67 sat on the
  floor 5.1 s from centre stick and needed 1597 to leave, and log 66 left
  one contact only at 1650.
- The true vertical speed near centre stick does not separate the builds
  (unasked sinking faster than 0.1 m/s in 11% and 41% of samples on
  4.7.0, 18% and 26% on 4.7.2); it counts VALT arresting the pilot's own
  descents as well.
- Two flights a build, one pilot, flown in sequence: the pilot's own
  behaviour is not controlled for.
- This is not a baro-only result. 4.7.0's re-latch tests
  `ahrs.get_hagl()`, which with tester B's EK3_OPTIONS 10 is the EKF terrain
  state minus its height, valid only while the range finder feeds the
  terrain estimate. At the 31 and 32 clears in VALT in logs 66 and 67,
  XKF5.HAGL had medians of 0.97 and 0.98 m, at TKOFF_GNDEFF_ALT 1.0. The
  EKF height from the log start had medians of -0.38 and +0.22 m. The
  range finder decides when the protection is on, and variant B does the
  same. Without one, the switch falls back to the baro-corrupted height
  that made the reference the reference 4-inch quad's gate fire at random
  (the private analysis repo).
- The 4.7.0 switch is rough. The flag chatters around 1 m, often several
  times a second, and three times HAGL read about 1 m with the vehicle on
  the floor (66 at 43.4 and 133.6 s, 67 at 105.2 s), clearing the
  protection there.

#### Baro-only SITL A/B, 2026-11-03

The same test with nothing but the baro observing the vertical: no flow,
EK3_SRC1_VELZ 0, GPS for the horizontal, and the range finder declared
forward (RNGFND1_ORIENT 0). The EKF and Copter read only a downward one;
SITL still points it down, so the wash script reads true height from it.
The log confirms the EKF saw no range (XKF5.rng 0 throughout). Builds as
above (`bc53e5f4`, `38999a35`); share of the hold on the floor:

| Build, EK3_GND_EFF_DZ | +1.5 m to 1 m | -1.5 m to 1 m | noisy, to 2 m |
|---|---|---|---|
| 4.7.0, 4 | 93, 93% | 0% | 40, 25, 50% |
| 4.7.2, 4 | 100, 100% | 0% | 28, 45, 37% |
| 4.7.0, -8 | 91, 90% | 0% | 33, 61, 62% |
| 4.7.2, -8 | 100, 100% | 0% | 57, 52, 46% |

- Without a range finder 4.7.0 is no better than 4.7.2. Its re-latch
  reads the EKF height, which a baro reading high near the floor puts
  above TKOFF_GNDEFF_ALT, so the flag is set for only 12-15% of the hold
  in the +1.5 m case (70% with the range finder deciding it). In one run
  the clamp held the sink to about 0.06 m/s on the way down. On the floor
  the EKF climbed past 1 m and the re-latch cleared the flag, releasing
  the clamp at the floor.
- A baro reading low near the floor holds on both builds with or without
  a range finder: 0.84-0.87 m, never on the floor. That is the sign tester B's
  older airframes had (see "Did it work before" above).
- The noise floor the record recommends for baro-only vehicles (DZ -8)
  does not help here: 52% of the noisy hold on the floor on both builds,
  against 37-38% at DZ 4, inside the scatter but the same way on both.
- So tester B's 4.7.0 advantage on the 4-inch (logs 66 and 67) comes from his
  range finder switching the protection. Without one, neither build holds
  a low hover over a baro that reads high near the floor.

#### Bit 4 on #33478's own head, 2026-11-03

Ported to ALT_HOLD as `EK3_AglKfVelBaroWash` on #33478's head
(`d0c4056d36`, branch `r1103/33478-wash` in `../../fix-33478`, not
committed; SITL `a68a40b4`), noisy wash only. Two findings correct what
is above.

- ALT_HOLD with a downward range finder runs surface tracking
  (SURFTRAK_MODE 1 by default) and holds the range, so with fusion off it
  sat on the floor 4% of the hover. VALT skips surface tracking by design
  (`mode_valt.cpp`), which is why VALT sinks where ALT_HOLD does not. Tester B
  has SURFTRAK_MODE 1, so ALT_HOLD would use his range finder this way.
- With SURFTRAK_MODE 0, bit 4 alone does not hold the hover on #33478:
  fusion off 82% and 64% on the floor, bit 4 76% and 62%. The EKF held
  its target about 0.4 m above the vehicle with VFuse set throughout: a
  velocity observation does not remove a baro bias in height. With the
  wash held back 5 s until the fusion was running, bit 4 gave 60% and
  22%, the vehicle sinking at about 0.02 m/s as the estimate took in the
  bias.
- On refresh12 the same case with bit 4 kept the EKF within 0.05 m rms of
  the truth for 55 s with the baro reading about 0.4 m high (valtv472
  runs above). So "the noisy case is held by bit 4" is true of the SFD
  stack, not of #33478 alone; some other change on refresh12 keeps the
  estimate off the baro bias. Not yet identified.

#### Superseded 2026-11-03 (later): no other change, the noise sequence

"Some other change on refresh12" was wrong, and so is any reading of the
bit 4 rows above as a reliable hold. All measured on refresh12
(`f085ae566f`, SITL `38999a35`; the scratch tree's build of the same head
is `d708f429`) with the noisy wash:

- #33478's ALT_HOLD test (surface tracking off) fails on refresh12 as it
  does on #33478's head. Bit 4: 73% and 100%; 98% and 100% with GNDEFF_ALT
  1 / GNDEFF_TMO 3; 100% and 100% with the bit 4 leg flown first, so
  nothing carries over from the fusion-off leg. Fusion off: 63-77%.
- The SFD test's own procedure (climb to 0.4 m on the range finder) holds
  with bit 4 in VALT and in ALT_HOLD alike: 0, 0, 0% in ALT_HOLD against
  33% and 26% with fusion off. Run in VALT with #33478's procedure it gave
  1% and 67%. So it is neither the mode nor the ground effect window.
- The wash script's noise came from one unseeded sequence, and the SFD
  procedure's timing repeated it. Seeding it (SCR_USER5, test as now in
  `valt-low-hover/test_valt_low_hover.py`), VALT, same six seeds:

  | Seed | 1 | 2 | 3 | 4 | 5 | 6 | vertical speed rms |
  |---|---|---|---|---|---|---|---|
  | fusion off | 64% | 36% | 47% | 24% | 23% | 32% | 0.15-0.19 m/s |
  | bit 4 | 7% | 74% | 0% | 0% | 2% | 0% | 0.04-0.06 m/s |

- Bit 4 steadies the hover on every seed and usually keeps it off the
  floor, but not reliably. A velocity observation cannot remove a steady
  baro bias in height. How much bias the estimate has taken in when the
  hover starts decides the outcome (seed 2; in the unlucky SFD run a -1.2 m
  baro spike at the start of the hover pulled the estimate down by about
  the bias). The earlier 0-2% rows, with EK3_OPTIONS 16, 26 and 92 and
  variant B with DZ -8, are each one realisation of that sequence.
- The same holds for the advice "EK3_OPTIONS 26 for tester B": it steadies the
  hover and usually holds it in SITL, and is not a fix. The flight record
  adds EK3_AGL_ABIAS_P 0.3 for bit 4 on a real airframe
  (the private analysis repo).
- Not explained: in the SFD procedure's VALT runs, XKF3.IPD sat about 0.3 m
  below baro minus XKF1 height on average, against equal in the ALT_HOLD
  runs. BOf stayed 0 and EK3_OGN_HGT_MASK is 0. Derived from the logs,
  mechanism not found.

- So for tester B this is configuration first: EK3_OPTIONS 26. It needs no
  firmware change and is what the SFD boards already fly (92 includes bit
  4). Not flown yet; SITL only, and SITL's wash is a model fitted loosely
  to logs 62 and 63, not their recorded baro.

## Branches and people

- `pr-ground-effect` - the PR branch (local matches GitHub head
  2f81d1bfc2).
- SmallFastDrone-4.6-AltHold: 35a7f215dc (TKOFF_GNDEFF_ALT), b417228a68
  (TKOFF_GNDEFF_TMO); SmallFastDrone-4.7-beta becb063a13 (HAGL check).
- Related: #32972 (the EKF side; its anchor's outer gate is this
  window), #32553, #33359.
