# PR #31216 - AP_HAL_ChibiOS: iFlight Borg H7

Analysis archive for [ArduPilot/ardupilot#31216](https://github.com/ArduPilot/ardupilot/pull/31216).
Branch `andyp1per/pr-iflight-borg-h7`. Record started 2026-10-30.

## 2026-10-30: rebuilt on current master, retired define, photos

CI at `758b814166` failed configure-all on this board: master now refuses
`define ALLOW_ARM_NO_COMPASS` ("no longer used", peterbarker's
`6ee4f05b4b`/`5cd59680f8` removed it everywhere; it had been ineffective
since 2019). The line is dropped from the hwdef commit, a no-behaviour
change. At the old base `26c7363f64` master's own AP_BattMonitor
`%d`/uint32_t sysid format fails a ChibiOS build (fixed in master's
`542f492878`), so the branch is rebuilt by cherry-pick onto master
`278a68a57a`; board ID 5290 is still unique, and IFLIGHT_BORG_H7 copter
builds. The README pointed at `blitz_h7_pro.png`, which was never added,
so test_new_boards failed. Andy pointed at iFlight's product page for
photos: the labelled top (all the expansion pads) and the underside
(R1/T1, R2/T2, SCL1/SDA1, T4/R4, M1-M4) were cropped from the gallery onto
white, about 70 KB each, as `iflight_borg_h7_top.jpg` and
`iflight_borg_h7_bottom.jpg`, folded into the hwdef commit. The CI
README check passes locally.

Pushed 2026-10-30 to andyp1per with a lease on the old head: `758b814166`
-> `2f220cecef`.

## 2026-11-02: completed for the released board

Checked against iFlight's released board: the product page specs and the
wiring diagram PDF (`P021105_iFlight Borg H7 FC Wiring diagram_20260604.pdf`,
the product page's download 535). No Betaflight IFLIGHT_BORG_H7 definition is
public (config repo master, 2025.12-config and 4.5-config, PRs, the build
server's target list, unified-targets, GitHub code search), so the voltage
divider could not be checked against one; Andy chose to keep
BATT_VOLT_MULT 11. The board is rated 4-12S, and 11 saturates at 36.3 V.

Changes (branch `sq/31216-1102b`, rebuilt as the three new-board commits on
the same base `278a68a57a`: `46f7587e5e` AP_Bootloader, `830d2c2874`
bootloaders, `c66fffe0a5` hwdef):
- README rewritten from the released specs and pinout; iFlight's labelled
  pinout (cropped from the wiring PDF, 132 KB) replaces the two gallery
  renders. SPA06-003 baro (the SPL06 driver handles it), 32MB SDMMC flash
  (Andy: it was always an SDMMC flash chip, never a card).
- LED strip: `defaults.parm` SERVO13_FUNCTION 120 and
  `DEFAULT_NTF_LED_TYPES 455` (the September bot review's functional gap).
- BATT2 is the second ESC's current (CU2 pad) as a current-only monitor
  (type 31 exists on master); the borrowed battery 1 voltage pin is gone.
- PC4 analog airspeed dropped: no pad on the released board (Andy agreed).
- `RELAY2_DEFAULT 1` and `RELAY3_DEFAULT 1`: relays default to no function,
  and once enabled their default of off would switch the VTX off or the
  camera to Vi2 at every boot.
- `DMA_NOSHARE`/`DMA_PRIORITY` include SPI4 (IMU2). Streams reshuffled but
  nothing lost DMA; the one shared stream (2,7) carries the same four
  peripherals as before.
- `HAL_INS_HIGHRES_SAMPLE 3` (hwdef playbook 7.4, both IMUs ICM42688).
- Bootloader: PD11 CAM_SW driven high like the main firmware; binaries
  rebuilt.
- LOG_FILE_MB_FREE stays 25: logging stops below 8MB free, so on 32MB this
  leaves the next log about 17MB; a lower floor keeps more old logs and cuts
  the next one short. Comment corrected from "500Mb microSD".

IFLIGHT_BORG_H7 copter builds (1.55 MB, no warnings), bootloader builds,
branch conventions and the hwdef-check helper pass (its `.elf` flag is a
gitignored build output).

Pushed 2026-11-02 to andyp1per with a lease: `2f220cecef` -> `c66fffe0a5`. Description posted (the PR had none) and the PR taken out of draft.

## 2026-11-02 (night)

AP-Review round 1 (COMMENT at `c66fffe0a5`): two minors. The bootloader LED moves from PA8 (the LED strip pad) to PE3, the status LED, and the bootloader is rebuilt; the current-scale bench check needs a board. `sq/31216-1102c` head `ba01eac9ac` (three commits, backup `pre-squash/31216-1102`); refresh12 brought to the released-board version (`de64bcd386`, `9e4067f7e0`), and IFLIGHT_BORG_H7 builds there. Pushed 2026-11-02 at `ba01eac9ac`.
