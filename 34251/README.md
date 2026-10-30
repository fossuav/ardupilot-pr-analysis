# PR #34251 - Copter, Plane: the INS_HNTC2 conversion defaults (4.7)

Analysis archive for [ArduPilot/ardupilot#34251](https://github.com/ArduPilot/ardupilot/pull/34251).
Branch `andyp1per/pr-static-notch-bug-4.7`, based on ArduPilot-4.7. Record
started 2026-10-30.

## 2026-10-30: reworded to what the diff does

Retargeted to ArduPilot-4.7 and rebased to `64b0c17788` on 2026-10-29.
The bot's round at that head (COMMENT) found the title, both commit
messages and the A/B table describing a save of MODE 0 / HMNCS 1 that
the diff does not make, and "Remove the conversion" describing master,
where 5b8866bedc/f1aff37cbb removed it; on 4.7 the conversion stays.

Measured in Copter SITL with the old fixed notch (ENABLE 1, ATT 30,
FREQ 95, BW 25) written into eeprom.bin under its 4.1 keys (k_param_ins
3, group elements 101/293/357/421; `notch_probe.py` in the session
scratchpad):

    base fbd0a3160c: wiped 0/1, converting boot 0/1, next reboot 1/3
    head 64b0c17788: wiped 1/3, converting boot 1/3, next reboot 1/3

Both store ENABLE, ATT, FREQ and BW and neither MODE nor HMNCS. REF is
not converted, and update_dynamic_notch() holds the notch at FREQ when
REF is 0, so the only filtering change for an upgrader is the 2xFREQ
notch on the first boot, which base gives from the second boot on.

Andy chose rewording over adding the save. Rebuilt by cherry-pick as
`r1030/34251r` (`94a411312f` Copter, `dff8813535` Plane, "stop INS_HNTC2
MODE and HMNCS changing across a reboot"), tree identical to
`64b0c17788`. Description redrafted with the table above.

Andy's decision: reword rather than add the save.

Pushed 2026-10-30 to andyp1per with a lease on the old head: `64b0c17788`
-> `dff8813535`.
