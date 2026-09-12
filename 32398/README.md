# PR #32398 - Copter: arming delay in milliseconds, compiled out at zero

Analysis archive for [ArduPilot/ardupilot#32398](https://github.com/ArduPilot/ardupilot/pull/32398).
Branch `pr-copter-arm-delay`, head `904630fd82` after the 2026-09-12 redesign.
One commit, on master of 2026-09-12. The previous head `2038b1c1d9` was three
commits on a master from 17 March.

## Status (one line)

Input renamed to `ARMING_DELAY_MS` so sub-second delays are expressible and a
zero delay compiles the flag out; `ARM_DELAY` override dropped; stale
`ARMING_DELAY_SEC` raises `#error`. Replied to peterbarker's two threads.

## Why the design moved (2026-09-12)

peterbarker's CHANGES_REQUESTED was "half way between two patterns": the old head
let both `ARM_DELAY` (the rudder-arm hold count) and `ARMING_DELAY_MSEC` be
overridden. He also suggested keeping `ARMING_DELAY_SEC` as the input and deriving
milliseconds from it.

That suggestion was implemented first and then withdrawn, because **sub-second
delays are the point of the PR** and it cannot express them:

    #define ARMING_DELAY_SEC 0.25
    #if ARMING_DELAY_SEC*1000 > 0    -> error: floating constant in preprocessor expression

Verified with gcc. The old `2.0f` default has the same problem, which is why a
zero delay could never be compiled out under the upstream name.

So: one input, in integer milliseconds. Built for SITL at the default, at 250 and
at 0; the stale-name `#error` verified to fire.

## The race rmackay9 questioned

"Surely we don't actually need this check... I suspect it works even if ARM_DELAY
is 0." It does not quite. With a zero delay `in_arming_delay` was still set at arm
and cleared only once `millis()` passed `arm_time_ms`, so an arm and a
`motors_output()` pass inside the same millisecond held the motor interlock off
for that pass. Compiling the flag out removes it.

## Hazard for the SFD fork

The SFD tree uses `ARMING_DELAY_MSEC`, from this PR's old revision, in nine
SFD-local hwdefs baked into `SmallFastDrone-4.7-base`. The new `#error` catches
only `ARMING_DELAY_SEC`, so those defines become silently ignored and every SFD
board gets a 2 s delay back. Recorded as a must-do in
`smallfastdrone/Tools/SFD/REFRESH_NOTES.md`. An `#error` on `ARMING_DELAY_MSEC`
here would turn a missed rename into a build failure; not yet added.

## Process note

A probe revert with `git checkout -- ArduCopter/config.h` silently undid the
config change itself, because the branch had no commit yet, and two probe builds
after that ran on a half-applied tree. Save a known-good copy before probing an
uncommitted change.
