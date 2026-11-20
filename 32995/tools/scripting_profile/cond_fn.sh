cond() {
    local tag=$1
    $M window $R $tag 32 > $R/${tag}_window.out 2>&1 &
    local wpid=$!
    sleep 6
    python3 $L/pcs.py 0 50000 $R/${tag}_c0.txt
    python3 $L/xipctr.py 3 1 $tag > $R/${tag}_xip.txt
    wait $wpid
    python3 $L/attrib.py $S/prof/arducopter $S/prof/arducopter.map $R/${tag}_c0.txt --top 25 --json $R/${tag}_c0.json > $R/${tag}_c0.report
    echo "== $tag: $(head -1 $R/${tag}_window.out | cut -c1-200)"
    grep -h "^ThreadsV3\|^ArduCopter\|^Scripting\|^idle\|^ISR" $R/${tag}_threads.txt
    sed -n 1p $R/${tag}_c0.report; grep -E "lua_vm|scripting_glue|script_heap|libc_libm" $R/${tag}_c0.report
    cat $R/${tag}_xip.txt | tail -2
    grep "LP n\|^  text: n" $R/${tag}_window.out | head -6
}
