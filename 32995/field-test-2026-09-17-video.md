# OSD video from the round-three build, delivered 2026-09-17

Two DVR captures of the analog downlink, and nothing else this round - no
`.bin` log and no `@SYS` files. In `support/raspberrypi/Gautam`:

| File | Length | RC path |
|---|---|---|
| `VID3_CRSF.mov` | 127.2 s, 7634 frames | CRSF on SERIAL3 (PIO UART) |
| `VID3_MAVLINK2.mov` | 282.8 s, 16965 frames | ELRS in MAVLink mode |

Both 720x480 at 60 fps. The flight date is not in the files; they arrived on
the analysis machine 2026-09-17 22:08 local.

Numbers below were taken 2026-09-17 with
[tools/osd_video_blocks.py](tools/osd_video_blocks.py) and
[tools/osd_video_ocr.py](tools/osd_video_ocr.py), against firmware
`4f982aea88` (identified from the screen, see below).

## The video is a per-field record of what the renderer delivered

NTSC at 60 fps is one captured frame per field: 98.5% of consecutive frame
pairs differ (a 30 fps source line-doubled to 60 would be near 0%), and the
firmware's own field count over a report window is consistent with it - 673
fields in a window the IO thread cannot have run in under 10 s. The overlay is
26 blocks of 9 lines per field, and a block the renderer misses goes out
transparent, so each frame says which blocks arrived. A character row is 18
lines - two blocks - so a miss cuts the glyphs in half along the row.

Grid on these captures: x=44.25, 21.70 px per column, 30 columns; y=7, 36.0
px per character row, 13 rows. The capture's horizontal phase walks about a
pixel a second and jumps after each analog dropout, so the OCR re-fits the
grid every window. Matching the cells against `font0.bin` itself (12x18 at 2
bits per pixel, the same file the firmware loads) is what reads the screen
back.

**Which fields count.** 33% of the CRSF capture and 40% of the MAVLink
capture are analog snow or black - the video link, not the OSD. Those are
excluded, along with anything within two fields of them. A block counts as
missing only if it carried ink within 15 fields either side, so a value
leaving the screen is not counted as a loss.

## The build that flew

The 10 s report's OSD line was caught on screen at t=103 s of the CRSF
capture and reads `FIELDS=673 LATE=769 B`. `blank=` was added to that line in
`be5351ba7a`, and round two (`35e92d8b2e`) printed `fields= late= desync=`,
so the firmware is round three - `4f982aea88` or one of its three
predecessors. That matters because the video carries no firmware hash.

## The overlay still loses blocks in flight

| | CRSF | RC over MAVLink |
|---|---|---|
| usable fields | 5137 (67%) | 10185 (60%) |
| text blocks missing | 20.8% | 11.4% |
| fields drawn whole | 44.8% | 64.0% |
| fields part missing | 53.5% | 35.7% |
| fields with the whole overlay gone | 1.7% | 0.2% |
| longest whole-overlay gap | 8 fields (134 ms) | 7 fields (117 ms) |

The firmware's own counter, over the ~11 s window ending at t=103 s of the
CRSF capture: `fields=673 late=769`, so **1.14 late blocks per field**. 673
fields at 59.94 Hz is 11.2 s, not 10 - the report runs from the IO thread,
which is where the stuck-thread warning below comes from.

For comparison, the round-two bench run
([bench-2026-09-16.md](bench-2026-09-16.md)) blanked ~14,800 of 15,600 blocks
per 10 s once armed, which is the whole overlay. One block per field is a
different regime: the tester now sees characters flickering rather than an
overlay that is not there.

### Superseded 2026-09-19: the one late block per field is a PAL/NTSC bug

Read live over SWD on the bench board (`570a564a8e`, disarmed, no motors):
the scan-out is in **PAL** (`is_pal` 1, 288 lines, 32 blocks) while fields
arrive at 57.9/s from an NTSC camera. `late_blocks` climbs 60.9/s - 1.05 per
field - with `resync_block` at 3, so the late block is block 2, the top half
of row 1, every field; at the top of a field the queue holds blocks 26-28,
PAL rows the NTSC field never reaches. The renderer rendered ahead into
them, the field ended first, and `advance_to(2)` found only stale entries.
`AP_OSD_PICO` defaults to PAL and `OSD_pico::init()` measures the standard
once, for 400 ms at boot, before the FC-powered camera (about 1.3 s to start,
from the reboots above) is sending video; MAX7456 re-checks at runtime and
PICO does not.

So the flight's `late=769` over 673 fields was about 1 block per field of
this bug plus about 0.14 of real lateness, not a renderer still short of
core1. The "about one late block per field" reading above stands as the
measurement; its interpretation does not. The same flight's missing top
half of row 1 is visible in the OCR as "IUI" and "J.C0A" - the bottom
halves of "101" and "3.60A".

Fixed 2026-09-19 by `b95f6d6ef7` (the driver re-measures the field rate and
switches standard from the core1 thread) and `202f47e8bb` (only while
disarmed, since a switch blanks the overlay for a field or two). Confirmed on
the bench board: the row is whole, `is_pal` reads 0 on the NTSC camera, and
disarmed late blocks are 0.03-0.06 per field. See
[bench-2026-09-19.md](bench-2026-09-19.md).

## The losses are block-aligned, so they are the renderer

Character rows that lost exactly one of their two halves, while the other
half was fully drawn: **1595** in the CRSF capture and **2918** in the
MAVLink one, 38% and 50% of all row-loss events. A cut on the 9-line block
boundary, through the middle of the glyphs, is not something a weak analog
link can produce - it is a block that missed its deadline.

Five consecutive fields of the heading and current row at t=69.1 s of the
CRSF capture show it directly: two fields with the row gone, one with only
the top halves of `120` and `9.87` drawn, then two drawn whole. The frame
grabs are in the session scratchpad; they are the tester's footage, so ask
before putting them in this public repo.

## Arming and flying is what costs the renderer

The MAVLink capture opens with 35 s on the ground (frame-to-frame motion at
the noise floor, altitude 0.0 m on screen, pre-arm messages cycling), then
takes off:

| phase | text blocks missing |
|---|---|
| on the ground, t=0-35 s | 3.2-3.9% |
| climb out, t=35-45 s | 7% then 37% |
| in the air, t=65-195 s | 5-30%, typically 10-15% |

Same screen either side - 10.7 text blocks per field on the ground against
11.0 in the air - so this is the load, not the content. It is the flight
version of the bench result that arming takes core1 from 55% to 96%.

## The CRSF session is about twice as bad, and that is not explained

At matched screen content the CRSF capture loses roughly twice the blocks the
MAVLink one does (19.5% against 7.1% on clean-link fields). Same firmware,
same board, same airframe. Candidates, none of them separated here: CRSF
parsing and telemetry cost on core0 (round one measured `rcin` at 7.1% of
core0 with CRSF against 1.8% over MAVLink, and the OSD renderer is on core1,
so the path would have to be indirect), a different flight profile, or a
worse video link inflating the measure. Worth an A/B on the bench, armed at
zero throttle, with only the RC protocol changed.

## What the video measure is worth

In the one window where both exist, the video says 2.55 missing text blocks
per field and the firmware says 1.14. The video over-reads because a marginal
link also removes white pixels: sorting fields by how clean the link was
locally, the MAVLink capture goes from 20.6% missing in the worst windows to
7.1% (0.76 blocks per field) in windows with no dropped frames at all, which
is the same size as the firmware's number.

So: the firmware counter is the measurement of renderer lateness, and the
video is an upper bound on it - but the video is the measurement of what the
pilot actually saw, which includes the link.

## The report's OSD line normally never reaches the screen

Derived from the source, not measured: `GCS::send_textv` calls
`AP_Notify::send_text` inline for every line, and `AP_OSD_Screen::draw_message`
shows whatever is in that single buffer. The 10 s report sends five lines in
one burst, so all but the last are overwritten before the OSD ever redraws,
and the last one is `PIO1 rx= drop= ovr= fe=`. That is what the message row
shows almost everywhere in both captures.

Two report lines were readable only because one burst got spread out in time:
`AP_Logger: stuck thread` at 101.5-103.0 s, then the OSD counters at 103 s.
`send_textv` calls `logger->Write_Message()` before `AP_Notify`, so a blocked
logger spaces the burst out.

Consequence for the next build: with no log pulled, the counter the build
exists to produce is invisible to the tester. Either pace the report lines,
or send the OSD line last, or give the counters their own OSD panel.

## AP_Logger: stuck thread, in flight

One event, CRSF capture, 101.5-103.0 s, in ALT_HOLD. `io_thread_alive()`
wants a heartbeat within 5000 ms, so the logger IO thread was gone for at
least five seconds in the air. The operation name in the message reads as
starting with F, which fits `fsync` but is not certain at this resolution.
Round one saw the same thread stall for ~10 s just after arming on the bench;
this is the first sighting in flight.

## PreArm: DCM Roll/Pitch inconsistent, 3 deg then 33 deg, sitting still

For the first 30 s of the MAVLink capture the aircraft cycles pre-arm
failures, read off the screen and legible by eye at t=20 s:

```
PreArm: DCM Roll/Pitch inconsistent 33 deg. Wait or reboot
```

t=9 s says 3 deg, t=20 s says 33, t=26 s says 31. The frame-to-frame motion
over that whole stretch is at the noise floor and the OSD reads 0.0 m and
0 m/s, so the aircraft was not being moved while the difference grew.

This is F8 reaching the field. `PICO2.py` sets
`AP_AHRS_DCM_BACKUP_DECIMATION 16`, RPI_UAVFC is `MCU PICO2`, and
`AP_AHRS::update()` skips 15 of every 16 DCM updates while EKF3 is primary.
`AP_AHRS_DCM::update()` then integrates whatever single delta angle is
current and runs `drift_correction()` with `_ins.get_delta_time()`, one
sample period, not the 16 that have actually elapsed - so both the rotation
and the correction time base are wrong by that factor. The board has one IMU,
so EKF3 runs one core, so `attitudes_consistent()` takes the
`total_ekf_cores == 1` branch and compares DCM against the primary: the
defect is not merely latent on this board, it is in the arming path.

Mechanism above is derived from the source, not measured. What would settle
it is cheap and worth doing before deciding F8: build RPI_UAVFC with
`AP_AHRS_DCM_BACKUP_DECIMATION 1` and see whether the pre-arm difference
still grows on a bench that is not moving.

## The video losses are the camera rebooting (added 2026-09-18)

The lost fields are two different things. Snow (lum 100, heavy noise) is
RF: short fades, plus the stretches before the VTX is powered and after
landing. Black is the receiver's own digital black (lum 1, std 0.0), so the
carrier was up with no video on it. Apart from a few 1-6 field blips, the
black episodes last 1.25-1.42 s: 18 in the CRSF capture after a 4.9 s one
at t=12.2 s, and 16 from take-off on in the MAVLink capture plus a 5.3 s one
just after it - and none in its 35 s on the ground.

Each one starts with a clean field cut to black at a sharp line, and comes
back the same way every time: two fields in, the camera image is nearly
white (mean lum 97-118 against 73-76 before) while the OSD's black outlines
are still black, so the receiver's levels are right and the camera's
exposure is not; exposure settles over 20-40 fields, the picture stays
monochrome to about +80 fields, and horizontal sync wanders meanwhile. That
is a camera booting, with the VTX and the FC up throughout.

Derived from the source, not measured: the FC holds the 5V and VID rails on
through GPIO18/19 into MP4334 EN pins with 27k pull-downs, exposed as
RELAY2/RELAY3. `AP_Relay::get_pin_state()` called `pinMode(OUTPUT)` on every
read, and on RP2350 `rp_pal_pad_set_mode()` cleared the pin's output enable
while it rewrote mux and pad, with interrupts on - so any relay read
(`RELAY_STATUS` requested by a GCS, a Lua `relay:get()`, `toggle()`) could
float a regulator enable for as long as the thread sat in that gap. Whether
anything was reading relays on these flights is not known.

Fixed as `4723972c44` (ChibiOS, on `rp2350-clean-v7-padmode`: an output
keeps its driver across a mode change) and `5fc3f9a1ff` (AP_Relay: reading
no longer sets the mode; `init()` now writes every relay so the pins still
become outputs at boot), bumped in `43b818a69c`. RPI_UAVFC, CubeOrange and
SITL build with 0 warnings; Rover.ServoRelayEvents and Plane.TestRCRelay
pass, which shows the relay semantics are unchanged but cannot show the
glitch. **Not run on hardware.** Owed: on the bench, request `RELAY_STATUS`
at 50 Hz on `4f982aea88` and then on `43b818a69c`, watching the camera or a
scope on GPIO18/19; and from the tester, `RELAY*`, `RC*_OPTION`,
`SCR_ENABLE`, which GCS was connected, and the log (`RELY` records).

### Relay fix reworked through review (2026-09-18, later)

The AP_Relay half above was reviewed as its own master PR (branch
`pr-relay-read-no-pinmode`, three `/pr-review` rounds with Codex) and
replaced by `de059fb843` "AP_Relay: don't re-apply a relay pin's mode on
every read": a per-pin `Bitmask<256>` sets the mode on a pin's first read
only, and writes keep master's `pinMode()` then `write()`. Rejected, with
reasons, so they are not tried again:

| change | argument for | why rejected |
|---|---|---|
| drop `pinMode()` from reads and force-write every relay in `init()` (the `5fc3f9a1ff` design) | reads stop glitching; `init()` still configures the pins | a `RELAYn_DEFAULT` "no change" relay, or one moved with `RELAYn_PIN` at runtime, is never made an output when its first command matches what the undriven input reads - found independently by a Codex cold read and both Claude reviewers |
| per-pin cache on writes as well as reads | no mode write at all after first use | a pin another feature reconfigures, or whose first sysfs `pinMode()` failed, is never taken back; re-applying on writes (which only happen on a level change) keeps that recovery |
| `pinMode()` on every set, to keep master's "always reclaim" | nothing ever stays with another owner | puts a mode write back on Rover's every-loop `set()` |

Pushed 2026-09-18 as `31df8dcb47` on `andyp1per/pr-relay-read-no-pinmode`
(`de059fb843` plus the `make_output` -> `ensure_output` rename and a
message that says where the fix stops); no PR opened yet.

What the master-side evidence showed, verified in the tree: `GPIO_Sysfs`
writes "out" on every `pinMode()` (kernel ABI: output low), so on Navio2 and
PilotPi a read could switch an ON relay off; `GPIO_RPI_BCM` drops the pin to
an input and back; on ChibiOS STM32 re-applying an output mode never touched
ODR, so there it was never a glitch. The RP2350 branch still carries the old
`e3f489bc73` and needs the new commit in its place.

### Evidence against the mechanism (2026-09-18, later)

The board's own record (`hwdef/RPI_UAVFC/DEVELOPMENT.md`, "The hwdef OUTPUT
HIGH/LOW initial level was ignored on RP2350") has both enables driven *low*
from boot by a since-fixed bug, and says "the 9V rail was observed on in
that state, and no relay command was observed to change it". Neither the
GPIO nor the EN pin was metered, so it is unresolved there too - but if
GPIO19 low does not turn the rail off, a relay read floating it cannot
either, and the float would not explain these reboots. The code fix stands
on its own (the glitch is real in the source); what it does not do yet is
explain the video. The bench test above now has to include metering GPIO19
and the MP4334 EN pin while driving RELAY3, before any reboot is blamed on
it. The same record settles the doc conflict: GPIO19/RELAY3 is the 9V rail,
and it says the mapping was once written backwards - the README and the
hwdef comment above the enables are the stale copies.

One behaviour change, accepted as correct (Andy, 2026-09-18): a relay read
no longer turns a pin back into an output, and a set only reconfigures the
pin when the level has to change. So a pin a script has made an input, or a
relay with `RELAYx_DEFAULT` "no change", stays in its mode until the first
real set. Rejected: forcing `pinMode()` on every set to keep the old
"relay calls always reclaim the pin" behaviour - it puts a mode write back
on every set, which is what caused the spikes seen on STM32.

Still open if the bench does not reproduce it: the production-rev power
tree the hwdef already doubts, the camera connector under vibration, and
motor load on the rail. The board docs also disagree on which GPIO is the
VID rail (README GPIO18; DEVELOPMENT.md and the hwdef pin names GPIO19).

## What this says to do next

1. F8 is now a user-visible arming failure, not a performance trade-off.
   The decimation-1 bench check above, then the decision.
2. Get the report counters somewhere the tester can reach without a log
   (pace the burst, or reorder it, or a panel).
3. Ask again for a `.bin` log. Both of these flights had one on board; the
   OSD counters, `RTDT`, `PM` and the PIO UART stats are all in it.
4. The RC-protocol A/B on the bench for the 2x difference between sessions.
5. The renderer is still short of core1 at ~1 late block per field. Whether
   that is worth more work depends on what the tester now sees - the symptom
   has moved from "no overlay" to "flickering characters".

## Reproduce

```sh
python3 tools/osd_video_blocks.py extract VID3_CRSF.mov blocks_crsf.npz
python3 tools/osd_video_blocks.py report blocks_crsf.npz
python3 tools/osd_video_ocr.py screen VID3_CRSF.mov blocks_crsf.npz
python3 tools/osd_video_ocr.py line VID3_CRSF.mov blocks_crsf.npz 103.0 104.1 6
python3 plots/make_plots.py
```

The videos are the tester's and are not in this repo;
[data/osd-video-2026-09-17.csv](data/osd-video-2026-09-17.csv) carries the
per-10 s aggregates the plot is drawn from.
