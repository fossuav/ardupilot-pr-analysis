# PR #32270 - self-review, 2026-09-04

Review of `copter-valt-mode` at 973cf77117 against merge-base ff37fde6f1,
followed by the fixes. Four parallel reviewers over the diff (per-commit slices
plus a whole-diff dev-call pass) and four independent Codex cold passes, one of
which died on a usage limit. The mechanical CI gate was clean before and after.

Nothing was posted to GitHub. The PR body and commit messages are unchanged;
only code was fixed.

## The review's first verdict was wrong, and that is the part worth keeping

The headline finding was "the mode is not justified - everything VALT does is
`SURFTRAK_MODE=0` plus `PSC_D_POS_P=0`, so it does not earn a mode number." Two
reviewers reached it independently and it agreed with @lthall's standing
objection, which made it feel settled.

It is wrong, and reading `../analysis/topics/althold_velocity_control.md`
settles it in one paragraph. `PSC_D_POS_P=0` kills the position loop at *every*
stick position including centre, which destroys the hold. VALT keeps full
position authority at centre and removes it only off-centre; that combination
is the mode, and no parameter produces it. The justification is measured, not
asserted: 0.095 m hold std against 0.27 m of baro noise on a baro-only quad,
and later 13 cm true std over 36 s hands-off.

Two more findings dissolved the same way:

- The `spool_up_at_zero_climb_on_ground()` rationale was filed UNCONFIRMED
  because no reviewer could construct a path to the land-detector guard -
  `Landed_Pre_Takeoff` relaxes the vertical controller every loop. The path is
  the *attitude* controller's angle boost, which keeps running: airframe
  hand-pitched to -54 deg, cos 0.59 giving ~1.7x, two motors saturating to hold
  attitude. Logged, with the latch and three refused re-arms.
- Calling `D_set_correction_speed_accel_m()` at loop rate was filed against the
  API's own "should only be called during initialization" comment. The `else`
  branch is required: `ModeAltHold::run()` refreshes only the trajectory limits,
  so without it the clamp persists after leaving ground effect.

The lesson is procedural. The review read the diff, the thread and the
playbooks, and never read the evidence repo. Three of its four headline
findings were about mechanisms already documented there. `../analysis/topics/`
is now the first stop.

## What the review got right

Four findings survived contact with the evidence, and one of them is new.

### The avoidance call was still missing

@peterbarker asked for it on 2026-02-23 and again on 2026-03-18
("The calls to the avoidance code in the new valt methods"). This repo's own
README recorded it as "addressed in code". It was not:
`ModeAltHold::alt_hold_run_flying()` makes three calls and
`ModeVelAltHold::alt_hold_run_flying()` made one. The missing one is
`copter.avoid.adjust_roll_pitch_rad()` - proximity lean-angle limiting, absent
in VALT on boards that set `AC_AVOID_ALTHOLD`. The tell was in the signature:
both `float&` roll/pitch parameters were unused in the override.

### The snap left a terrain offset in the error it assumes is zero

VALT's whole premise is "pos_desired freezes at exactly where the EKF says the
vehicle is - zero initial error by construction". But

```
_pos_target_ned_m.z = _pos_desired_ned_m.z + _pos_offset_ned_m.z + _pos_terrain_d_m
```

so snapping `pos_desired` to the estimate leaves the error at
`offset + terrain`, not zero. The offset self-heals through the timeout in
`D_update_offsets()`. The terrain term does not: its only reset lives *inside*
`update_surface_offset()`, which VALT never calls, and `ModeAltHold::init()`
skips `D_init_controller()` when the D controller is already active. Enter VALT
from any mode that had surface tracking running and the defining property is
quietly false for the whole flight.

Iteration 2 of the original development (`althold_velocity_control.md`) decided
to skip `update_surface_offset()` entirely. That suppresses *new* offsets; it
never considered one inherited at mode entry.

Fixed with a `ModeVelAltHold::init()` that calls `init_pos_terrain_D_m(0)`,
which is what surface tracking itself does when it stands down, and is bumpless
(it compensates `_pos_desired` by the same amount). This also closes a second
symptom: `deflection` was normalised against the raw `get_pilot_speed_up_ms()`
while the rate it came from was generated against the surface-tracking-adjusted
value, so with a stale terrain velocity full stick never reached deflection 1.

### VALT_POS_EXPO at or below 1 is not a valley

`w_pos = (1-d)^expo + d^expo` clamped to [0,1]. At `expo == 1` that is exactly 1
for every deflection; below 1 it exceeds 1 everywhere and clamps to 1. So any
value in (0, 1] gives full position authority at every stick position - VALT
degenerates to AltHold without surface tracking - and with `@Increment: 0.5` the
first two non-zero stops a GCS slider offers are precisely the inert ones.

The notes describe this end of the range as "toward 1 = more position authority
everywhere", which is directionally right and understates it: at 1 it is total.
The code is doing what the maths says; the parameter documentation was the thing
that was wrong, so that is what was fixed.

### New: the ground-effect detector does not know about VALT

`ArduCopter/baro_ground_effect.cpp` special-cases `Mode::Number::ALT_HOLD` to
stand a near-level attitude target in for "pilot is asking for slow horizontal",
because AltHold has manual attitude and no NE controller. VALT is AltHold with
manual attitude and no NE controller, and was not in the test. So
`_pilot_slow_horizontal` was always false in VALT and `slow_horizontal` fell
back to actual NED speed alone - a strictly weaker touchdown detector than
AltHold's, in exactly the regime the ground-effect correction limit exists for.
One-line fix.

## Fixes applied

| Fix | Files |
|---|---|
| Restore `copter.avoid.adjust_roll_pitch_rad()` in the VALT flying state | `mode_valt.cpp` |
| Clear an inherited terrain offset at VALT entry | `mode_valt.cpp`, `mode.h` |
| Take stick deflection from the pilot demand, before avoidance clips it | `mode_valt.cpp` |
| `!is_positive(expo)` so a NaN parameter cannot reach `powf`/`constrain_float` | `mode_valt.cpp` |
| `VALT_POS_EXPO` description states the <=1 behaviour; index 29 -> 25 (next free) | `Parameters.cpp` |
| VALT included in the ground-effect slow-horizontal proxy | `baro_ground_effect.cpp` |
| `FLTMODE_GCSBLOCK` bitmask docs gain `24:VALT` | `AP_Vehicle.cpp` |
| `MODE_VALT_ENABLED` whitelisted for non-copter enable-in-turn builds | `test_build_options.py` |
| `MODE_VALT_ENABLED 0` in the minimised-feature builds | `minimize_common.inc` |
| Comment density cut to the surrounding files' level | `mode_valt.cpp`, `mode.h`, `mode_althold.cpp` |
| Autotest: real assertion for the blend, event waits, workable timing margins | `arducopter.py` |

Not fixed: `mode_valt.cpp` has no licence header. 0 of 29 `ArduCopter/mode_*.cpp`
carry one, so adding it here would make this the odd file out. The mechanical
gate flags it; it is being left deliberately.

## The autotest, and one test that had to be thrown away

The blend now has an assertion that can fail. `VALT_POS_EXPO`'s observable is
that at full deflection `pos_desired` is left marching instead of snapped, so
`|DPD - PD|` from `PSCD` separates the two paths. Held full-down for 5 s at each
setting, measured from the onboard log:

| `VALT_POS_EXPO` | mean \|DPD - PD\| |
|---|---|
| 0 (hard cutoff) | **0.0000 m** |
| 3 (blend) | **0.0396 - 0.0443 m** across four runs |

Total separation, so the gates are set at 0.005 and 0.02. This is the SITL
counterpart of the flown log77 result (DPD 0.15-0.24 m below PD at full down).

The ground-effect correction limit **still has no coverage**, and two attempts
to give it some were discarded rather than shipped:

1. Inject `SIM_BARO_GLITCH = -8` during an open ground-effect window and assert
   the vehicle does not climb. With the limit compiled out the test still
   passed (true altitude 599.62 -> 598.22): the commanded descent's feedforward
   dominates the gross motion, so the outcome does not discriminate.
2. Assert instead on the quantity the limit actually bounds, the position error
   while the window is open. With `VALT_POS_EXPO=0` this reads exactly 0.0000 m
   either way - the snap zeroes the error itself, so there is nothing to bound.
   With the blend on it reads 0.0036 m with the limit and 0.0055 m without,
   both an order of magnitude under the 0.1 m leash.

The reason is the same in both cases: the limit only bites once the height
*estimate* has stepped further than the leash, and SITL's EKF gates a raw baro
glitch long before that. The real failure was a genuine 2.4-3.8 m estimate
excursion from rotor wash. Reproducing it needs `SIM_BARO_GEFF_M`, which lives
on `pr-ground-effect`, not on this tree. The subtest was kept as an exercise of
the path with the discriminating assertion removed and the gap written into the
test as a comment, so the next reader does not re-derive it.

## How the fixes were landed

Squashed back into the commits that introduced them rather than left as a
trailing "address review comments" commit, so the series still reads as one
change per commit. Old head 973cf77117, new head d6d572ad43; the content diff
between the two is exactly the nine files above.

| Fix | Commit it went into |
|---|---|
| avoidance call, terrain reset at entry, comment trims | `Copter: add VALT velocity alt-hold flight mode` |
| deflection source, `!is_positive`, parameter index and description | `Copter: blend VALT position authority with stick deflection` |
| `spool_up_at_zero_climb_on_ground()` comment | `Copter: VALT holds ground idle at mid-stick on the ground` |
| ground-effect slow-horizontal proxy | `Copter: bound VALT position correction in ground effect` |
| the whole autotest rework | `autotest: cover VALT take-off from the ground` |

The autotest changes could not be split across the three autotest commits that
build the test incrementally - the rework replaces the function wholesale - so
they went into the last of them. The three fixes that touch other modules could
not go into any existing commit under the one-module-per-commit rule and are new
commits at the end: `AP_Vehicle:`, `autotest:` (the build-options whitelist) and
`hwdef:`.

Every one of the twelve commits was built individually; all compile.

## Verification

- `./waf copter` clean.
- `test.Copter.ModeVAltHold` passes; `ModeAltHold` and
  `GroundEffectCompensation_takeOffExpected` pass alongside it, covering the
  shared `get_alt_hold_state_D_ms()` and `baro_ground_effect.cpp` edits.
- Mechanical gate clean apart from the licence header noted above.
- Revert checks run for the ground-effect assertions (both discarded, above).
  The blend assertion fails by construction when the blend is removed, since
  the snap drives `|DPD - PD|` to zero.

An early `ModeVAltHold` failure during this session ("No such mode 29") was an
artifact: a Codex agent's `MODE_ALTHOLD_ENABLED=0` experiment left a 936-byte
empty `mode_valt.cpp.o` in the build tree. It is not a defect and nothing was
changed for it.

## Still open after this round

- **Mode number 29 is contested.** `pr-mode-rate-acro` assigns it to
  `RATE_ACRO`, and the pinned pymavlink already carries `29 : 'RATE_ACRO'`
  (`mavutil.py:2449`, also in installed 2.4.49). `COPTER_MODE` in
  `ardupilotmega.xml` stops at 28 with no `COPTER_MODE_VALT`. The PR body
  discloses this; what is missing is the decision and a linked mavlink PR.
- **The PR's own A/B does not say what the PR says.** The ground-effect section
  offers "hands-off holds wandered 0.5-1.0 m per 20 s" as the reason to prefer
  the clamp over the snap. Duration-matched (mean 5.3 vs 5.5 s segments), the
  snap drifted **0.663 +/- 0.158 m** and the clamp **0.851 +/- 0.212 m**, and
  the conclusion in `valt_gndeff_position_clamp.md` is "no detectable difference
  in hold quality". The defensible arguments are log62's unprompted settle onto
  the floor and the event rates (0.76 vs 3.01 throttle collapses/min, 0.31 vs
  2.07 jolts/min). The claim as written will not survive a reviewer who reads
  the A/B.
- **Three known limitations are absent from the PR body**: the clamp protects
  nothing once the estimate error reaches 2-4 m; log83 measured net +0.109 m/s
  upward drift at mid-stick with it engaged 100% and railed 34%; and the on-deck
  throttle surge is a regression against the snap, with the land detector never
  latching.
- **The A/B confound is not stated**: eleven commits landed between the arms,
  two of them ICP201XX baro-driver changes, and the gate fired on 8-94% of
  samples until `BARO1_THST_SCALE` was corrected.
- **The justification in the PR body has no numbers.** @lthall's objection is
  answerable from `althold_velocity_control.md` - baro std 3.7 m in descent,
  worst jump 15.28 m in 0.1 s, ground effect to -11 m, against a 0.095 m hold -
  and the "Why a separate mode instead of an AltHold option?" section currently
  asserts robustness without citing any of it. This is the highest-value edit
  left and it is a prose edit, deferred with the rest.
- A VALT-entry consistency gate (baro or rangefinder against EKF altitude at
  mode entry) is still unimplemented; `ekf_alt_ok()` lets VALT engage on an
  estimate diverged 5x.

## Reproduce

```
git checkout copter-valt-mode
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.ModeVAltHold,ModeAltHold
```

The blend measurement is printed by the test itself
("VALT_POS_EXPO=N mean |DPD-PD| = ... m").
