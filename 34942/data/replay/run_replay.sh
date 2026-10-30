#!/bin/bash
# Replay each log in a list through one Replay binary.
# usage: run_replay.sh <Replay binary> <file listing one log path per line> <output dir>
# Each log's output goes to <output dir>/<log name>/ (logs/00000001.BIN and replay.out),
# which is the layout score.py reads.
set -u
replay=$(readlink -f "$1"); list=$2; out=$(readlink -f "$3")
while read -r log; do
    [ -z "$log" ] && continue
    n=$(basename "$log" .bin)
    d="$out/$n"; rm -rf "$d"; mkdir -p "$d"
    (cd "$d" && "$replay" "$log" > replay.out 2>&1; echo "exit $?" >> replay.out)
done < "$list"
