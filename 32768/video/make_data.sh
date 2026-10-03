#!/bin/sh
# Extract the CSVs the page and the video are drawn from.
# log12 is a real-flight log and stays out of this repo: pass its path.
# Usage: ./make_data.sh /path/to/log12.bin
set -e
cd "$(dirname "$0")"
X=../../../ardupilot-dist/.claude/skills/log-analyze/log_extract.py
L=../data/arm-only/barodrift_arm.BIN
mkdir -p data
python3 $X extract "$1" --types BARO --condition "BARO.I==0" --fields TimeUS,Alt,Temp,Press --decimate 5 --limit 0 > data/log12_baro.csv
python3 $X extract $L --types XKF1 --condition "XKF1.C==0" --fields TimeUS,PD,VD --decimate 5 --limit 0 > data/sitl_xkf1.csv
python3 $X extract $L --types BARO --condition "BARO.I==0" --fields TimeUS,Alt --decimate 5 --limit 0 > data/sitl_baro.csv
