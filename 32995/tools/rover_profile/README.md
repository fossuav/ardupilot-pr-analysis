# Rover profiling tools (2026-11-26)

Self-contained copies, for the motorless RPI_UAVFC testbed on COM15. Every
tool listens on TCP 5771, so they can run beside the Plane tools' bridge on
5770. Start `bridge.py COM15 127.0.0.1 5771` with Windows Python, and
OpenOCD as in ../../README.md, then see bench-2026-11-26-rover.md,
"Reproduce".

- `param_dump.py`: every parameter over MAVLink, count-checked, to .parm/.json
- `ekfcheck.py`: feed the fake fix, report EKF3 flags until it has a position
- `rover_session.py`: Plane's `session.py` for Rover: sticks centred,
  throttle held at RC3_TRIM (Rover's stop), mode numbers for Rover
- `rover_summary.py`, `libgroup.py`: where core0's time goes
- `rover_pick.py`: registry lines from the profiles, `[ardurover]` by default
  (`MARK`), `ALL` for every ArduPilot library and vehicle directory
- `rover_ab.py`, `rover_abana.py`: flash A and B in turn and compare
