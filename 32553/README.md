# PR #32553 - Reset terrain offset from baro when ground effect clears (EKF3)

Analysis archive for [ArduPilot/ardupilot#32553](https://github.com/ArduPilot/ardupilot/pull/32553).
Branch `pr-terrain-reset-ge`, base master. No logs committed; numbers
are from a BF_X indoor quad (SmallFastDronev1 board, Mar 2026), cited
inline.

## Status (one line)

Two commits, no autotest; the 1.88 -> 0.3 m result in the PR body is
real but was obtained with the Copter-side HAGL release check (now in
#32472) also in place, the reset alone was measured to drift back, and
the current snapshot form of the reset has not been flown. On the same
vehicle the AGL-KF stack (#33359 + #33507) later achieved the target
without a reset, so the PR may be superseded.

## The problem

EK3_RNG_USE_HGT > 0: terrainState is seeded from PD + rng during
ground effect, PD is baro-contaminated, and the rangefinder height
observation hgtMea = rng - terrainState then reinforces the wrong PD.
log200 (not committed): hover with baro and rangefinder both reading
~0.96 m, EKF altitude -0.78 m, terrainState mean 1.88 m; the AGL KF
(HAgl) read 0.85 m throughout. The loop's strength: log205, a +/-0.5 m
innovation clamp at the normal K let per-sample PD motion of 0.02 m grow
the terrain offset to 131 m and the altitude to -140 m; the vehicle fell.

## The conclusion and why

Reset terrainState from baro plus rangefinder when the ground-effect
flags clear. Forms flown:

| log | baro used | offset at reset | later |
|---|---|---|---|
| 202 | offset-corrected (baroHgt - baroHgtOffset) | -0.61 m | - |
| 203 | raw baroDataDelayed.hgt | -0.19 m | -1.08 m after 25 s |
| 206 | raw, with the HAGL release check (becb063a13) | 0.3 m | stable |

The offset-corrected form is wrong because baroHgtOffset tracks the
contaminated PD through calcFiltBaroOffset. The PR now uses the raw
baro minus a baroHgtOffset snapshot taken at ground-effect entry, a
third form that maps raw baro into the NED-D frame; it has not been
flown. The second commit gates the reset on baro being the active
height source.

## Key finding: the reset needs the release check to fire, and is one-shot

- log204: with the release check on EKF altitude, ground effect never
  stayed clear (re-armed after every 5 s timeout), so this reset never
  fired. The 0.3 m figure comes from log206, after the HAGL check. A
  reviewer reading "1.88 -> 0.3 m" should know the PR is not
  sufficient on its own for that; #32472 is.
- log203: -0.19 m at the reset, -1.08 m 25 s later. The loop resumes
  as soon as normal terrain estimation continues. "Normal terrain
  offset estimation continues afterwards" in the body understates it.
- The obvious alternative, seeding terrainState from aglKfH (right at
  0.85 m while terrainState was 1.88 m), was not tried. #33359 uses
  aglKfH for the source switch, not for the terrain state. Worth an
  answer in the body.
- Possibly the same signature elsewhere: a ducted quad, log21 (not
  committed), EK3_RNG_USE_HGT 10, ends a 2 min hover 0.85 m below a
  healthy rangefinder after a spool-up in which PD drifted -0.5 m on
  the ground. The XKF5 terrain offset was not examined; hypothesis.

## Relation to the AGL-KF stack

The same vehicle later flew #33359 with `EK3_RNG_USE_HGT=3` (logs
283/285/286, not committed): `XKF5.TOfs` bounded -0.13 to +0.56 m
against +4.1 m in the original crash, AGL KF valid throughout,
`HAglStd` ~0.11 m and flat from 0.2 to 3.8 m, and at a 2.2 m hold the
baro read 0.4 m low while `TOfs` held ~0.2 m. The baro-to-terrain
coupling this PR resets is broken at the switch instead. Caveat: the
baro error exercised there was ~0.4 m, not the ~4 m of the crash case.
If this PR stays open, its description should say why it is still
needed once #33359 lands.

## What is here

```
32553/
  README.md    <- this file
```

No logs committed.

## Reproduce

No SITL reproduction exists. With #32472's SIM_BARO_GEFF_M, a SITL
rangefinder and EK3_RNG_USE_HGT > 0, take off in AltHold and compare
the XKF5 terrain offset against flat-ground truth (it should return to
the on-ground value); the PR body lists an autotest as outstanding.

## Branches and people

- `pr-terrain-reset-ge` - the PR branch (local matches GitHub head
  9031a31bba).
- SmallFastDrone-4.7-beta 6cfd575a1a (the flown form).
- Depends in practice on #32472 (release check); pairs with #33359.
- Review: rmackay9 asked for logs and repro steps; rishabsingh3003
  requested changes.
