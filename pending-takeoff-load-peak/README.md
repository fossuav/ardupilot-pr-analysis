# Takeoff blocked for the rest of a boot by one busy second (Copter, ChibiOS)

Not a PR yet. The code is Andy's, merged upstream: `6e86351aeb`
"AP_HAL_ChibiOS: add support for idle-hook based true CPU load" and
`342a8bdfd8` "Copter: add system load takeoff check", both 2025-08-16, in
4.7 and unchanged on master as of `3d066385b6` (2026-10-25). Leonard Hall's
May 2026 rework of `takeoff_check.cpp` (`26528294a8`, `ff1a48113c`,
`d3a26130ac`) kept the load test as it was.

## Status (one line)

Found 2026-10-30 on SFD-O4 log64 (3408138/645): two armings, no takeoff.
Mechanism from the source; fix not written.

## The flight

log64, beta `52b1d36f`, `BRD_IDLE_STATS 1`. Armed in ACRO at 60.1 s and
81.7 s; "Takeoff blocked: CPU overload" every 2 s from 62.6 s to the end of
the log, at 92.2, 92.0, 91.9, 92.1 then 84.4-87.4%. Never NOT_LANDED. The
same firmware and parameter took off on logs 61, 62, 63 and 65.

## Mechanism (derived from the source, not measured)

- `Copter::takeoff_check()` keeps the spool-up block while
  `avg_load > 95.0f || peak_load > 99.5f`.
- `peak_load` is `sysGetCPUPeakLoad()`, `_load.peak` in
  `hwdef/common/sysperf.c`. It is raised whenever the current run/idle ratio
  (cumulative averages halved each second, so roughly a 1 s figure) exceeds
  it, and zeroed only in `SYS_MEASURE_INIT`, which `main_loop()` enters once
  at boot. It is the worst second since boot.
- The message prints `avg_load`. Every printed value was under 95%, so by
  elimination the peak blocked, and the reason the pilot is shown is not the
  one that applied.
- `AP_BoardConfig::use_idle_stats()` reads `BRD_IDLE_STATS` live, so setting
  it to 0 lifts the block without a reboot; a reboot clears the peak.

## What the log can and cannot show

The peak is not logged, so when it latched is unknown. Before the first arm
this boot had a radio failsafe (12.7-17.7 s) and turtle mode
(17.9-27.1 s); the other boots had neither. Main-loop load is no guide:
`PM.Load` 26-30% and `PM.MaxT` about 5.2 ms at 200 Hz, the same on logs 61,
63, 64 and 65. The whole-CPU average of 84-92% includes the fast rate thread
(`FSTRATE_ENABLE 2`, about 2 kHz), leaving 8-15% under the peak threshold.

## Fix to try

Test the headroom at takeoff, not the worst since boot (root playbook
ARCH-2, test for what you need): reset the peak when the vehicle arms, or
keep a windowed peak, and print whichever value blocked.

## Testing it

Not an EKF change, so Replay does not apply. SITL cannot show it either as
things stand: `AP_HAL_SITL` does not implement `get_system_load()`, whose
default returns false, so the load check never blocks there. It needs
hardware, or a SITL load source added first.
