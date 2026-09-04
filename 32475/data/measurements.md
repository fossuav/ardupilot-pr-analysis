# SITL measurements (branch f1ed87b9c1, throwaway harness in scratch worktree)

## HarnessCarrierDrop - THROW_DROP_CNF=1.0 (the value THROW_DROP_CNF's own doc
## recommends for carrier drops), MOT_SPOOL_TIME=2.0 (top of SPOOL_TIME range)
detected=yes
freefall_lost_count=1        <- new spool-up re-check aborted the recovery
recovered=no                 <- "Throw height achieved" never arrived
final_alt=-0.0               <- vehicle fell to the ground with motors shut down

## HarnessDropAltProfile - THROW_ALT_DCSND at its shipped default of 1.0 m
release_alt=55.58
lowest_alt=52.97             <- fell 2.61 m below release
settled_alt=54.32
total_loss=1.25              <- matches "DCSND below release", not the doc's
                                "freefall + uprighting + this value / 5-10 m"
climb_back=1.35              <- vehicle climbed 1.35 m back up after arrest

## HarnessSrcSetLeak - THROW_SRC_INI=2, THROW_SRC_SET left at default 0
restore_msgs=0
completion_switch_msgs=0
loiter_accepted_after_throw=False   <- still on the no-aiding source set after
                                       the throw completed; LOITER refused
(also: entering THROW while disarmed with SRC_INI pointing at a no-aiding set
 blocked wait_ready_to_arm entirely until the harness was reordered)

## HarnessSpunInHand - NOT REPRODUCED
spun_in_hand_detected=False
Provocation too weak: SITL will not spin a grounded vehicle, and it has no
"held in the hand" state. The analytic envelope stands on the arithmetic only.

## After the fixes (2026-09-04)

Same provocations, run against the fixed tree:

- ThrowDropLongFall (was HarnessCarrierDrop): 0 "freefall lost", "Throw
  detected" -> "Throw height achieved, good position" -> ALT_HOLD. Recovers.
- ThrowSrcInitRestoredOnCompletion (was HarnessSrcSetLeak): "Throw: restored
  EKF Source Set 1" received, LOITER accepted afterwards.

## Gate teeth check

Rebuilt with drop_body_in_freefall() neutered to a plain 0.5g check:

  ThrowSpinDrop        PASSES  -> covers the earth-frame OR-gate
  ThrowSpinTumbleDrop  FAILS   -> covers the body-frame spin ceiling

Measured from the ThrowSpinTumbleDrop dataflash log: peak |gyro| 23.67 rad/s
(1356 deg/s); 70 IMU samples where only the spin-scaled cap admits freefall
against 6 where a plain 0.5g gate does.
