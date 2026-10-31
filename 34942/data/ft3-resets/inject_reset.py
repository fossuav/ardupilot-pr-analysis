#!/usr/bin/env python3
"""Scratch only: let Replay repeat a flight's EKF3 bootstrap resets (aux 187).

AP_AHRS::reset_configured_backend() calls NavEKF3::InitialiseFilterBootstrap()
from the RC loop, and the DAL records nothing for it, so Replay diverges at the
first one. This edits AP_DAL::handle_message(RFRF) to call it before the first
EKF3 update frame that starts after each time in REPLAY_EKF3_RESET_US (a comma
separated list of the flight's "EKF bootstrap reset performed" TimeUS values).
The RC loop runs after the fast loop's AHRS update, so the next frame to start
after the message is the first one the flown EKF ran after its reset.
usage: inject_reset.py <tree>
"""
import sys

p = sys.argv[1] + "/libraries/AP_DAL/AP_DAL.cpp"
s = open(p).read()
old = "    if (frame_types & uint8_t(AP_DAL::FrameType::UpdateFilterEKF3)) {\n"
assert s.count(old) == 1
new = """    {
        // ABTEST: repeat the flight's EKF3 bootstrap resets, which the DAL does not record
        static uint64_t abtest_reset_us[8];
        static uint8_t abtest_nreset, abtest_ireset;
        static bool abtest_loaded;
        if (!abtest_loaded) {
            abtest_loaded = true;
            const char *str = getenv("REPLAY_EKF3_RESET_US");
            while (str != nullptr && *str != 0 && abtest_nreset < ARRAY_SIZE(abtest_reset_us)) {
                char *end = nullptr;
                abtest_reset_us[abtest_nreset++] = strtoull(str, &end, 10);
                str = (*end == ',') ? end + 1 : nullptr;
            }
        }
        if ((abtest_ireset < abtest_nreset) && ekf3_init_done &&
            (frame_types & uint8_t(AP_DAL::FrameType::UpdateFilterEKF3)) &&
            (_RFRH.time_us > abtest_reset_us[abtest_ireset])) {
            const bool ok = ekf3.InitialiseFilterBootstrap();
            ::printf("ABTEST EKF3 bootstrap reset at %llu for %llu (%s)\\n", (unsigned long long)_RFRH.time_us,
                     (unsigned long long)abtest_reset_us[abtest_ireset], ok ? "ok" : "not complete");
            abtest_ireset++;
        }
    }
""" + old
s = s.replace(old, new)
if "#include <stdlib.h>" not in s:
    s = s.replace('#include "AP_DAL.h"\n', '#include "AP_DAL.h"\n#include <stdlib.h>\n#include <stdio.h>\n', 1)
open(p, "w").write(s)
print("injected", p)
