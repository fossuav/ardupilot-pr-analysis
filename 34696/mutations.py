"""Remove one term of the #34696 EKF failsafe mode restore at a time, rebuild,
rerun test.Copter.EKFFailsafeRestoreMode, and report which subtest failed.

Usage: python3 mutations.py <worktree at the PR head> <log dir> [variant...]
Run with .claude/skills/autotest copied into the worktree. The originals are
written back and rebuilt at the end, pass or fail."""
import os, re, subprocess, sys
wt = sys.argv[1]; out = sys.argv[2]
files = {'ekf': 'ArduCopter/ekf_check.cpp', 'rc': 'ArduCopter/RC_Channel_Copter.cpp'}
orig = {k: open(os.path.join(wt, v)).read() for k, v in files.items()}
V = {
    'no_restore': [('ekf', "    if (!ekf_check_state.restore_pending) {\n        return;\n    }\n", "    if (true) {\n        return;\n    }\n")],
    'no_allowlist': [('ekf', "(mode_before == Mode::Number::LOITER || mode_before == Mode::Number::POSHOLD) &&", "true &&")],
    'no_cap': [('ekf', "        ekf_check_state.restore_count < EKF_FAILSAFE_RESTORE_MAX) {", "        true) {")],
    'no_count_reset': [('ekf', "        ekf_check_state.restore_count = 0;\n", "")],
    'no_thresh_cancel': [('ekf', "        ekf_check_state.restore_pending = false;   // a restore needs the checks\n", "")],
    'no_option': [('ekf', "!failsafe_option(FailsafeOption::EKF_RESTORE_MODE) || ap.land_complete", "ap.land_complete")],
    'no_land_complete': [('ekf', "!failsafe_option(FailsafeOption::EKF_RESTORE_MODE) || ap.land_complete ||", "!failsafe_option(FailsafeOption::EKF_RESTORE_MODE) ||")],
    'no_land': [('ekf', "        flightmode->mode_number() == Mode::Number::LAND ||\n", "")],
    'no_last_reason': [('ekf', " ||\n        _last_reason != ModeReason::EKF_FAILSAFE) {", ") {")],
    'reason_only': [('ekf', "_last_reason != ModeReason::EKF_FAILSAFE) {", "get_control_mode_reason() != ModeReason::EKF_FAILSAFE) {")],
    'no_aux_cancel': [('rc', "        copter.failsafe_ekf_restore_cancel(mode);\n", "")],
    'no_any_failsafe': [('ekf', "    if (any_failsafe_triggered() || ekf_check_state.fail_count != 0 || !hands_off) {", "    if (ekf_check_state.fail_count != 0 || !hands_off) {")],
    'no_restart': [('ekf', "    if (any_failsafe_triggered() || ekf_check_state.fail_count != 0 || !hands_off) {\n        ekf_check_state.restore_start_ms = 0;\n", "    if (any_failsafe_triggered() || ekf_check_state.fail_count != 0 || !hands_off) {\n")],
    'no_roll': [('ekf', "                           is_zero(channel_roll->norm_input_dz()) &&\n", "")],
    'no_pitch': [('ekf', " &&\n                           is_zero(channel_pitch->norm_input_dz());", ";")],
    'no_delay': [('ekf', "    if (now_ms - ekf_check_state.restore_start_ms < EKF_FAILSAFE_RESTORE_DELAY_MS) {\n        return;\n    }\n", "")],
}
only = sys.argv[3:]
def write_all(state):
    for k, v in files.items():
        open(os.path.join(wt, v), 'w').write(state[k])
try:
    for name, edits in V.items():
        if only and name not in only:
            continue
        st = dict(orig)
        for k, old, new in edits:
            assert st[k].count(old) == 1, (name, old[:50])
            st[k] = st[k].replace(old, new)
        write_all(st)
        b = subprocess.run(['./waf', 'copter'], cwd=wt, capture_output=True, text=True)
        if b.returncode != 0:
            print(name, 'BUILD FAILED'); print(b.stdout[-1500:]); continue
        log = os.path.join(out, 'restore_mutation_%s.log' % name)
        with open(log, 'w') as f:
            r = subprocess.run(['python3', '.claude/skills/autotest/run_autotest.py', '--timeout', '2400',
                                'test.Copter.EKFFailsafeRestoreMode'], cwd=wt, stdout=f, stderr=subprocess.STDOUT)
        leg, exc = '?', ''
        for l in open(log).read().splitlines():
            m = re.search(r'---------- (.*?)  -', l)
            if m:
                leg = m.group(1)
            if 'Exception caught' in l and not exc:
                exc = l.split('Exception caught:')[-1].strip()[:90]
                break
        print('%-15s exit %d  failed in: %s | %s' % (name, r.returncode, leg if r.returncode else '-', exc), flush=True)
finally:
    write_all(orig)
    subprocess.run(['./waf', 'copter'], cwd=wt, capture_output=True)
    print('restored originals and rebuilt', flush=True)
