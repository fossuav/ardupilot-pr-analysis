# Squash B, 2026-10-31: #34543, #34630, #34292

Built in the scratch worktree sq-b on new branches
(sq/34543, sq/34630 and sq/34292 already exist from 10-05/10-08 and were
left alone). Nothing pushed. Push plan: push_B.tsv, remote andyp1per, each
row leased on the PR's current head.

Every branch's tree equals its PR head (`git diff <old> <new>` empty). SITL
copter built at every new commit that touches code (rover too on #34292),
MatekH743 copter at the #34543 and #34630 tips: all rc=0, 0 warnings
(build_B.out). `pr_review.py checks`: clean on all three.

## #34543: 351aea9eaa -> sq/34543-1031 31a28194aa (14 -> 12 commits)

The first two commits (7e3f6c8b33, 238d5d9df1) are kept as they are.

- 78aa029352 (AHRS semaphore) folded into cbda421ea8, the lane items.
- 351aea9eaa (SIM_TERRAIN 0) folded into 92767a6d63: all 30 OSDEKFLanes
  lines it sits in are 92767a6d63's.
- d9e4277412, cbda421ea8 and 92767a6d63 reworded with the drafts in
  r1030/DRAFTS.md; cbda421ea8 gains the AHRS-semaphore paragraph and
  92767a6d63 a line on SITL terrain. The 09f2c62741 reword is not used: the
  DCM fix it assumes folded stays on top.
- a2f1de5edd (DCM fix) and its test 003ef442a9 stay on top.
- af50a66828 (flash check) is NOT folded: every line it changes was moved
  into vehicle_test_suite.py by 003ef442a9, which stays on top, so it
  cannot fold into 92767a6d63 without rewriting that move, and folding it
  into the DCM test would tie a general test fix to the DCM fix. It stays
  last, its own commit. (B.md's "92767a6d63 / 17f017fb8c" target did not
  hold for it.)

Old:
   d9e4277412 AP_NavEKF3: report the status of each lane
   09f2c62741 AP_AHRS: pass out the status of each EKF3 lane
   1bb1914cd1 AP_OSD: map the symbols after SYM_LQ for MSP DisplayPort
   cbda421ea8 AP_OSD: show the status of each EKF lane
   92767a6d63 autotest: check the OSD EKF lane items
   78aa029352 AP_OSD: take the AHRS semaphore for the EKF lane items
   edc6cb9dec AP_OSD: show the flow sensor's signal strength on an EKF flow lane
   17f017fb8c autotest: check the flow signal strength on the OSD EKF lane items
   a2f1de5edd AP_AHRS: keep the EKF3 lane status while DCM is active
   003ef442a9 autotest: check the OSD EKF lane items through a DCM fallback
   af50a66828 autotest: have the OSD lane flash check see the text come back
   351aea9eaa autotest: keep SITL terrain out of OSDEKFLanes

New:
   cde70e3602 AP_NavEKF3: report the status of each lane
   f70d27a889 AP_AHRS: pass out the status of each EKF3 lane
   a7acb52718 AP_OSD: map the symbols after SYM_LQ for MSP DisplayPort
   ff54d9bc07 AP_OSD: show the status of each EKF lane
   1356f5f0e1 autotest: check the OSD EKF lane items
   69bbf4c860 AP_OSD: show the flow sensor's signal strength on an EKF flow lane
   e63c2bcbe5 autotest: check the flow signal strength on the OSD EKF lane items
   9c50820487 AP_AHRS: keep the EKF3 lane status while DCM is active
   be83879cb1 autotest: check the OSD EKF lane items through a DCM fallback
   31a28194aa autotest: have the OSD lane flash check see the text come back

## #34630: 9a64b9bc5f -> sq/34630-1031 c63cdfafdd (28 -> 24 on #33484)

#33484 underneath (e0e4a38f57 and its eight) is unchanged, as are the first
two copy commits (d5ac3ff446, 8c0f8058db). This PR carries its own copies of
#34543's first ten commits, on #33484's base and from before #34543's rebase
(no DCM fix, no SIM_TERRAIN fix), so it cannot be restacked onto
sq/34543-1031 and keep its tree. The same squash is applied to those copies
instead:
- dbe769432a folded into a488b89db8, reworded as sq/34543's lane items;
- 9a64b9bc5f (flash check, all 19 lines 60b8bd1d79's) folded into
  60b8bd1d79, reworded as sq/34543's test plus a line on the flash check;
- e5ac04130f reworded as sq/34543's d9e4277412.
Its own commits:
- 32decd38b8 (250 ms comment) folded into e18433d773, message kept.
- f29c794577 (250 ms) folded into afd12ac827, message rewritten for 250 ms
  with the reason.
- 17ead03a5e stays on top, as asked, with everything that depends on it:
  7e63c513bf (extends its condition), a7ac51780b and 6b84dcfeb9 (document
  that behaviour), 057ca0f7d8 and 191ad8c36b (test it). So none of B.md's
  floor folds into 623c5886fa, a67dd5323c or d402ac272a were made.

Old (after e0e4a38f57):
   e5ac04130f AP_NavEKF3: report the status of each lane
   db7fdb8f08 AP_AHRS: pass out the status of each EKF3 lane
   026926e5a5 AP_OSD: map the symbols after SYM_LQ for MSP DisplayPort
   a488b89db8 AP_OSD: show the status of each EKF lane
   60b8bd1d79 autotest: check the OSD EKF lane items
   dbe769432a AP_OSD: take the AHRS semaphore for the EKF lane items
   caeb6f8b27 AP_OSD: show the flow sensor's signal strength on an EKF flow lane
   34af52a8c2 autotest: check the flow signal strength on the OSD EKF lane items
   e18433d773 AP_NavEKF: add flow axis lockout recoveries to the lane status
   afd12ac827 AP_NavEKF3: report which flow axis a velocity reset recovered
   7f2879512e AP_OSD: flash a flow arrow once for the velocity reset recovering it
   20a854705f AP_NavEKF3: add an option to quiet the flow velocity reset messages
   32decd38b8 AP_NavEKF: the lane reports a flow velocity reset for 250 ms
   f29c794577 AP_NavEKF3: report a flow velocity reset for 250 ms rather than 500 ms
   ebd1c5318f autotest: check the quiet option silences flow velocity reset messages
   1c559b90f7 AP_NavEKF: add the flow quality floor to the lane status
   623c5886fa AP_NavEKF3: report the flow quality floor with each lane
   a67dd5323c AP_OSD: show the flow signal strength against the lane's quality floor
   d402ac272a autotest: check the OSD flow signal strength against EK3_FLOW_QMIN
   17ead03a5e AP_NavEKF3: report the flow quality floor only with the AGL KF option
   a7ac51780b AP_OSD: say the EKF lane quality floor needs EK3_OPTIONS bit 3
   057ca0f7d8 autotest: check the OSD shows no flow quality floor without the AGL KF
   7e63c513bf AP_NavEKF3: report the flow quality floor while a lane is latched by it
   191ad8c36b autotest: check the OSD keeps a latched flow quality floor
   6b84dcfeb9 AP_OSD: say the EKF lane quality floor also shows while it holds a lane
   9a64b9bc5f autotest: have the OSD lane flash check see the text come back

New (after e0e4a38f57):
   d35f39cef2 AP_NavEKF3: report the status of each lane
   f13fdac94e AP_AHRS: pass out the status of each EKF3 lane
   acecf9d889 AP_OSD: map the symbols after SYM_LQ for MSP DisplayPort
   752ac5ca05 AP_OSD: show the status of each EKF lane
   9c1d52a13e autotest: check the OSD EKF lane items
   351b387ec0 AP_OSD: show the flow sensor's signal strength on an EKF flow lane
   dad290e40c autotest: check the flow signal strength on the OSD EKF lane items
   ab1d697526 AP_NavEKF: add flow axis lockout recoveries to the lane status
   bbe2c08343 AP_NavEKF3: report which flow axis a velocity reset recovered
   a0e67735df AP_OSD: flash a flow arrow once for the velocity reset recovering it
   8a1f2b0ca3 AP_NavEKF3: add an option to quiet the flow velocity reset messages
   cd0b0a0a5b autotest: check the quiet option silences flow velocity reset messages
   7bc0bdafb6 AP_NavEKF: add the flow quality floor to the lane status
   f9511fee5d AP_NavEKF3: report the flow quality floor with each lane
   4d7aac1ac0 AP_OSD: show the flow signal strength against the lane's quality floor
   b906b91a1e autotest: check the OSD flow signal strength against EK3_FLOW_QMIN
   2dc3040b8a AP_NavEKF3: report the flow quality floor only with the AGL KF option
   1d227c0715 AP_OSD: say the EKF lane quality floor needs EK3_OPTIONS bit 3
   d58d72219c autotest: check the OSD shows no flow quality floor without the AGL KF
   53ebca1e83 AP_NavEKF3: report the flow quality floor while a lane is latched by it
   df5f350561 autotest: check the OSD keeps a latched flow quality floor
   c63cdfafdd AP_OSD: say the EKF lane quality floor also shows while it holds a lane

## #34292: 3917ef38f2 -> sq/34292-1031 3dcdfb487b (27 -> 25 commits)

Everything up to 8cd64105c4 (19b9e2bd9a and its test included) is unchanged.
- 244d608769 + b43ace7296 merged as "AP_NavEKF3: leave the flow focus floor
  out of Rover builds", at 244d608769's place, message rewritten for the net
  change (no bypass ever lands).
- b582cc7fe7 folded into c0498ea0d5, message rewritten for the three Rovers.
- a0ab050ad6, a0e43dce3e and 3917ef38f2 kept as they are (a0e43dce3e and
  3917ef38f2 were optional folds; not made).

Old (after 8cd64105c4):
   244d608769 AP_NavEKF3: keep the focus floor off flow at a declared sensor height
   a0ab050ad6 AP_OpticalFlow: SITL flow from a sensor mounted above the ground
   c0498ea0d5 autotest: check a flow-only Rover keeps its speed over a range finder
   b43ace7296 AP_NavEKF3: leave the flow focus floor out of Rover builds
   a0e43dce3e AP_OpticalFlow: say Rover does not use FLOW_HGT_MIN
   b582cc7fe7 autotest: drive the flow Rover with no declared height and when small
   3917ef38f2 AP_NavEKF3: replay a Rover log without the flow focus floor

New (after 8cd64105c4):
   d5db25eeb0 AP_NavEKF3: leave the flow focus floor out of Rover builds
   215f298a6b AP_OpticalFlow: SITL flow from a sensor mounted above the ground
   88341d1d0d autotest: check a flow-only Rover keeps its speed over a range finder
   663224bbb5 AP_OpticalFlow: say Rover does not use FLOW_HGT_MIN
   3dcdfb487b AP_NavEKF3: replay a Rover log without the flow focus floor
