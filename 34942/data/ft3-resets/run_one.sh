#!/bin/bash
# run_one.sh <Replay binary> <log> <out dir> [reset TimeUS list]
# Replays one log into <out dir>/logs/00000001.BIN, console to <out dir>/replay.out.
set -u
replay=$(readlink -f "$1"); log=$2; out=$3
rm -rf "$out"; mkdir -p "$out"
cd "$out" || exit 2
if [ $# -ge 4 ]; then
    REPLAY_EKF3_RESET_US="$4" "$replay" "$log" > replay.out 2>&1
else
    "$replay" "$log" > replay.out 2>&1
fi
echo "exit $?" >> replay.out
