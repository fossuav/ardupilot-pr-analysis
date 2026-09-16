# Field test round two: OSD and RC input on RPI_UAVFC

Written 2026-09-16 after the first flights
([field-test-2026-09-16-results.md](field-test-2026-09-16-results.md)).
Background, the hypothesis table and the file-pull procedure are in
[field-test-osd-rcin.md](field-test-osd-rcin.md); this page is what changed.

The first flights showed core1 with ~2% idle in flight. The question this
round answers: **does the OSD renderer actually miss its deadline in flight,
and is the RC UART losing bytes?** The firmware now counts both, every 10 s,
into the log.

## The build

Branch `rp2350-v5-squashed-and-cleaned-and-rebased` at `35e92d8b2e`, ChibiOS
`af493a7bd5`:

```
./waf configure --board RPI_UAVFC --enable-stats \
    --extra-hwdef=field-profile.hwdef
./waf copter
```

`field-profile.hwdef` now has only the sampler and the report:

```
undef AP_RP2350_PC_SAMPLER_ENABLED
define AP_RP2350_PC_SAMPLER_ENABLED 1
undef AP_RP2350_DEBUG_REPORT_ENABLED
define AP_RP2350_DEBUG_REPORT_ENABLED 1
```

`AP_XIP_PROFILER_ENABLED` is gone - it was ~13% of core1 in flight. Heap cost
against a normal build: 28.0 KB (`__heap_base__` 0x2002b8f8 to 0x200328f8).
The sampler and per-thread timing still perturb what they measure, but far
less than round one.

0 warnings. Not run on hardware before shipping (the bench board was not
connected), so the first boot is also the check that the new lines appear.

## Files for the tester

In `C:\Users\uav\rp2350_field2`:

| File | md5 | Use |
|---|---|---|
| `RPI_UAVFC-field2.uf2` | `b1c12def0a774a44d23989bb1d870ba6` | BOOTSEL drag-and-drop |
| `RPI_UAVFC-field2.apj` | `b82584b089d3280d5237a9a353bf43e2` | `uploader.py` / Mission Planner |
| `RPI_UAVFC-field2_with_bl.hex` | `aea5ba3d792f3496551faf26b9b16929` | SWD, app **and** bootloader |
| `RPI_UAVFC-field2.elf` | `04e691a87eae0869b93e42cee098b58e` | **keep** - sampler attribution |

Plus `field-profile.hwdef` and `uploader.py`. The log must report `35e92d8b`.
Ask which upload route the tester used: an app UF2 has still not been
confirmed on this hardware.

## Parameters

- `INS_RAW_LOG_OPT 0` and `INS_LOG_BAT_MASK 0`. Round one had 9 and 1, and
  the log dropped 76% of its messages.
- `LOG_BITMASK` was already fine (140510 has PM, RCIN and RCOUT).
- Otherwise leave everything as flown last time.

## What to fly

1. **CRSF**, the RC setup under test (`SERIAL3_PROTOCOL 23`). Round one has
   no usable log for it.
2. Hover a minute, then fly the cases where OSD and RC problems appear, and
   mark each symptom with a mode change as before.
3. After disarm, download the log and **check it is more than a header**
   before power-off. Round one's CRSF log was 32 KB. If it is small again,
   pull the files anyway and say so - that is a finding.
4. Same `@SYS` files as before. `uarts.txt` now has rows for the PIO UARTs.
5. If there is time, the same hover with RC over MAVLink, for comparison.

## Reading the new report

Every 10 s, in the GCS and in the log as MSG (each line now fits the log's 50
characters):

| Line | Meaning |
|---|---|
| `Perf: main=200Hz rate=1610Hz` | main loop and rate thread rates |
| `Perf: core0load:85% core1load:97% xip=91%` | scheduler load on core0, idle-derived load on core1, XIP cache hit rate, all over the window |
| `OSD: fields=500 late=N desync=N` | fields scanned out; blocks sent blank because the renderer was late; fields cut short by the FIFO running dry |
| `PIO0 rx=N drop=N ovr=N fe=N` | receive bytes, bytes lost to a full ring, state-machine FIFO stalls, framing errors |
| `XIPpark: n= max=us` | only when core1 was parked for a flash write |
| `PROFc1 ...` | core1 sampler top 16, cumulative |

On RPI_UAVFC `PIO0` is SERIAL3 (RC) and `PIO1` is SERIAL4 (SmartAudio);
`uarts.txt` prints the mapping as `SERIAL3 PIO0`.

What to look for:

- `late` is out of 32 blocks per field at PAL (26 at NTSC), so a clean PAL
  window is `late=0` of 16,000. Late blocks that appear only between arm and
  disarm, and line up with the tester's OSD notes, confirm the core1
  hypothesis. `late=0` through an OSD symptom kills it.
- `desync` above zero is a different fault - the PIO FIFO starved outright,
  not just a slow render.
- `PIO0` `drop`, `ovr` or `fe` above zero during RC trouble means bytes lost
  below the protocol parser. All zero with RC trouble points at latency in
  `rcin` or the main loop instead - compare with `Perf: main=` and `PM`.
- `core1load` per window replaces the idle-PC arithmetic from round one.
