#!/usr/bin/env python3
# Measurement-only patch: log XKF5 for every EKF3 core, not just the primary.
import sys
p = sys.argv[1] + '/libraries/AP_NavEKF3/AP_NavEKF3_Logging.cpp'
s = open(p).read()
old = ("void NavEKF3_core::Log_Write_XKF5(uint64_t time_us) const\n{\n"
       "    if (core_index != frontend->primary) {\n"
       "        // log only primary instance for now\n"
       "        return;\n"
       "    }\n\n")
new = "void NavEKF3_core::Log_Write_XKF5(uint64_t time_us) const\n{\n"
assert s.count(old) == 1
open(p, 'w').write(s.replace(old, new))
