# PR #32972 - Protect height fusion from baro ground effect at takeoff (EKF3)

Analysis archive for [ArduPilot/ardupilot#32972](https://github.com/ArduPilot/ardupilot/pull/32972).
Branch `pr-baro-gnd-effect`, stacked on #32768. No logs are committed;
the numbers below are from real indoor flights (cited inline) and from
the code.

## Status (one line)

Eight commits on top of #32768 (five plus three review fixups);
flight-developed on a BF_X indoor quad (SmallFastDronev1 board) over 22
indoor flights (Mar 2026) and run since on two more airframes; two SITL
autotests on the branch; rebased onto the 11-commit #32768 rewrite and
pushed 2026-09-04 (263f181a18), which cleared all twelve red CI checks;
the pre-liftoff anchor ends earlier than the PR body says (finding 1) and
can also engage in mid-air (finding 5); a 2026-09-09 flight adds a second
real-flight case of the innovation floor blocking a correction, this time
in level cruise (finding 6).

The 2026-09-04 automated review and the three commits answering it are in
[review-response-2026-09-04.md](review-response-2026-09-04.md); findings 4
and 5 below live there in full.

## Review 2026-09-10: the noise floor widens the gate it relies on, and one test measures the wrong signal

Module discipline holds on all 25 commits, all five ground-effect commits
and HEAD build `./waf copter` cleanly when built individually, `diff --check`
is clean with no tabs and no non-ASCII in any diff or message,
`dal.get_time_flying_ms()` is DAL-logged via RFRH so the anchor gate is
replayable, `resetHeightDatum()` refreshes the reference after zeroing in
the right order, and EKF2 needs no change (it hard-codes `gndMaxBaroErr =
4.0f` so it has no equivalent DZ=0 bug). The estimator logic is sound. Four
things block merge.

**M1. The three fixups do not squash mechanically.** Simulating `rebase
--autosquash` with per-file 3-way merges: `f282f9df7a` onto `90a7b58f40`
gives **2 conflicts**, `263f181a18` onto `66e976c661` gives **1**, and
`c9fb73f0ec` onto `8ebd7f71e6` is clean. Both conflicts come from
`!assume_zero_sideslip()`, which `2371087c61` introduces *later* but which
appears as fixup context. Worse, `f282f9df7a`'s second hunk puts
`gndEffectHgtResetSuppressStart_ms = 0;` inside a block that `66e976c661`
creates and that does not exist at the fixup's target commit. A careless
resolution silently drops the suppression-window reset - so the window is
cleared once per boot instead of once per ground-effect episode, and a
failed baro is masked once per flight rather than once per episode - or
leaves an intermediate commit that does not compile.

**M2. Squashing must also rewrite the three target commit messages.** None
mentions what its fixup adds: `90a7b58f40` says nothing about the 5 s
suppression bound, `66e976c661` nothing about the 5 m reference-innovation
guard (the whole mid-air re-arm defence), `8ebd7f71e6` nothing about
`BaroGroundEffectResetSuppression`, an entire second test.

**M3. The negative-DZ noise floor also widens the innovation gate and the
bad-IMU detector, and nothing says so.** `R_OBS[5] = posDownObsNoise` and
`R_OBS_DATA_CHECKS[i] = R_OBS[i]`, so the floored R feeds both the Kalman
gain and every consistency check:

- `hgtTimeout` needs a raw innovation of `5*sqrt(P+R)` - about 20 m at the
  default DZ=+4 / ALT_M_NSE=2, and **about 40 m at the recommended DZ=-8**.
  Real ground-effect errors are 4-11 m, this record's own range. So on a
  vehicle configured as this PR recommends, the ResetHeight suppression
  added by `90a7b58f40` **cannot fire from ground effect at all** - and the
  PR body claims the suppression protects that case.
- The accel-aliasing detector uses `sq(hgtErr) > R_gain * R_OBS[5]`, so its
  threshold moves from ~12 m to ~24 m at DZ=-8 - and `!badIMUdata` is the
  suppression's only escape hatch.
- Nothing in EKF health notices a deweighted-and-floored lane:
  `hgtTestRatio` stays under 1 by construction and `status.flags.vert_pos`
  stays true. That is precisely the mechanism behind finding 6 below.

Ask: leave `R_OBS_DATA_CHECKS[5]` at the un-floored value so the gate and
the aliasing detector still see the real error, and/or bound the floor by
continuous engagement time. Do **not** gate the floor on `time_flying_ms ==
0` - log196 measured -1.2 m in exactly the post-liftoff regime that would
remove, so that obvious alternative is already dead.

**M4. `BaroGroundEffectAtTakeoff` measures `GLOBAL_POSITION_INT.relative_alt`.**
`peak_relative_alt_excursion()` reads it, and the final check uses
`get_altitude(relative=True)` from the same source.
`AP_AHRS::get_relative_position_D_home()` substitutes
`-AP::baro().get_altitude()` whenever `status.flags.vert_pos` is false. This
is the trap recorded in `Tools/autotest/CLAUDE.md` ("A green test is not
coverage", third Copter trap) **naming this PR**, and it is why
`BaroGroundEffectResetSuppression` was rewritten onto `LOCAL_POSITION_NED.z`.
Today the EKF stays healthy in this test so it does read the estimate
(UNCONFIRMED whether it could go unhealthy), but the phase-A assertion `if
peak < 0.3: raise` is **fail-open** under the fallback: reading the raw baro
gives ~3.6 m and passes whether the code works or not. Use
`self.ekf_position_D_m()`, the helper the sibling test already has.

### The two behaviour changes, as traced

The **innovation floor** is reachable whenever `takeoff_expected ||
touchdown_expected`, `activeHgtSource == BARO`, `!fusingGndEffectHgtRef` -
no armed check, no altitude check, no `assume_zero_sideslip()` check, so a
fixed-wing takeoff roll reaches it too. The error it can introduce is **not
bounded by the mechanism**: it caps each downward correction at `K*0.5 m`,
so an estimate that has run high recovers at a rate set only by `K` for as
long as the gate is latched. It is applied *after* the consistency test, so
it does not blind the gate - that part is fine.

The **observation deweighting** is new in this PR and gated additionally on
`is_negative(_baroGndEffectDeadZone)`. At DZ=-8 / ALT_M_NSE=2 that is R 16
-> 64 m^2, so the maximum recovery rate from a floored innovation falls ~4x.

**Flags set far from the ground remain fully reachable on this base:**
`AP_GroundEffect.cpp` forces `near_ground` true at any altitude once
horizontal drift from launch exceeds 20 m with no HAGL, so
`touchdown_expected` can latch in cruise (finding 6: 51 s at 17.9 m). The
anchor is defended against this; **the floor and the deweighting are not
defended at all**, and the deweighting is what turns a latched gate from a
nuisance into the 5.6 m measured. The PR should defend itself here rather
than rely on the vehicle gate.

**"Anchor ends at first throttle and can engage in mid-air" is still true of
this diff.** The gate is `dal.get_time_flying_ms() == 0`, unchanged by any
commit here. The 5 m guard does not prevent mid-air *engagement*; it
releases after engagement. Because `posDownGndEffectRef` is refreshed every
cycle while `!takeoff_expected`, a mid-air re-arm engages with an innovation
near zero, and because the anchor fuses at R=1 the filter is actively
dragged toward the reference - so the guard only trips for relative motion
faster than roughly 2-3 m/s (steady-state innovation ~ v/(K*f_baro), K~0.05
at R=1). That matches the one measurement here (release at innov 5.6 well
under a second into a free fall). A *slow* mid-air divergence is not caught.
Derived, UNCONFIRMED by test.

### Should-fix

- **Commit ordering ships the bug the last commit fixes.** `2371087c61`
  retro-fits `!assume_zero_sideslip()` onto `90a7b58f40` and `66e976c661`,
  so commits 1-4 are states in which a fixed-wing takeoff gets both the
  ResetHeight suppression and the held-height anchor - the failure commit 5
  exists to prevent - sitting in the middle of a bisect range that includes
  an autotest commit. Fold the gate into the two commits that first use the
  flags. That commit also carries an unrelated hunk (`!fusingGndEffectHgtRef`
  on the innovation floor) that belongs with `66e976c661`; its message's
  "Also skip..." is the tell.
- **The DZ=0 clamp fix is a separate upstream bug and is undisclosed.** With
  `gndMaxBaroErr = MAX(DZ, 0)` on master and DZ in [0, 0.5),
  `constrain_value` is called with `low=0.0, high=-0.5`; it returns `low`
  for `amt<0` and `high` otherwise, so any innovation below -0.5 m gets an
  extra -0.5 m added, at the value the parameter documents as "no ground
  effect". The fix is correct but is buried in the noise-floor commit while
  the body mentions only the `fabsF()` change. It is a behaviour change for
  existing DZ=0 users and is backportable on its own - split it out.
- **`!badIMUdata` in the suppression reduces to a constant on the target
  vehicles.** `badIMUdata` is assigned only inside `if (fuse_gps_vz &&
  fuseVelVertData && POSZ != GPS)`. Without GPS vertical velocity - the
  indoor flow/baro copters this PR exists for - it is permanently false, so
  the commit message's "do not reset to it unless the IMU is also bad" is
  protection that does not exist there. The EKF3 playbook has the review rule
  for exactly this. Say so in the message or drop the clause.
- **The suppression's own escape hatch cannot reach the baro while the
  anchor is active.** `ResetHeight()` resets to `-hgtMea`, and `hgtMea` is
  `-posDownGndEffectRef` when the anchor is on, so the `badIMUdata` path
  resets the height to the held reference - to itself. A code property;
  UNCONFIRMED as reachable, since the anchor keeps the innovation inside the
  gate by construction. Worth a comment rather than code.
- **`BaroGroundEffectResetSuppression` is calibrated within ~6% of not
  firing.** `SIM_BARO_GEFF_M=30` gives ~21.7 m of error against a gate of
  `5*sqrt(P+16)` ~ 20.3 m, and `XKF4.SH` settles at 1.06 as recorded here.
  Any drift in `ALT_M_NSE` defaults, `P[9][9]` or the SITL on-ground AGL
  flips it to a silent pass-by-timeout. Raise `SIM_BARO_GEFF_M` for real
  margin. It also runs at the **default** DZ=+4, so it never exercises the
  suppression in the negative-DZ configuration the PR is for - and per M3 it
  could not.
- **The parameter description still omits the measured hazard.** It
  documents the negative mode but never says a negative value assumes a
  rangefinder or other height/velocity anchor. Finding 2 measured -1.15 m of
  on-ground drift on a baro-only quad at that setting and estimates
  steady-state lag going ~1.0 m -> ~3.7 m on a 5-inch baro-only quad. Still
  open, as this record says.
- **PR body: template and house style.** The repo template is `### Summary` /
  `### Classification & Testing` / `### Description`; the body uses its own
  five headings and replaces the repo's checklist. Four bullets use the
  `**Bold headline.** explanation` pattern the playbook forbids, and the body
  contains em-dashes, a multiplication sign, an arrow and a tilde.

### Corrections and notes

- **Strike finding 1's parenthetical.** It says "the PR body says R =
  0.1*|DZ|; the code is `sq(MAX(0.1*|DZ|, 1.0))`". Both halves are now
  stale: the code is a flat `posDownObsNoise = sq(1.0f)` and the body says
  "at a fixed 1 m observation noise". Note the flat 1.0 also overrides a
  user's `EK3_ALT_M_NSE` in both directions - someone who set 0.5 gets a
  *weaker* observation during the anchor.
- `90a7b58f40` states a -4.3 m ground effect "caused a -3.65 m altitude jump
  at takeoff" via `hgtTimeout` -> `ResetHeight`. At any plausible
  `EK3_ALT_M_NSE` the ground-effect gate is 10-20 m wide, so a -4.3 m
  innovation should not time out - and this record says log190 (reset
  suppressed) still ramped -3.9 m, "so the reset was a contributor, not the
  cause". UNCONFIRMED, log189 was not available. Either supply the gate
  arithmetic or soften the sentence; a maintainer who does the arithmetic
  will ask.
- If `takeoff_expected` is false while `land_complete` is true, the
  reference is not refreshed, `hgtMea` equals the current state, the
  innovation is identically zero, `lastHgtPassTime_ms` is refreshed forever
  and `hgtTimeout` can never fire while the filter dead-reckons. A code
  property; no reachable Copter path was constructed (`AP_GroundEffect`
  re-stamps `takeoff_time_ms` while `!throttle_up && land_complete`, so
  `takeoff_expected` effectively latches with `land_complete` - except in
  THROW, where `touchdown_expected` needs `D_is_active()`, not set pre-throw).
  UNCONFIRMED. Cheap defence: refresh the reference on `!gndEffectExpected`.
- The anchor re-engages without hysteresis: once the 5 m guard drops it the
  reference is frozen by `takeoff_expected`, so if the state comes back
  within 5 m it re-engages against the same stale reference. No harm
  identified; one line of comment.
- `ResetHeight` is not the only path that snaps height to a ground-effect
  baro: the `AID_NONE` transition in `AP_NavEKF3_Control.cpp` does
  `meaHgtAtTakeOff = baroDataDelayed.hgt; stateStruct.position.z =
  -meaHgtAtTakeOff;`, overwriting the value deliberately frozen while
  `takeoff_expected`, with the raw contaminated baro. Reachable on an indoor
  flow copter that loses flow during spool-up. Pre-existing master
  behaviour, not introduced here, but adjacent enough that a reviewer may
  raise it against the PR's framing.
- Neither new behaviour is observable in a log - no bit for
  `fusingGndEffectHgtRef` or for the suppression window. Debugging both here
  needed instrumented builds and a non-shipped XKHD message. A bit in XKFS
  would cost nothing and would make finding-6-class problems visible in a
  customer log.
- Comment density on added EKF3 lines is 42.6% against 19.9% for
  `AP_NavEKF3_PosVelFusion.cpp` as a whole, and three 4-5 line blocks
  restate their commit messages. Trim to the non-obvious why.
- Test discrimination as it stands: `BaroGroundEffectResetSuppression` was
  A/B'd with the bound compiled out and fails, and `BaroGroundEffectAtTakeoff`
  discriminates the `resetHeightDatum` reference refresh and the anchor's
  release at liftoff. Nothing tests the noise floor commit, the clamp fix,
  the fly-forward gate, or the 5 m guard.
- **Owed evidence.** The Replay of log7 is still listed as owed and was not
  run. M3 is exactly what it would settle - how much of the 5.6 m in finding
  6 is the deweighting against the floor, on the flight's own sensor stream.
  Until then M3 is quantified from code arithmetic only.

## SITL check 2026-09-10: M4 is real but latent, not an active failure

Ran `BaroGroundEffectAtTakeoff` on the PR's own tree (head 263f181a18). It
passes: 0.990 m peak excursion with the default dead zone, 0.040 m armed at
idle in ground effect.

The question M4 turns on is whether `GLOBAL_POSITION_INT.relative_alt` is
reading the EKF estimate or the raw-baro fallback, which
`AP_AHRS::get_relative_position_D_home()` substitutes whenever
`status.flags.vert_pos` is false. From the run's own log, `XKF4` core 0:

| | |
|---|---|
| samples | 867 over 110 s |
| `vert_pos` false | 12 samples, t = 3.5 to 5.7 s |
| first arm | t = 43.7 s |
| `vert_pos` false after first arm | **0** |

So the flag drops only during EKF initialisation at boot and is true for the
whole of both measured phases. **The test currently measures what it claims
to measure**, and the earlier reading here - that it measures the wrong
signal - overstates it.

What survives is the fail-open shape, and it is still worth fixing. If a
regression ever did drive the EKF unhealthy - which is precisely the
ground-effect failure mode this PR exists to prevent - `relative_alt` would
silently become raw baro, and phase A's `if peak < 0.3: raise` would still
pass, because raw baro shows around 3.6 m of ground effect. The assertion
cannot fail in the direction it is guarding. Switching to
`self.ekf_position_D_m()`, which the sibling test already uses, costs
nothing and removes the trap. Downgrade M4 from must-fix to should-fix.

## Fix 2026-09-10 (head e6a198cf8b): the takeoff test now reads the EKF

`BaroGroundEffectAtTakeoff` reads `LOCAL_POSITION_NED` via a new
`peak_ekf_alt_excursion()`, as `BaroGroundEffectResetSuppression` already
did. The numbers barely move - 0.990 -> 0.991 m and 0.040 -> 0.027 m - which
is the point: the flag is only false during EKF startup, so this closes the
trap rather than fixing a wrong result, exactly as the SITL check above
predicted.

One thing the change turned up: `assert_baro_drift_cleared_at_arm()` is
called twice, and its second call runs the **no-GPS** arm reset, where the
reported height falling back to the recalibrated baro is the behaviour under
test and `LOCAL_POSITION_NED` is not published at all. A blanket switch to
the EKF signal broke it. Both helpers are kept, with the reason on each, and
only the two ground-effect call sites use the EKF one. `BaroDriftClearedAtArm`
and `BaroGroundEffectResetSuppression` both still pass.

Still outstanding and needing a rebase: the three unfolded fixups, which do
not squash mechanically (2 conflicts, 1 conflict, clean).

## Rebase 2026-09-10: 26 commits -> 22, head cba8f121ac, on current master

The three fixups are folded and `2371087c61`'s fly-forward gate is
dissolved into the two commits that first use the flags, so no
intermediate commit ships the fixed-wing failure that commit existed to
prevent. Its four hunks went where they belong: the `!assume_zero_sideslip`
on `baroInGndEffect` to the ResetHeight suppression, and the parameter-doc
qualifier, the `!fusingGndEffectHgtRef` innovation-floor skip and the
`!assume_zero_sideslip` on the anchor to the hold commit.

`f282f9df7a` turned out to straddle two commits, which is why it would not
autosquash: two hunks belong with the suppression, but the other three add
`gndEffectHgtResetSuppressStart_ms` beside `posDownGndEffectRef` and
`fusingGndEffectHgtRef`, both introduced by the *later* anchor commit. The
dependency is positional, not logical, so all five went into the
suppression commit at valid positions for that point in history and the
anchor commit's members land beside them afterwards.

Verification: `git diff 263f181a18 <restructured>` was **empty** before the
master rebase, so the split provably changed no content, and the same check
against the old head e6a198cf8b after adding the test commit was empty too.
Each of the three restructured EKF commits builds on its own. On master,
`BaroGroundEffectAtTakeoff` (0.980 / 0.029), `BaroGroundEffectResetSuppression`
and `BaroDriftClearedAtArm` all pass.

The three target commit messages now describe what their fixups added - the
suppression bound, the reference-innovation release, and the second test -
which was the other half of that finding.

## The problem

BF_X indoor quad (DPS310, EK3_RNG_USE_HGT -1): motor spool-up drops the
barometer 4-5 m. With the stock 4x scaler, log189 (not committed) stepped
-3.65 m at takeoff, the hgtTimeout ResetHeight snapping PD to the corrupt
baro. With ResetHeight suppressed (log190) PD still ramped -3.9 m, so the
reset was a contributor, not the cause. Other airframes: a 5-inch baro-only
quad -9 to -11 m spool-up spikes; a ducted quad 121 Pa (10 m) on a ground
throttle ramp at ThO 0.15 with the rangefinder at 0.04 m; a MatekH743 flow
quad -6.15 m at motor start.

## The conclusion and why

Three guards, each chosen after the obvious alternative was flown:

- Suppress ResetHeight while ground effect is expected. Riding on IMU
  integration for the window is accurate over seconds; snapping to a
  baro known to be metres wrong is not (log189).
- Negative EK3_GND_EFF_DZ as a noise floor. Per-fusion logging (log191,
  XKHD, not in the PR) showed PD 0.31 -> 3.06 m over about 11 baro
  samples with K growing 0.0005 -> 0.027 as P[9][9] grew: the 4x
  scaler (R 16 m^2 at EK3_ALT_M_NSE 2) is too weak. Every innovation in
  the window was positive, so the -0.5 m innovation floor was doing
  its job; the contamination was IMU drift integrating against a
  deweighted baro, not the baro pushing PD. R = |DZ|^2 (64 m^2 at -8)
  slows that.
- Pre-takeoff anchor. Baro-only with DZ -8 the spool-up (7.9 s, log196)
  still drifted -1.2 m from accel bias against R 64 and needed 75%
  throttle to leave the ground; fusing meaHgtAtTakeOff instead
  (log198) cut it to 0.13 m. That is the PR body's 1.2 -> 0.1 m.

Rejected:

- Innovation-variance capping in the GPS_GLITCH_RAD=0 style (log192):
  never activates; the noise floor makes the gate so wide the test
  ratio stays under 1.
- Capping Kfusion[9] directly (log193/194): PD still reached 5.9 and
  3.0 m, because the protected phase lasted four samples before the
  height source switched to baro above the RNG_USE_HGT threshold. That
  led to #33359 (AGL KF for the switch), not to a change here.
- A bi-directional +/-0.5 m innovation clamp at the normal R (log205):
  with EK3_RNG_USE_HGT > 0 the terrain offset diverged to 131 m and
  the altitude to -140 m; the vehicle fell with an unrecoverable EKF
  failsafe. terrainState = PD + rng feeds hgtMea = rng - terrainState,
  so per-sample PD motion of 0.02 m is amplified without bound; the
  floor's small K is what keeps that loop slow. Baro-only (log209) the
  clamp was also worse than the floor, -3.68 m against -1.65 m
  (log208): a constant K of 0.04 contaminates at 0.2 m/s where the
  floor's K averages 0.08 m/s.

## Key finding 1: the anchor ends at the takeoff command, not at liftoff

Anchor conditions: takeoff_expected || touchdown_expected, DZ < 0,
!assume_zero_sideslip(), time_flying_ms == 0. The last is zero exactly
while Copter's land_complete is true, and land_complete does not wait
for liftoff. Stabilize and Acro clear it as soon as the motors are
THROTTLE_UNLIMITED with throttle above the lower limit
(mode_stabilize.cpp), i.e. at the first real throttle. AltHold and
Loiter pilot takeoffs clear it in do_pilot_takeoff on throttle >=
min(TKOFF_THR_MAX, 0.9) or on EKF accel/velocity/altitude-change
thresholds, and with PILOT_TKOFF_ALT 0 (the indoor setting the
SmallFastDrone branches use) stop() clears it once throttle_in exceeds
hover/2. So the anchor covers the ground-idle interval and, in most
configurations, none of the spool-up; the spool-up gets the post-liftoff
floor, R = |DZ|^2, which is the regime log196 measured at -1.2 m.

Where the anchor does persist (AltHold with a takeoff altitude set) it
persists because it hides from the takeoff detector the motion the
detector waits for (log203: liftoff never detected with the anchor
on). The notes tried !takeOffDetected (true after 1 s from motor
vibration), !inFlight (baro-derived) and time_flying_ms and found each
circular; the PR picked the least bad. Open.

Flight timeline that shows it: ducted quad, log21 (not committed),
SmallFastDrone 4.7-beta4 with the equivalent code, third arm in Loiter,
EK3_GND_EFF_DZ -4 or -5 (the notes disagree; the anchor R is 1 m^2 either
way, see below):

| t (s) | EKF alt | CTUN.BAlt | RFND | |
|---|---|---|---|---|
| 120.18 | 0.03 | -0.21 | 0.16 | arm, reset fires |
| 120.20 | 0.00 | 0.00 | 0.16 | clean |
| 120.86 | ~-0.05 | rising | 0.17 | AUTO_ARMED, throttle up |
| 122.5 | -0.30 | -0.06 | 0.17 | on the ground |
| 123.18 | ~-0.36 | | 0.17 | vehicle-side window closes |
| 124.0 | -0.46 | -0.02 | 0.16 | |
| 125.0 | -0.52 | +0.02 | 0.17 | bottom |
| 130.0 | -0.25 | +0.49 | 0.42 | lifting off |
| 160.0 | 0.15 | 0.50 | 0.70 | -0.55 m vs rangefinder |

An earlier reading of this flight blamed the EKF chasing a corrupted baro
after the window closed. The table says otherwise: the compensated baro
sits within 0.1 m of zero from 122.5 to 125 s while the EKF walks away
from it, which is IMU drift against a deweighted baro (the log196
mechanism), and the recovery from 125 s is the baro regaining weight.
That build's window timer counts from land_complete clearing and expired
3.0 s after arm, so land_complete cleared at arm and the anchor never
ran; the spool-up had only the floor. The -0.85 m that persisted through
the hover is a different mechanism, see ../32553/.

Upstream vehicle side (#32472, same as master): the window timer is
anchored while !throttle_up && land_complete, with throttle_up =
has_manual_throttle() && throttle > 0 and a 5 s cap, so in Stabilize
the outer gate can also close 5 s after the first throttle. In ALT_HOLD
it never closes: has_manual_throttle() is false there, so throttle_up is
false whatever the stick does, the timer is re-anchored every cycle and
the 5 s cap never expires. That is why the ResetHeight suppression needed
a bound of its own; see review-response-2026-09-04.md.

BaroGroundEffectAtTakeoff arms in ALT_HOLD at idle with the stick
untouched, so land_complete stays true for the whole 8 s: it tests the
anchor against a glitch, not a takeoff, and it does not reach the
ResetHeight suppression at all - the held reference keeps the innovation
inside the gate. BaroGroundEffectResetSuppression was added for that
branch and its expiry.

The anchor noise: the PR body says R = 0.1*|DZ|; the code is
sq(MAX(0.1*|DZ|, 1.0)), which is 1 m^2 for every allowed DZ. The
0.64 m^2 in the flight notes does not match; either the SmallFastDrone
build lacked the floor of 1.0 or the note computed it from the formula.

## Key finding 2: where a negative dead zone is right, and where it is wrong

The parameter conflates two knobs and the sign selects which:

| `EK3_GND_EFF_DZ` | innovation dead zone | baro R in ground effect       |
|------------------|----------------------|-------------------------------|
| +4               | -0.5 to -4.0 m       | `ALT_M_NSE^2 * 4` = 16 m^2    |
| +10              | -0.5 to -10.0 m      | 16 m^2 (unchanged)            |
| -8               | -0.5 to -8.0 m       | `max(8,1)^2` = 64 m^2         |

The 4x scaler is hard-coded and independent of the parameter; the dead
zone uses `fabsF()` either sign. So a negative value gives a wider dead
zone and 4x more deweighting at once.

That is right when a rangefinder anchors the height (the BF_X flights
behind this PR, where the floor was what kept the terrain-offset feedback
loop stable). It is wrong on a baro-only vehicle, where the baro is the
only observation and deweighting it to R = 64 leaves the vertical channel
on IMU integration: flown on a baro-only quad, log51 (not committed), the
EKF drifted to -1.15 m while the vehicle sat on the ground. On the 5-inch
baro-only quad (height time constant ~6 s measured from the innovation
ramp) the same value would take the steady-state lag at 0.16 m/s from
~1.0 m to ~3.7 m. Positive values scale the dead zone only, which costs
nothing: the logged post-clamp innovation of -7.63 m at spool-up inverts
exactly to a raw -11.13 m, which at +10 would present as -1.63 m. Not a
cure either; the EKF moved 0.05-0.09 m across that spike, and the 1.3 m of
lag accrued in the climb that followed.

The parameter description should say "negative values assume a
rangefinder (or another height or velocity anchor) is fused"; the -8
example as written will be copied onto baro-only airframes.

## Key finding 3: what the floor costs on the other side

- 5-inch baro-only quad, log38 phase 2 (not committed): a rangefinder
  dropout on a touchdown put +3.6 m into the estimate through a mechanism
  that is SmallFastDrone-only (fixed there); the ground-effect innovation
  floor then held XKF3.IPD at exactly -0.5000 through the re-takeoff, so
  the baro could not correct it. The PR keeps the floor except while the
  anchor is active.
- Same quad, log41 seg1 (positive DZ 4, so the 4x scaler): a real 3.26 m
  climb inside the 5 s window (RFND 0.34 -> 3.60, the baro tracked it)
  moved PD 0.75 m, then a 2.6 m step at the timeout. With
  |DZ| > 2*ALT_M_NSE the negative-DZ floor deweights the baro more
  than the scaler, so a real climb inside the window tracks worse as
  |DZ| grows. That flight was also fusing a synthetic zero velocity
  through the window (SmallFastDrone bug, fixed there; master never had
  the term), so it is not a clean measurement. Inconclusive; the trade
  is real.

## Key finding 6: the floor blocks a correction in cruise when the gate latches for a reason unrelated to ground effect (log7, 2026-09-09)

Finding 3 records the floor holding `XKF3.IPD` at exactly -0.5000 through
a re-takeoff on a 5-inch baro-only quad, so the baro could not correct a
+3.6 m error. This is a second real-flight instance of the same
mechanism, in level cruise, and it isolates the cost cleanly because the
flight ran two source configurations on one airframe at once.

SFD-O4, a SmallFastDronev1 BF_X quad on 4.7.1 (`797f6854`), flown with
`EK3_SRC_OPTIONS=8` (SRC_PER_CORE): core 0 on SRC1 (GPS, POSZ baro,
VELZ GPS) and core 1 on SRC2 (flow, POSZ baro, **VELZ None**). Same IMU,
same baro, same rangefinder, same instant. `EK3_GND_EFF_DZ=-8`,
`EK3_ALT_M_NSE=1.0`, `GNDEFF_ALT=0.5`.

In a stationary hover at 17.9 m above the takeoff altitude,
`touchdown_expected` was set for **51 s continuously** (116.73-167.73 s;
20.8% of the whole armed flight). Over that window:

| | core 0 (GPS) | core 1 (flow) |
|---|---|---|
| altitude 121 s -> 160 s | 17.63 -> 17.63 m | 18.06 -> **23.27 m** |
| `XKF3.IPD` | -0.4 to +0.2, moving | **-0.500, pinned** |
| baro over the window | flat, 17.55-18.12 m | same baro |

5.6 m of runaway in 38 s against a flat barometer that was the lane's own
height source. Core 0 never engaged the floor because GPS velZ held its
altitude, so its innovation never reached -0.5. Core 1 had nothing else:
`gndEffectExpected` deweighted its only height observation to
`sq(8) = 64 m^2` (PosVelFusion.cpp:1724) and floored its innovation at
-0.5 m (line 1296) at the same time.

**The vehicle side of this is fixed, the EKF side is not measured
(2026-09-10).** Why the gate was open at all is
`../34362/` - a descent test with no deadband
and a drift rule that asserts ground proximity when it means "I do not
know" - and why `get_hagl()` returned nothing to stop it is
[#34361](https://github.com/ArduPilot/ardupilot/pull/34361). Both are
written, with SITL showing the gate no longer opens in that hover.

What this finding still owes is its own half: a Replay of log7 through the
fixed EKF showing `XKF3.IPD` on the flow lane is no longer pinned and the
5.6 m does not accrue. That has not been run. Until it is, the floor's
behaviour in cruise is described here but not demonstrated fixed, and
nothing above should be read as saying the EKF-side response was changed -
it was not.

The trigger is on the vehicle side, in #32472, and its archive entry
already anticipated this class of failure - see the note added there. In
short: the rangefinder was out of range high for 101 s continuous, the
AGL KF went invalid, `ahrs.get_hagl()` returned false, `AP_GroundEffect`
fell back to its position branch, and 21.8 m of horizontal drift past
`AP_GROUNDEFFECT_TAKEOFF_DRIFT_NE_MAX_M` = 20 m forces `near_ground`
true at any height.

What this does and does not argue:

- It does **not** argue the floor is wrong. Everything in "The conclusion
  and why" stands: log192, log193/194 and log205 each killed an
  alternative, and log205 in particular shows a bi-directional clamp
  driving the terrain offset to 131 m. The floor's asymmetry is what
  keeps that loop slow.
- It **does** argue that the floor's safety rests entirely on the gate
  being right, and that the gate can be wrong by a wide margin without
  anything in the EKF noticing. A vehicle with a second vertical
  observation absorbs that; a flow-only vehicle, which is the
  configuration this feature set exists for, does not.
- Options, none tested: bound the floor's engagement by how long it has
  been continuously active with a same-signed innovation; or require the
  gate's `near_ground` to rest on an actual height rather than a drift
  fallback (the #32472 side, and the cheaper fix); or exempt a lane with
  no other vertical observation. The first two are preferable because
  they do not add per-lane behaviour.
- **log7 carries `LOG_REPLAY=1`.** Any of these can be run against the
  flight's own sensor stream, which is tier 1b, rather than argued.

Full flight note in the private analysis repo (`logs/log7_sfdo4.md`).
Public-facing text should cite this as "flight tests show the
ground-effect innovation floor can pin the height innovation at -0.5 m in
cruise when the gate latches on a horizontal-drift fallback, costing 5.6 m
on a lane with no vertical velocity source" and give no more.


## Also measured

- The whole protection set off vs on: ducted quad log22 vs log21
  (TKOFF_GNDEFF_TMO 0 vs 3): post-compensation BARO.Alt std 39 ->
  92 cm, alt-error std 11 -> 17 cm, a new 0.10 Hz oscillation the
  vehicle physically followed (84 cm rangefinder swing), two yaw resets
  within 5 s of arm vs none. Confounded with BARO_THST_FILT 1.0 -> 0.1
  in the same flight.
- With a rangefinder height source and the AGL-KF switch (#33359), PD
  stayed within +/-0.05 m through takeoff (log195). That, not this PR,
  is the fix for rangefinder vehicles; this PR is for baro-only.

## What is here

```
32972/
  README.md                        <- this file
  review-response-2026-09-04.md    rebase, the 2026-09-03 review, findings 4 and 5
  plots/
    ab_ground_effect_takeoff.png   A: baseline DZ 4 vs this PR at DZ -5
    ab_reset_suppression_bound.png B: baseline vs unbounded vs bounded suppression
    make_plots.py                  regenerates both from data/ab-2026-09-04/
  data/ab-2026-09-04/
    A1_base_dz4.BIN                baseline binary (1c88a3bf62), DZ 4, GEFF 5
    A2_branch_dzm5.BIN             branch binary, DZ -5, GEFF 5
    B1_base.BIN                    baseline binary, GEFF 30
    B2_nobound.BIN                 branch with the suppression bound compiled out
    B3_branch.BIN                  branch as merged, GEFF 30
    harness.py                     the throwaway autotest methods used
```

All SITL (CMAC home), no real-flight logs. The flight-derived numbers in
the sections above are from logs that are not committed.

## Reproduce

```
git checkout pr-baro-gnd-effect
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.BaroGroundEffectAtTakeoff
Tools/autotest/autotest.py --no-configure test.Copter.BaroGroundEffectResetSuppression
```

Measure the EKF height with XKF1.PD in the log, or LOCAL_POSITION_NED.z
live. Never GLOBAL_POSITION_INT.relative_alt: AP_AHRS falls back to the
raw baro whenever the EKF vertical position is unhealthy, which is the
state these tests create, so it reports the barometer and any assertion
on it passes whether the code works or not (finding 4).

The takeoff-command gap has no test yet. To build one: Stabilize,
EK3_GND_EFF_DZ -5, EK3_RNG_USE_HGT -1, arm, raise throttle to about
half hover and hold 8 s (land_complete clears at the first throttle, so
the anchor is off), with SIM_BARO_GLITCH -5 or, with #32472,
SIM_BARO_GEFF_M (applies whenever throttle > 0, decays to zero at 2 m
AGL); watch XKF1.PD. The terrain-loop failures (log205) need a SITL
rangefinder with EK3_RNG_USE_HGT > 0 and the same injection. A baro-only
variant (RNGFND1_TYPE=0) with a -8 floor should reproduce the on-ground
drift of finding 2.

## Branches and people

- `pr-baro-gnd-effect` - the PR branch, at 263f181a18 (2026-09-04),
  local and origin in sync, based on 1c88a3bf62 (#32768 head).
  Pre-rebase backups: pr-baro-gnd-effect-backup-prerebase (3980009868)
  and pr-baro-gnd-effect-backup-20260904 (pre-fixup, 0e2cb01baf).
- SmallFastDrone-4.7-beta equivalents: c31449d865 (ResetHeight),
  8809637be5 (noise floor), 721f9986a7 (anchor); 873a262140 is the
  variant flown on the ducted quad.
- Related: #32472 (vehicle-side window, where the outer gate is
  decided), #32553 (terrain reset, the log200-206 series), #33359 (AGL
  KF switch, log195), the AGL KF #32389.
- Automated review 2026-09-03 (AIReview label, external dev-call batch,
  not GitHub Actions): four points, all answered, two of them belonging
  to #32768 rather than here. See review-response-2026-09-04.md.
