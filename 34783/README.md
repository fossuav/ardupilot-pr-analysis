# #34783 AP_OpticalFlow: publish PX4Flow frames from the main loop

Opened 2026-10-16 at `c0c1aeab19` on `andyp1per:pr-px4flow-publish`, one
commit on upstream master `5cd59680f8`.

## Why

Found answering AP-Review on #33484: its flow latch could pair a newly set
flag with an old release-run start when a PX4Flow sample arrived on another
core. The PX4Flow backend's `update()` was empty and its I2C `timer()`
called `_update_frontend()` directly, so `AP::ahrs().writeOptFlowMeas()`,
EKF3's `writeOptFlowMeas()` and the DAL's Replay writes all ran on the bus
thread. Concretely: EKF3 zeroed `delAngBodyOF`/`delTimeOF` there while the
main loop accumulated them (`AP_NavEKF3_core.cpp:813`), pushed `storedOF`
there while fusion recalled it, and `AP_DAL::writeOptFlowMeas()` called
`end_frame()` and wrote ROFH mid-frame. None of these was observed; they are
traced in source.

It is the driver-side case of ARCH-18 (aap 1.7.44-1.7.45): a backend's
callback writes only backend state under `_sem`, and the frontend's copy in
the main loop is the only crossing. HereFlow (`new_data` flag) and BMP280
(accumulators) are the precedents cited.

## The change

`timer()` reads the integral frame and stores it, with its read time, under
`_sem`; `update()` takes it under `_sem`, drops it if more than 100 ms old,
and converts and publishes it after releasing the semaphore. The EKF times
a sample at publication, so frames arrive up to one flow update period
later in normal running: 5 ms on Copter and Sub (400 Hz loop, 200 Hz task),
20 ms on Plane and a default Rover (50 Hz loop).

## Review before opening

- Gate clean. Reviewer agent: code correct; message errors fixed (Rover is
  50 Hz by default, not 200; Pixart and PulsedLightLRF do not keep the
  pattern - this also corrected ARCH-18's examples in the playbook).
- Codex cold read: no age check on a buffered frame (added: 100 ms), and
  "no frame is overwritten" too strong (reworded). Codex check of the final
  commit: all four points fixed; latency bound and "10 Hz" wording refined.
- Testing: built for SITL Copter, Plane, Rover and CubeOrange Copter. No SITL
  PX4Flow simulator exists, so not run; not tested on hardware. "Checked by
  a human programmer" left for the author to tick.

## Beta

Carried as SmallFastDrone-4.7.2-beta topup25 and listed in `prs.txt` after
#34292. TD25 uses MAVLink flow, so it does not exercise this.
