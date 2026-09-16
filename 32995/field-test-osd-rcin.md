# Field test guide: OSD and RC input on RP2350

Written 2026-09-16 for a tester reporting OSD and RC input problems on
RPI_UAVFC with analog video. The point of this build is that the board
reports what it is doing, so one flight plus a file pull before power-off
tells us which cause it is, instead of another round of guessing.

Read [README.md](README.md) for the state of the PR itself.

**Superseded in part by the first flights** - see
[field-test-2026-09-16-results.md](field-test-2026-09-16-results.md), and
fly [field-test-round2.md](field-test-round2.md) next.
`AP_XIP_PROFILER_ENABLED` below cost ~13% of core1 in flight and must be
dropped, and this build's log does not carry the full 10 s report: the log
keeps only the first 50 characters of each line.

## What the data has to separate

All of these produce "the OSD is glitchy and the RC feels laggy", and the
firmware can tell them apart:

| Cause | What it would be | Where it shows |
|---|---|---|
| Core1 contention | the OSD scanout thread `OSD_c1`, the rate thread, `rcout` and the SPI0 (IMU) bus thread all run on core1 | `threads.txt` per-core loads, `PROFc1` histogram, `RTDT` in the log |
| XIP park | a flash write (parameter or storage save) drops XIP and parks core1, which is where OSD scanout and the rate loop live | `XIPpark: n= max=` lines in the log, timed against the tester's symptom notes |
| XIP cache thrash | core0 and core1 competing for the 16 KB XIP cache | `xip=NN%` in the `Perf:` line |
| Core0 saturation | `rcin` shares core0 with the main loop, GCS and logging | `Perf: core0load`, `main=NNHz`, `tasks.txt`, `PM` log message |
| Interrupt time | the OSD line ISR and the RC edge capture competing in interrupt context | core0 histogram `pcprof0.txt`, the `ISR` rows of `threads.txt` |

The per-core loads in `threads.txt` were wrong until 2026-09-15 (every
figure was halved and the stack column read as used rather than free), so
ignore any earlier capture.

## The build

Board RPI_UAVFC, branch `rp2350-v5-squashed-and-cleaned-and-rebased`,
ArduPilot `bc30cce141`, ChibiOS `af493a7bd5`. Built with an overlay so the
board hwdef is untouched:

```
./waf configure --board RPI_UAVFC --enable-stats \
    --extra-hwdef=field-profile.hwdef
./waf copter
```

`field-profile.hwdef` (kept beside the firmware):

```
undef AP_RP2350_PC_SAMPLER_ENABLED
define AP_RP2350_PC_SAMPLER_ENABLED 1
undef AP_RP2350_DEBUG_REPORT_ENABLED
define AP_RP2350_DEBUG_REPORT_ENABLED 1
undef AP_XIP_PROFILER_ENABLED
define AP_XIP_PROFILER_ENABLED 1
```

The `undef` lines matter for the two flags the board hwdef defines as 0;
without them the overlay only adds a second, conflicting definition.
RPI_UAVFC does not define `AP_XIP_PROFILER_ENABLED` at all.

What each switch buys and costs:

- `AP_RP2350_PC_SAMPLER_ENABLED` - a statistical PC sampler on both cores
  off a TIMER0 alarm every 197 us (~5.1 kHz), handler in SRAM, 24 KB of
  BSS. This is the "statistical analyser": it says which functions the
  cores are actually in.
- `AP_RP2350_DEBUG_REPORT_ENABLED` - the 10 s report: one `Perf:` line
  (main loop Hz, rate Hz, per-core load, XIP hit rate), an `XIPpark:` line
  when core1 has been parked, and the core1 sampler's top 16 PCs as
  `PROFc1` lines. These go to the GCS **and into the dataflash log as MSG
  records**, which is what makes a field flight readable afterwards.
- `--enable-stats` - ChibiOS per-thread timing, so `threads.txt` carries
  LOAD per thread and per core.
- `AP_XIP_PROFILER_ENABLED` - per-thread XIP cache hit counters, appended
  to `threads.txt`.

`AP_RP2350_SPI_CYCLE_STATS_ENABLED` is deliberately **not** set: it counts
SPI stop/start cycles into globals that nothing prints, so the numbers are
only reachable over SWD and are no use in the field.

Measured cost, from the ELFs: the heap goes from 336.8 KB to 309.3 KB
(`__heap_base__` 0x2002bce8 to 0x20032cf8), so about 27.5 KB of the ~124 KB
freed by the 2026-09-15 stack work. There is no measurement yet of the CPU
cost in flight; the first hover is the baseline for that.

**This build perturbs what it measures.** Two ~5.1 kHz interrupts and the
per-context-switch timing are not free, and the OSD and rate loop are the
things under test. Treat absolute numbers as "with profiling on", and
compare like with like.

## Files for the tester

In `C:\Users\uav\rp2350_field` (Windows host beside the bench). The same
firmware in three containers, so the tester can pick whichever upload route
suits them:

| File | md5 | Use |
|---|---|---|
| `RPI_UAVFC-field-profile.uf2` | `685f1d621de26cd70f6bf5a42b68c96c` | BOOTSEL drag-and-drop |
| `RPI_UAVFC-field-profile.apj` | `380b42ed779f9af74581c2a9e28adc6b` | `uploader.py` / Mission Planner |
| `RPI_UAVFC-field-profile_with_bl.hex` | `d2c392a743a045be9c045de62c641f35` | SWD, app **and** bootloader |

Plus `RPI_UAVFC-field-profile.elf` - **keep this**. Sampler output is raw
addresses; without the exact ELF it cannot be attributed to functions. And
`field-profile.hwdef`, the overlay above.

The log records the firmware hash; check it reads `bc30cce1` before
trusting an attribution.

### Which one to use

**UF2 is the easy one.** Hold BOOTSEL while plugging in USB, the board
appears as a mass-storage drive, copy the `.uf2` onto it. The blocks are
addressed at `0x10020000`, so it writes the app and leaves the bootloader at
`0x10000000` alone - unlike a Betaflight UF2, which starts at `0x10000000`
and takes the bootloader with it.

Caveat worth stating plainly: the generator is verified (the UF2 payload is
byte-identical to the `.bin`, 5745 blocks from `0x10020000`, RP2350 Arm
Secure family `0xe48bff59`), but nobody has yet flashed an *app* UF2 on this
hardware - only bootloaders that way. If the board comes up on the old
firmware, or does not come up, fall back to the apj:

```
py uploader.py --port COM5 RPI_UAVFC-field-profile.apj
```

with Mission Planner closed; the bootloader can appear on a different COM
number.

The `_with_bl.hex` is for SWD recovery only. It starts at `0x10000000` and so
rewrites the bootloader as well - the way back if a BOOTSEL load ever wipes
it. Until 2026-09-16 this file was written at the STM32 base `0x08000000`,
where openocd silently wrote none of it; check the first line reads
`:020000041000` before trusting one.

## Parameters

Leave the tuning alone so the flight is comparable with the tester's
earlier ones. Only make sure the log carries the relevant messages -
`LOG_BITMASK` needs PM (8), RCIN (64) and RCOUT (1024) set in addition to
the usual bits. `RTDT` (rate loop dt) and the `MSG` records are logged
regardless.

## In the field

1. Power on with the GCS connected and confirm a `Perf:` line appears
   within ~15 s, followed by `PROFc1` lines. If they do not appear, the
   wrong firmware is loaded.
2. Hover for a minute, hands off as much as the conditions allow. This is
   the baseline for the numbers below.
3. Then fly the cases where the OSD and RC problems show up.
4. **Mark each symptom.** Note the time, and make it visible in the log:
   a flight mode change is the easiest marker, since it is logged and
   easy to find. "OSD tore at about 3 minutes" is much weaker than a mode
   change at the moment it happened.
5. Land and **do not power cycle**. The sampler histogram, the thread
   statistics and the XIP park counters all accumulate since boot and are
   gone after a reset.
6. With USB connected, pull these files over MAVFTP (MAVProxy:
   `ftp get @SYS/threads.txt threads.txt`, and the same for each):
   `threads.txt`, `tasks.txt`, `pcprof0.txt`, `pcprof.txt`, `dma.txt`,
   `memory.txt`, `uarts.txt`, `timers.txt`.
   `pcprof0.txt` is core0 and `pcprof.txt` is core1, each the full top-512
   table rather than the 16 PCs the log carries.
7. Then download the `.bin` log.

## What to send back

- the `.bin` log
- the eight `@SYS` files, named with the flight number
- for each symptom: time, what the video did (tearing, rolling, blanking,
  character corruption) and what the RC did (lag, steps, failsafe)
- the setup: RC protocol and frame rate, video standard (PAL or NTSC), ESC
  protocol, and whether telemetry was connected

## How we read it

- **`PROFc1` from the log**: pull the MSG records into a text file and
  attribute them with the matching ELF:
  `python3 Tools/debug/rp2350_pc_profiler.py --elf RPI_UAVFC-field-profile.elf --histogram profc1.txt`
  The tool reads the flash base from the ELF, so RPI_UAVFC's app offset is
  handled. The same tool reads `pcprof0.txt` and `pcprof.txt`.
- **`threads.txt`**: per-thread stack use (free/total) and LOAD per core,
  with `C0`/`C1` tags and an ISR row per core. Core1 should show the rate
  thread, `rcout`, `SPI0` and `OSD_c1`.
- **`tasks.txt`**: scheduler task times on core0, for main loop overruns.
- **`RTDT` in the log**: rate loop dt average, max and min at 10 Hz. A max
  that spikes at the same time as an `XIPpark` line is the park, not
  contention.
- **`Perf:` lines**: main loop Hz, rate Hz, core loads, XIP hit rate.
- **`PM`**: main loop time and load from the vehicle's own accounting.
- **`dma.txt`**: DMA contention. Note it prints 12 channels for RP2350
  while the chip has 16, so channels 12-15 are labelled as a second
  controller (known, unfixed).

## Once we know

The freed SRAM is what makes the next step possible: the RAMFUNC2 registry
(`hwdef/common/rp2350_ramfunc2_registry.txt`) moves hot functions out of
XIP flash into SRAM, and the sampler output is exactly the input that
registry wants. `hwdef/RPI_UAVFC/PROFILING.md` covers how to add entries
and the traps (relocating a small leaf that core0 calls can cost more than
it saves).
