'''Insert a throwaway A/B harness into a scratch tree's Tools/autotest/arducopter.py.

usage: python3 insert_harness.py <tree> <harness .txt> <method name>

The harness goes in front of EK3_ZeroVelFusionNotUsedWithGPS and is registered
after EK3HardLandingRearm in tests1e. Never run this on a branch that will be
pushed; git checkout -- Tools/autotest/arducopter.py removes it.
'''
import sys

tree, harness_path, name = sys.argv[1:4]
path = tree + "/Tools/autotest/arducopter.py"
src = open(path).read()
anchor = "    def EK3_ZeroVelFusionNotUsedWithGPS(self):"
reg = "            self.EK3HardLandingRearm,\n"
assert src.count(anchor) == 1 and src.count(reg) == 1
src = src.replace(anchor, open(harness_path).read().rstrip() + "\n\n" + anchor)
src = src.replace(reg, reg + "            self.%s,\n" % name)
open(path, "w").write(src)
