# ardupilot-pr-analysis

Analysis of in-flight ArduPilot PRs.

Each PR has its own subdirectory named by PR number, containing a `README.md`
orientation (read that first), the write-up, plots, and the SITL data needed to
reproduce them. A fresh reader should be able to open `<pr-number>/README.md`
and pick up the full state of that PR's investigation.

The working rules for editing these records - the evidence cascade, and when
code based on a real flight may be changed - are in [CLAUDE.md](CLAUDE.md).

## Conventions

- One directory per PR, named by number (e.g. `32768/`).
- Each PR directory starts with `README.md` - the summary, conclusion, key
  findings, file map, and reproduction steps.
- `plots/` holds PNGs plus a `make_plots.py` that regenerates them from `data/`.
- `data/` holds only **SITL** logs (no real-flight data). SITL BINs are
  identifiable by their hundreds of `SIM_*` parameters and the CMAC default
  home (-35.36, 149.16); this repo is public, so real flight logs must never be
  committed here.

## PRs

| PR | Topic | State |
|----|-------|-------|
| [32768](32768/) | Clear baro temperature drift on arming (ArduCopter/EKF3) | arm-only design; periodic alternative rejected; self-reviewed 2026-08-29: tolerance gate removed, EKF3 reported-origin fix |
| [33338](33338/) | Periodic height-only datum reset (prototype) | experiment; reinforces arm-only (see 32768) |
| [33318](33318/) | AC_Loiter drag/feed-forward consistency fix | SITL + vehicle confirmed; forensic agreement with reviewer root cause |
| [33359](33359/) | AGL KF for the optical-flow rangefinder height switch | indoor alt-hold divergence; Replay-validated; flight-validated on log281; third and fourth commits need #33507 |
| [32475](32475/) | Throw mode improvements: drop detection, uprighting, yaw, source sets (Copter) | ~30 real drops on six airframes distilled; self-reviewed 2026-09-04 and pushed as 8 commits: drop abort and source-set leak fixed, altitude-target "fix" reverted as the design was right, 9 of 11 old commits panicked at boot; direction-finding yaw unvalidated |
| [32401](32401/) | Pending arm on switch for in-air arming (Copter) | two field cases: retries unclearable failures, resets an EKF that was fine |
| [32514](32514/) | Reset the EKF failsafe gate on a source-set change (Copter) | field before/after; gate re-latches correctly when position returns |
| [32471](32471/) | Hover Z-bias learning for vibration rectification (EKF3/Copter) | approved; SITL A/B 2026-09-04 shows 3x less height error against real VRF, and that bit 2 is about moving platforms not the motors-off bias; needed two new SIM knobs to measure |
| [32472](32472/) | Ground effect altitude and timeout parameters (Copter) | approved; two differences from the flown design recorded |
| [32553](32553/) | Reset terrain offset from baro when ground effect clears (EKF3) | result needs #32472's HAGL check; reset drifts back; likely superseded by #33359 |
| [32972](32972/) | Protect height fusion from baro ground effect at takeoff (EKF3) | 22-flight development record; SITL A/B plots for both behaviour changes; anchor ends at first throttle and can engage in mid-air |
| [33478](33478/) | Fuse AGL KF velocity as a velD observation (EKF3) | three flights, 36 s hands-off at 0.13 m with #33507 at 0.3; SITL A/B confirms the 14x/10x covariance collapse, clip-cycle prediction refuted; param index 12 -> 15; its own autotest A/B arms are unmatched (bit 3 against bit 4) so that number is not attributable to the fusion alone |
| [33484](33484/) | Recover velocity from a single-axis optical-flow lockout (EKF3) | Replay-tuned 500 ms, flown; the near-ground flow floor split out to #34292 on 2026-09-04, and two `SIM_FLOW_OFS` commits are the same patch on both branches |
| [33585](33585/) | Keep optical flow nav alive above the rangefinder range (EKF3) | Replay-validated on log308; guard rewritten twice after review, three terms each with a failing-without-it autotest leg; terrain gate restored after rmackay9 review, merging the option bits open with him; stacked on #33478 |
| [33497](33497/) | FLOW_HF_RATEF for a half-rate HereFlow node | sensor-rate slope 0.52 -> 1.00; not reproducible in SITL |
| [33498](33498/) | Inhibit Z gyro bias from optical flow without a yaw source (EKF3) | flight-validated; no SITL test yet |
| [33507](33507/) | Accel-Z bias state in the AGL KF (EKF3) | bias state right, 0.05 default too stiff: 0.3 flown on two airframes |
| [32270](32270/) | VALT velocity alt-hold mode (rebase + ground idle at mid-stick + ground-effect correction limit) | self-reviewed 2026-09-04: missing avoidance call and an inherited terrain offset fixed, blend now has a SITL A/B; mode number 29 contested, PR prose not yet updated |
| [34208](34208/) | Interpolate the rate target in the fast rate thread | SITL A/B + hardware; opened 2026-08-29 |
| [34209](34209/) | EKF3: no XY accel bias learning in unaided flight | autotest fails on master / passes fixed; opened 2026-08-29 |
| [34210](34210/) | Advanced land failsafe (LAND_FS_OPTIONS bit 0) | design reshaped twice by its SITL runaway test; opened 2026-08-29 |
| [34292](34292/) | Optical flow minimum focus height, FLOW_HGT_MIN (AP_OpticalFlow/EKF3) | split from #33484; two review rounds answered, replay record moved to its own ROFM message after a growth bug, and a SIGFPE this PR introduced fixed; the flown 0.1 m value was checked against the `RNGFNDx_GNDCLR` clamp and cleared it (log67 had GNDCLR=0) |
