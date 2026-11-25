"""The registry's matching key, as rp2350_ramfunc2_sections.sh computes it."""
import re


def key(name):
    """The registry's matching key: drop a decltype return type, the argument list and spaces."""
    if name.startswith("decltype"):
        depth = 0
        for i in range(8, len(name)):
            if name[i] == "(":
                depth += 1
            elif name[i] == ")":
                depth -= 1
                if depth == 0:
                    name = name[i + 1:].lstrip()
                    break
    depth = 0
    for i, c in enumerate(name):
        if c == "<":
            depth += 1
        elif c == ">" and depth:
            depth -= 1
        elif c == "(" and depth == 0:
            name = name[:i]
            break
    return re.sub(r"\s+", "", name)
