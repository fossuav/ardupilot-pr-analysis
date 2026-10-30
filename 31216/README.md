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
