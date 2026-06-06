# ardupilot-pr-analysis

Analysis of in-flight ArduPilot PRs.

Each PR has its own subdirectory named by PR number, containing a `README.md`
orientation (read that first), the write-up, plots, and the SITL data needed to
reproduce them. A fresh reader should be able to open `<pr-number>/README.md`
and pick up the full state of that PR's investigation.

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
| [32768](32768/) | Clear baro temperature drift on arming (ArduCopter/EKF3) | arm-only design; periodic alternative explored and rejected |
| [33338](33338/) | Periodic height-only datum reset (prototype) | experiment; reinforces arm-only (see 32768) |
| [33318](33318/) | AC_Loiter drag/feed-forward consistency fix | SITL + vehicle confirmed; forensic agreement with reviewer root cause |
