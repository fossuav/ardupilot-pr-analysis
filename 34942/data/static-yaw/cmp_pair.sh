#!/bin/bash
# cmp_pair.sh: for each log in loglist2.txt, compare out2-nofix against
# out2-fix (cmp_replays.py, replayed core 0) and the per-arm verdicts
# (stale_probe.py "at the arm" lines, in order).
S=/tmp/claude-1000/-home-andy-github-smallfastdrone-beta/c72a7562-fe47-4333-b873-673b10019194/scratchpad/r1030/34942
while read -r log; do
    n=$(basename "$log" .bin)
    a=$S/out2-nofix/$n/logs/00000001.BIN
    b=$S/out2-fix/$n/logs/00000001.BIN
    echo "== $n: $(timeout 900 python3 $S/cmp_replays.py "$log" "$a" "$b" | head -1)"
    timeout 900 python3 $S/stale_probe.py "$log" "$a" > "$S/v_nofix_$n.out" 2>&1
    timeout 900 python3 $S/stale_probe.py "$log" "$b" > "$S/v_fix_$n.out" 2>&1
    na=$(grep -c "at the arm:.*hgt error 1" "$S/v_nofix_$n.out")
    nb=$(grep -c "at the arm:.*hgt error 1" "$S/v_fix_$n.out")
    arms=$(grep -c "at the arm:" "$S/v_nofix_$n.out")
    echo "   arms $arms, height-error refusals: without fix $na, with fix $nb"
    paste -d'#' <(grep "^disarm\|at the arm" "$S/v_nofix_$n.out") <(grep "^disarm\|at the arm" "$S/v_fix_$n.out") |
        awk -F'#' '/^disarm/{d=$1; next} $1!=$2 {print "   " d " | without: " $1 " | with: " $2}' | sed 's/  */ /g'
done < "$S/loglist2.txt"
