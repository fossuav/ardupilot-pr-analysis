#!/usr/bin/env python3
"""Install the probes in harness.py into an ArduPilot checkout, and remove them.

The probes are deliberately not committed to the firmware tree: they have no
pass/fail gate, so they are A/B instruments rather than tests. This script is
the paste-and-register step, which is most of the friction in using them.

    python3 install_harness.py /path/to/ardupilot          # install
    python3 install_harness.py /path/to/ardupilot --revert # remove

Then, one invocation per arm of the A/B, collecting the log after each:

    VRF_LEARN=2 VRF_SIM=0.15 VRF_PRE=0.15 \
        Tools/autotest/autotest.py --no-configure test.Copter.VRFArmTransient
    cp "$(ls -S logs/*.BIN | head -1)" somewhere/arm_name.BIN

and read the numbers out with metrics.py.

Gotchas, all of which cost time at least once:

- Build with ./waf, never autotest.py build.*, and rebuild between arms that
  differ in firmware rather than in parameters.
- The probes reboot twice, so logs/ ends up with several BINs. The flight is
  the largest; `ls -S | head -1` picks it. Do not assume it is the last.
- autotest.py wipes logs/ at the start of every step, so collect after each
  arm, not at the end of the sweep.
- self.delay_sim_time() requires a reason argument. Omitting it raises
  TypeError halfway through the run, after the build.
- Multiple tests in one SITL session use comma syntax with the vehicle named
  once: test.Copter.A,B - not test.Copter.A,Copter.B.
- --revert here is just `git checkout -- Tools/autotest/arducopter.py`. It is
  spelled out so a sweep script can undo itself without touching git.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(HERE, "harness.py")
TARGET = os.path.join("Tools", "autotest", "arducopter.py")
MARK_BEGIN = "    # --- A/B harness (installed by install_harness.py) ---\n"
MARK_END = "    # --- end A/B harness ---\n"


def probes():
    """-> (list of names, indented source) for every top-level def in harness.py"""
    src = open(HARNESS).read()
    names = re.findall(r"^def (\w+)\(self\):", src, re.M)
    blocks = re.split(r"^(?=def \w+\(self\):)", src, flags=re.M)[1:]
    body = "".join("".join("    " + ln if ln.strip() else ln
                           for ln in b.splitlines(True)) + "\n" for b in blocks)
    return names, body


def install(root):
    path = os.path.join(root, TARGET)
    src = open(path).read()
    if MARK_BEGIN in src:
        sys.exit("already installed - revert first")
    names, body = probes()

    anchor = "\n    def tests1c(self):\n"
    if src.count(anchor) != 1:
        sys.exit("cannot find tests1c in %s" % path)
    src = src.replace(anchor, "\n" + MARK_BEGIN + body + MARK_END + anchor[1:])

    # register inside tests1c's list, right after it opens
    head = src.index("    def tests1c(self):")
    open_list = src.index("ret = ([", head)
    eol = src.index("\n", open_list) + 1
    src = src[:eol] + "".join("             self.%s,\n" % n for n in names) + src[eol:]

    open(path, "w").write(src)
    print("installed %s into %s" % (", ".join(names), path))


def revert(root):
    path = os.path.join(root, TARGET)
    src = open(path).read()
    if MARK_BEGIN not in src:
        print("not installed")
        return
    src = src[:src.index(MARK_BEGIN)] + src[src.index(MARK_END) + len(MARK_END):]
    names, _ = probes()
    for n in names:
        src = src.replace("             self.%s,\n" % n, "")
    open(path, "w").write(src)
    print("reverted %s" % path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    revert(root) if "--revert" in sys.argv else install(root)
