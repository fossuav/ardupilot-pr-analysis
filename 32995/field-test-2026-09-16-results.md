# Field test results, 2026-09-16: OSD and RC input on RPI_UAVFC

Data from the tester in `C:\support\raspberrypi\Gautam\Data` (WSL
`/mnt/c/support/raspberrypi/Gautam/Data`), taken with the build described in
[field-test-osd-rcin.md](field-test-osd-rcin.md). Two sessions:

| Session | RC path | Uptime at file pull | Log |
|---|---|---|---|
| `Data_CRSF` | CRSF on SERIAL3 (PIO UART) | ~316 s | **unusable** - 32 KB, header and two records |
| `Data_MAVLINK2` | ELRS MAVLink mode, SERIAL3 `MAVLink2` at 460800 | ~289 s | 111 s: arm at 6 s, STABILIZE, ALT_HOLD from 25 s, disarm 96.9 s |

Firmware checked: log reports `bc30cce1` / ChibiOS `af493a7b`, and the ELF
on the bench host is md5-identical to the build tree
(`059b3dd6f88b971d15e699ba999a47b2`), so the sampler attribution is valid.
Uptimes are from the core1 sampler's count at 5076 Hz (core0's count is
5-6% lower in both sessions; not investigated).

## What the data shows

### Core1 is ~98% busy in flight

The `@SYS` files are cumulative since boot, and most of each session was on
the ground (MAVLink session: ~90 s of flight in ~289 s), so they understate
flight load: `threads.txt` gives core1 idle 16-23%. The PROFc1 dumps in the
log are timestamped, so the idle PC (`rp2350_idle_c1`, `S144c`/`S144e`) can
be differenced per 10 s window:

| Window | core1 idle |
|---|---|
| boot to first dump (mostly on the ground) | 31% |
| every 10 s window from takeoff to disarm (9 windows) | 0.5-2.5% |
| first window after disarm | 11.9% |

The rate loop itself is healthy through it: `RTDT` dtAvg 0.62 ms (1610 Hz),
dtMax 0.9-1.2 ms, and no `XIPpark` line at all between arm and disarm (MSG is
a critical write, so its absence is real). Parks start after disarm: 9 per
10 s window, max 5.8 ms - most likely the storage writes that follow a
disarm. A visible OSD hitch then, but not in flight.

### Why that matters for the OSD (hypothesis)

`OSD_c1` is the lowest-priority thread on core1 (58, `PRIORITY_IO`), behind
the rate thread (182), `SPI0` and `rcout` (181). The renderer keeps two 9-line
blocks queued, about 1 ms of video. When it is late, `advance_to()` sends that
block transparent - the overlay drops out for a band of lines. With ~2% idle
on the core that is a plausible in-flight-only OSD fault. **Not proven:**
nothing counts late or blank blocks, so the next build has to.

The renderer is cheap (`render_block` and `core1_thread` together ~0.2% of
core1 samples); the problem, if it is this, is latency, not cost.

### The field build inflated core1 by roughly 13%

`ap_xip_cs_hook` (`AP_XIP_PROFILER_ENABLED`, which the guide told the tester
to build in) is the top function on core1: 18.7% of all core1 samples over
the CRSF session, and roughly 13% in flight (six of its hot PCs sum to 8.4%
per window; those six are ~65% of its samples overall). It runs on every
context switch - ~14,500/s on core1, from the `W=` counts - and does a linear
search over up to 24 thread entries. The samples are spread over that loop,
so this is real CPU time, not a stall. `xip_profiler.cpp` says the hook is
placed in SRAM through the RAMFUNC2 registry; the registry line is commented
out, so it runs from XIP flash.

Its per-thread XIP hit rates are also not per-thread on SMP: both cores
share `CTR_HIT`/`CTR_ACC` and each core's context switch resets them. Only
the aggregate (~91%) means anything.

So the production build has more core1 headroom in flight than this data
shows - roughly 15% idle rather than 2%. The OSD renderer is still last in
line on that core.

### Raw gyro logging ate the log

`INS_RAW_LOG_OPT=9` and `INS_LOG_BAT_MASK=1` are set (defaults 0). `DSF.Dp`
reaches **298,726 dropped messages against 93,584 written**. What we asked
for mostly did not survive: 148 `RTDT` records in 88 s of flight (10 Hz would
be 880), 270 `RCIN` in 111 s, 11 `PM`. `Write_GYR` is also 2.8% of core1,
since it runs in the IMU path there.

### Core0 misses its loop rate in flight

`PM`: LR 199-200 Hz on the ground, 189-194 Hz in flight, 47-86 long loops per
10 s window (3-6 on the ground), MaxT 6.3-7.0 ms, scheduler load 86-100%.
`read_AHRS` (EKF) averages ~2.0 ms of the 5 ms loop and is 45-52% of task
time; `update_flight_mode` 0.73 ms.

`rcin` (177) sits below the main loop (180) on core0. That is the normal
ArduPilot ordering, but on STM32 the main loop has slack and here it does
not.

### RC input: what differs between the sessions

- `rcin` thread: 7.1% of core0 with CRSF, 1.8% with RC over MAVLink.
- `GCS::update_receive`: with RC over MAVLink every call takes 772-2927 us,
  avg 964 us; with CRSF 65-1417 us, avg 148 us. The loop reads everything
  `available()` returns, so this is a lot of bytes, or slow per-byte reads
  on the PIO UART. Unexplained.
- `AP_Param::find_var_info_group` is 2.1% of core0 samples in the CRSF
  session and ~0 in the other. It is reached from parameter name copies (a
  GCS parameter download), saves and `configured()` checks; telling which
  needs a time-resolved profile. Unexplained.
- `AP_Logger::periodic_tasks` in the CRSF session: avg 802 us, 999 overruns,
  16.7% of task time, against 47 us and 37 in the MAVLink session. Together
  with the 32 KB log, logging was not healthy in that session.
- **The RC UART has no visible stats.** SERIAL3 and SERIAL4 are PIO UARTs;
  `PIORXDriver` implements neither `uart_info()` nor the byte counters the
  `UART` log message needs, so `uarts.txt` prints the port names and nothing
  else and the log has no `UART` record for them. The driver already
  counts RX overruns (`pio_uart_rx_overrun_count`), framing errors and IRQ
  time, but nothing reads them. SERIAL2 (hardware UART, GPS) is clean: no
  drops, FE/OE/NE all zero.

Free heap at file pull: 24.2-24.8 KB. The profiling build costs ~27.5 KB, so
a normal build would have ~52 KB.

## What the guide got wrong

Recorded loudly, since the guide is what the tester flew from:

- It recommended `AP_XIP_PROFILER_ENABLED`. That cost ~13% of core1 in
  flight and its per-thread figures are invalid on SMP. Drop it.
- It said the 10 s report lands in the log, which "is what makes a field
  flight readable afterwards". The log keeps only the first 50 characters of
  a STATUSTEXT (the MAVLink field length, not the 64 of the MSG record), so
  `Perf:` is cut at `core1lo`, losing core1 load and XIP rate, and each
  `PROFc1` line keeps about four tokens. The windowed idle figure above is recoverable; core1
  load and XIP rate per window are not.
- It said the board hwdef defines each overlay flag as 0. RPI_UAVFC does not
  define `AP_XIP_PROFILER_ENABLED` at all (and the XIP code tests
  `defined()`, not the value).
- It relied on cumulative `@SYS` files. They are diluted by ground time; the
  in-flight numbers have to come from the log.

## Next build and next flight

Build changes, smallest first:

1. Drop `AP_XIP_PROFILER_ENABLED` from the overlay.
2. OSD: count blank (late) blocks and desyncs per 10 s window and report them.
   This is the measurement that confirms or kills the core1 hypothesis.
3. Report `pio_uart_rx_overrun_count`, `pio_uart_rx_framing_count` and
   `pio_uart_irq_us_max` for the RC port, and implement `uart_info()` for
   `PIORXDriver` so `uarts.txt` covers it.
4. Split `Perf:` into lines of at most 50 characters, so core1 load and XIP
   rate survive into the log.

Flight changes for the tester:

- `INS_RAW_LOG_OPT 0`, `INS_LOG_BAT_MASK 0` for these flights.
- The CRSF flight is the one that needs a log - it is the RC path under test
  and the only session where `rcin` was expensive. Download it after
  disarming and check the file is more than a header before power-off.
- Note OSD symptoms against time as before; with a blank-block counter in the
  report they can be matched per window.

A/B worth doing once the counters exist: the same hover with the OSD enabled
and `OSD_TYPE 0`, which says directly how much core1 the scan-out takes.

## Round two build (2026-09-16)

All four build changes above are done, as additive commits on the PR branch:

| Commit | Change |
|---|---|
| `3729215583` | count late and desynced OSD blocks |
| `04d0df615d` | PIO UART traffic and error stats: `uarts.txt` rows, `UART` log records, counters for the report |
| `709499232b` | fit the report into 50 characters: `Perf:` split in two, `PROFc1` wrapped on the real limit |
| `35e92d8b2e` | `OSD:` and `PIOn` lines in the 10 s report, as per-window deltas |

Normal RPI_UAVFC, Laurel and Pico2 builds: 0 warnings. The field build is in
the guide. Not yet run on hardware - the bench board was not connected - so the
first boot is also the first check that the new lines appear.
