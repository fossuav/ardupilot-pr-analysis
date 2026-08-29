# PR #32270 - VALT velocity alt-hold flight mode

Analysis archive for [ArduPilot/ardupilot#32270](https://github.com/ArduPilot/ardupilot/pull/32270).
Branch `copter-valt-mode` (andyp1per fork), base `master`. No logs are
committed here; the validation is the `ModeVAltHold` autotest and real flights
that stay private.

## Status (one line)

Rebased onto master on 2026-08-29 (941 commits behind before) and extended with
three commits: ground idle at mid-stick, its autotest, and a position
correction limit in ground effect. Autotest passes. A maintainer's objection to
the mode's existence stands unanswered by design; the PR is kept current as a
record of the SmallFastDrone branch rather than argued.

## What the mode is

The pilot stick commands climb/descent rate instead of driving a jerk-limited
position trajectory. VALT inherits from AltHold and overrides only the flying
state: off-centre, pos_desired snaps to the estimate (velocity control); at
centre it freezes with zero initial position error and the position loop holds.
Any baro offset accumulated during a manoeuvre cancels instead of feeding a
trajectory, which is the point on small, high disc-loading copters with heavy
baro ground effect. `VALT_POS_EXPO` (default 0, inert) blends position
authority back in with stick deflection so a stuck velocity loop has a backstop
at full deflection.

## The three additions

1. **Ground idle at mid-stick.** Mid-stick is VALT's resting hold state, but the
   shared AltHold ground state machine spools the motors up at any stick at or
   above mid while a take-off only triggers on a positive climb rate. Parked at
   mid-stick the vehicle sat spooled-but-not-taking-off with `land_complete`
   true; angle boost while the airframe was handled pushed `throttle_out` past
   hover/2 and the land detector's missing-take-off guard latched a
   `flow_of_control` internal error that blocked arming until power cycle. A
   `Mode::spool_up_at_zero_climb_on_ground()` virtual (default true) lets VALT
   stay in ground idle until a climb is commanded; every other mode is
   byte-identical. Side effects, stated in the message: take-off from mid-stick
   waits for the spool-up, and a parked VALT vehicle auto-disarms after
   `DISARM_DELAY` where AltHold would not.
2. **Autotest** for the ground phase: motor output at mid-stick must sit below
   AltHold's at the same stick (the discriminating observable), the vehicle
   stays landed, and a climb command lifts off.
3. **Position correction limit in ground effect.** Rotor wash steps the baro by
   metres at ground contact; one measured case stepped 2.4 m and the position P
   loop turned it into a 2.4 m/s climb demand off the deck. While the baro
   ground-effect flags are set the vertical position correction is limited to
   0.1 m/s (AC_P_1D turns that into an error limit, so small errors are still
   corrected at full gain and a large one saturates). Measured drift with no
   position authority at all is 0.03-0.05 m/s. Dropping authority outright was
   tried first and left nothing to arrest drift (0.5-1.0 m per 20 s hands-off).
   The limit follows the ground-effect flags, which also expect a touchdown in
   any slow demanded descent, so it is in force through a gentle descent at
   height as well.

## What the rebase fixed

- `MODE_VALT_ENABLED` now depends on `MODE_ALTHOLD_ENABLED` (master made AltHold
  optional after the PR was opened): `#error` in Copter.h and a build_options
  dependency, otherwise the build-options CI links VALT without its base class.
- `extract_features.py` could not detect the feature (no `ModeVelAltHold::init`);
  an explicit entry was added.
- VALT was missing from both AVAILABLE_MODES lists and the `FLTMODE1` values.
- The autotest was ported off the removed `watch_altitude_maintained()` helper
  and `delay_sim_time()` now requires a reason.
- The ground-effect commit message said 0.3 m/s where the flown and committed
  value is 0.1 m/s.

Still needed: a companion mavlink PR adding `COPTER_MODE_VALT = 29`; the pinned
pymavlink still names mode 29 `RATE_ACRO`, which is what MAVProxy prints.

## What is here

```
32270/
  README.md          <- this file
```

## Reproduce

```
git checkout copter-valt-mode
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.ModeVAltHold
```

## Branches and people

- `copter-valt-mode` - the PR branch, force-pushed 2026-08-29 (previous head
  558a9a9e1a).
- Reviewers: @peterbarker (avoidance calls in the VALT flying state, addressed
  in code), @lthall (does not see the justification for the mode; not argued).
