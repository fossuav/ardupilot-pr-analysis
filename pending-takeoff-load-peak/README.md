# Takeoff blocked for the rest of a boot by one busy second (Copter, ChibiOS)

Not a PR yet. The code is Andy's, merged upstream: `6e86351aeb`
"AP_HAL_ChibiOS: add support for idle-hook based true CPU load" and
`342a8bdfd8` "Copter: add system load takeoff check", both 2025-08-16, in
4.7 and unchanged on master as of `3d066385b6` (2026-10-25). Leonard Hall's
May 2026 rework of `takeoff_check.cpp` (`26528294a8`, `ff1a48113c`,
`d3a26130ac`) kept the load test as it was.

## Status (one line)

Found 2026-10-30 on SFD-O4 log64 (3408138/645): two armings, no takeoff.
Mechanism confirmed from the logged threads.txt (the first account below
is superseded); not pursued, as open PR #33366 fixes it.

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

### Superseded 2026-10-30 (later) by the logged threads.txt and review

"Zeroed only at boot" and "the worst second since boot" are wrong. Found by
the /pr-review round on `6ab81d05b2` and confirmed from the flight's own log.
On master, `main_loop()` tests `use_idle_stats()` before the parameters are
loaded (`HAL_ChibiOS_Class.cpp`, before `setup()`), so with the default 0
the measurement never starts at boot. `Util::thread_info()`, the
`@SYS/threads.txt` reader, calls stop then start: on the first read that
starts it, and on a later read the stop only takes effect at the next idle
entry while the start is skipped, which leaves it stopped with average and
peak frozen. AP_Logger reads `@SYS/threads.txt` after every arming and
copies it into FILE records, so the log does carry the figures this section
said it could not:

| Log | First arming | Second arming |
|---|---|---|
| log64 (blocked) | LOAD 0.0% PEAK 0.0% | LOAD 87.3% PEAK 99.5% |
| log63 (flew) | LOAD 0.0% PEAK 0.0% | LOAD 87.4% PEAK 97.1% |
| log65 (flew) | LOAD 0.0% PEAK 0.0% | - |

So on log64 the measurement was not running at boot, and the radio failsafe
and turtle mode could not have set the peak. It started with the logger's
read after the first arming at 60.1 s; the block began at 62.6 s; after a
restart the first values of `current` come from very few run and idle
samples (`sysperf.c`), which is enough to cross 99.5% without a sustained
overload. After the second arming's read the reported average stayed at
exactly 87.4% from 82.8 to 90.9 s: the freeze. The section above is left as
written because the reasoning from the takeoff check itself (the peak
blocked, and the message showed the average) still holds.

## What the log can and cannot show

The peak is not logged, so when it latched is unknown. Before the first arm
this boot had a radio failsafe (12.7-17.7 s) and turtle mode
(17.9-27.1 s); the other boots had neither. Main-loop load is no guide:
`PM.Load` 26-30% and `PM.MaxT` about 5.2 ms at 200 Hz, the same on logs 61,
63, 64 and 65. The whole-CPU average of 84-92% includes the fast rate thread
(`FSTRATE_ENABLE 2`, about 2 kHz), leaving 8-15% under the peak threshold.

Superseded: the peak is logged, in the `@SYS/threads.txt` copy written
after each arming (table above). Neither the radio failsafe nor turtle mode
can have set it, because measurement was not running then.

## Fix to try

Test the headroom at takeoff, not the worst since boot (root playbook
ARCH-2, test for what you need): reset the peak when the vehicle arms, or
keep a windowed peak, and print whichever value blocked.

## Testing it

Not an EKF change, so Replay does not apply. SITL cannot show it either as
things stand: `AP_HAL_SITL` does not implement `get_system_load()`, whose
default returns false, so the load check never blocks there. It needs
hardware, or a SITL load source added first.

## 2026-10-30 (later): prototyped

Local branch `pr-takeoff-load-recent` on master `278a68a57a`, commit
`9541f64de8`, not pushed; SITL and MatekH743 copter build,
`check_branch_conventions.py` clean. Copter only: while the spool-up block
is held, keep the highest `avg_load` of the current and the previous 2 s
warning window and test that instead of the HAL's since-boot peak; the
message now says "avg" or "peak" and prints the value that blocked.

What building it found (derived from the source, not measured):
`takeoff_check()` runs at 50 Hz and reaches the load test only while the
block is held, from spin-up until every check passes. A window that starts
there holds one sample on its first evaluation, so the recent peak equals
the current average, which `avg > 95` already covers. The peak test then
adds only a 2-4 s hold-off after near-saturation while something else
holds the block. Dropping the peak test and blocking on the average alone
would be smaller and lose almost nothing (root playbook ARCH-7); left as
the decision for the PR. `get_system_load()` has no other caller, and
`@SYS/threads.txt` reads sysperf directly, so a HAL-side fix would not have
touched that diagnostic either.

## 2026-10-30 (later): the peak test dropped

Andy's decision: drop the peak test. Local branch `pr-takeoff-load-avg`,
commit `6ab81d05b2` on master `278a68a57a`, not pushed: the load check
blocks on `avg_load > 95` alone, which the warning already prints, and the
comment says why the HAL peak is not used. No new state. SITL and
MatekH743 copter build, astyle unchanged, `check_branch_conventions.py`
clean. `pr-takeoff-load-recent` (`9541f64de8`, the windowed peak) is
superseded and can be deleted.

## 2026-10-30 (later): dropped in favour of #33366

The /pr-review round on `6ab81d05b2` found open PR #33366 (robertlong13,
"AP_HAL_ChibiOS: log idle-hook based true CPU load", head `5c87069c35`)
already fixing the HAL side: it starts the measurement once the parameters
have loaded, removes the stop/start freeze in `thread_info()`, adds
`consume_system_load()` with its own window for the takeoff check and for
logging, makes threads.txt report the peak since its previous read, and
makes the takeoff thresholds parameters (`TKOFF_CPU_AVG`, `TKOFF_CPU_PEAK`)
with the message printing both values. That covers every part of this
record's fix and the mechanism behind log64, so Andy's decision is to drop
both local branches (`pr-takeoff-load-recent` `9541f64de8`, `pr-takeoff-
load-avg` `6ab81d05b2`) and support #33366 instead.

A comment for #33366 with log64's figures (the three threads.txt
observations above, and that 87.4%/97.1% on a boot that flew cannot
separate the restart transient from the steady-state peak) is drafted but
not posted; Andy posts it. Open question for that PR: whether the 99.5%
peak default leaves margin at an 87% average with the fast rate thread.
