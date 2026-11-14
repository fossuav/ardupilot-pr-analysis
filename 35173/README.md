# PR #35173 - keep -fno-math-errno through the EKF O2 pragmas

Analysis archive for [ArduPilot/ardupilot#35173](https://github.com/ArduPilot/ardupilot/pull/35173).

Opened 2026-11-14 at `fde5fe5a87`, branch `pr-ekf-o2-math-errno`, three
commits on master `699f00dfcd`:

- `da042b1ecc` AP_NavEKF3: keep -fno-math-errno through the O2 pragma
- `d965cb76e1` AP_NavEKF2: keep -fno-math-errno through the O2 pragma
- `fde5fe5a87` AP_NavEKF: keep -fno-math-errno through the GSF O2 pragma

From the SFD 4.7.2 beta's `27371d37cf` (EKF3) and `f7ff8539ae` (GSF),
which use an if/else form of the pragma and have no EKF2 commit.

## What it does

ChibiOS builds with `-fno-math-errno`. On GCC 10 a
`#pragma GCC optimize("O2")` drops that flag, and GCC 10 will not
inline a helper defined before the pragma (`sq()`, `MIN()`, `MAX()`,
`is_positive()`, `AP_ParamT` conversions) into a function after it
("optimization level attribute mismatch"). Each EKF header now follows
its O2 pragma with `#pragma GCC optimize("no-math-errno")` under
`#ifdef __NO_MATH_ERRNO__`, so builds without the flag see the same
pragmas as before.

## Measurements (tier 2: compiler output), 2026-11-14

All on master `699f00dfcd` against the branch, ARM GCC 10.2
(10-2020-q4-major), copter, `--consistent-builds`.

| Board | Flash (bytes) | `bl` calls in EKF3 + GSF functions |
|---|---|---|
| CubeOrange | -1712 | 1735 -> 1349 |
| MatekH743 | -1712 | 1733 -> 1347 |
| SkySakuraH743 | -1120 | 1732 -> 1346 |
| MicoAir405v2 | -960 | 1494 -> 1198 |
| MatekF405 | -776 | 1373 -> 1148 |

Flash from `size_compare_branches.py`, measured on the two-commit
version (`9ce7c792d7`, `3e608dd287`). The three-commit head is
byte-identical to it on MatekF405, since the EKF2 commit changes
nothing where EKF2 is compiled out and the short and long pragma forms
compile identically.

Per commit, MatekF405 (each state built and linked):

| State | text | EKF calls | notes |
|---|---|---|---|
| master | 872008 | 1373 | |
| + EKF3 (`da042b1ecc`) | 871272 | 1148 | |
| + EKF2 (`d965cb76e1`) | 871272 | 1148 | byte-identical, EKF2 compiled out |
| + GSF (`fde5fe5a87`) | 871232 | 1148 | CompassLearn's two outlined calls go |

With `HAL_NAVEKF2_AVAILABLE 1` on MatekF405 (EKF2 / EKF3 `bl` calls):

| State | EKF2 | EKF3 |
|---|---|---|
| master | 1159 | 1294 |
| EKF3 + GSF only (the first draft) | 1235 | 1069 |
| EKF3 + EKF2, GSF unfixed (`d965cb76e1`) | 1017 | 1069 |
| all three | 1017 | 1069 |

The first draft's GSF change without EKF2 made EKF2 worse: helpers
defined between EKF2's bare O2 and the GSF include (`Vector3::zero()`,
`QuaternionT::operator[]`, `AP_ParamT` operators, `zero_range()`) lost
their inlining. Found by both the Claude and the Codex review, measured
here, and fixed by the EKF2 commit.

Other numbers:

- SITL copter is byte-identical to master at `fde5fe5a87`.
- Fused multiply-adds in EKF3 + GSF: CubeOrange 2610 -> 2634, MatekF405
  1820 -> 1835 (about 1% more, a rounding-level change).
- A minimal probe (`-Os -fno-math-errno`, template helper before the
  pragma): GCC 10.2 calls it out of line under a bare O2 and inlines it
  with `no-math-errno` after; host GCC 13.3 inlines it either way.
- Stacked pragmas accumulate: a later bare `O2` does not drop
  `no-math-errno` again (probe, and the `d965cb76e1` row above, where
  the GSF header's bare O2 still follows). A Codex round-two finding
  that the per-commit numbers needed the GSF commit is refuted by that
  row.
- On GCC 10 the O2 pragma also re-enables strict aliasing despite
  `-fno-strict-aliasing`, with or without this change (probe: the store
  through `float *` no longer forces a reload of `int *`). Pre-existing,
  not touched.

## Flight evidence (tier 1, on the 4.7-based beta)

The SFD beta's refresh16 topup1 build (`3af5f41e1b`, which contains
`f7ff8539ae` and `27371d37cf`) flew on 2026-11-13: about 5 min of acro
and Loiter. Replay of the flight in SITL reproduces the board's EKF to
float rounding (position 7.6 um, velocity 1.9e-6 m/s), the same
agreement as flights before the change. That build carries the if/else
form without the EKF2 commit; its EKF3 and GSF output is what the PR
produces on a board with EKF2 compiled out. EKF CPU time on hardware
was not measured.

## Left alone

- `ArduCopter/rate_thread.cpp`, `libraries/AP_Math/polygon.cpp` and
  `libraries/AP_Mount/SoloGimbalEKF.cpp` put an O2 pragma after their
  includes and have the same mismatch on a smaller scale (the Claude
  review measured rate_thread.cpp at 93 -> 77 calls, +246 B, object
  level on MatekF405). Candidates for a separate PR.
- The AP_Math and Filter `.cpp` pragmas come before any include, so the
  helpers they call are compiled under the same options.
- The GSF pragma sits in a header, so it also compiles CompassLearn at O2
  and applies to EKF3 even in `HAL_DEBUG_BUILD` (derived from the
  source, not measured). Pre-existing.

## Reviews

2026-11-14, before opening: mechanical gate clean; one Claude reviewer
and a Codex cold read on the two-commit draft, both finding the EKF2
regression; the Claude reviewer also flagged commit messages crediting
one commit with both commits' numbers, and comments saying "GCC" for a
GCC 10 problem. All fixed in the three-commit rewrite. Codex round two:
audit of the five earlier findings all CLOSED; its one new finding
refuted by measurement (above).

## Files

- `outlined_calls.py` - counts `bl` targets from EKF functions in one or
  more ARM ELFs and lists the targets whose count differs.

## Reproduce

```bash
# flash, from the ArduPilot checkout on the branch
Tools/scripts/size_compare_branches.py --master-branch=upstream/master \
    --branch=pr-ekf-o2-math-errno --vehicle=copter \
    --board=CubeOrange,MatekH743,SkySakuraH743,MicoAir405v2,MatekF405

# call counts, on two linked ELFs
python3 outlined_calls.py \
    /opt/gcc-arm-none-eabi-10-2020-q4-major/bin/arm-none-eabi-objdump \
    master=<master>/arducopter branch=<branch>/arducopter

# EKF2 enabled
printf 'define HAL_NAVEKF2_AVAILABLE 1\n' > ekf2.hwdef
./waf configure --board MatekF405 --consistent-builds --extra-hwdef=ekf2.hwdef
./waf copter
```
