#!/usr/bin/env python3
"""replay_fleet.py with XKFA kept as well: fleet_run.py <replay_fleet args>"""
import importlib.util
import sys
spec = importlib.util.spec_from_file_location(
    'replay_fleet', '/home/andy/github/smallfastdrone-beta/.claude/skills/log-analyze/replay_fleet.py')
rf = importlib.util.module_from_spec(spec)
sys.modules['replay_fleet'] = rf
spec.loader.exec_module(rf)
rf.WANT = ('XKF1', 'XKF5', 'GPS', 'MSG', 'XKFA')
sys.argv = ['replay_fleet.py'] + sys.argv[1:]
rf.main()
