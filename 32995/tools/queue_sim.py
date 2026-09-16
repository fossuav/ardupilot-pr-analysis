#!/usr/bin/env python3
'''
Model of the OSD_pico block queue: advance_to() in the completion interrupt
and the renderer loop in core1_thread(), old and new. The renderer gets a
random number of render slots per block tick to stand in for core1
starvation. Reports the fraction of non-blank blocks sent late.
'''
import random

BLOCKS = 26


class Sim:
    def __init__(self, resync, skip_blank, blank_set):
        self.resync = resync
        self.skip_blank = skip_blank
        self.blank = blank_set
        self.queue = []          # block ids, oldest first, max 2 waiting
        self.next_render = 0
        self.resync_block = 0
        self.late = 0
        self.late_seen = 0
        self.nonblank = 0
        self.blank_sent = 0

    def is_blank(self, b):
        return self.skip_blank and b in self.blank

    def advance_to(self, block):
        if self.is_blank(block):
            self.blank_sent += 1
            return
        self.nonblank += 1
        while self.queue and self.queue[0] != block:
            self.queue.pop(0)
        if not self.queue:
            if self.resync:
                self.resync_block = (block + 1) % BLOCKS
            self.late += 1
            return
        self.queue.pop(0)

    def render(self, slots):
        while slots > 0 and len(self.queue) < 2:
            if self.resync and self.late_seen != self.late:
                self.late_seen = self.late
                self.next_render = self.resync_block
            skipped = 0
            while skipped < BLOCKS and self.is_blank(self.next_render):
                self.next_render = (self.next_render + 1) % BLOCKS
                skipped += 1
            if skipped == BLOCKS:
                break
            self.queue.append(self.next_render)
            self.next_render = (self.next_render + 1) % BLOCKS
            slots -= 1


def run(resync, skip_blank, supply, ticks=200000, seed=1):
    rng = random.Random(seed)
    # a typical screen: text on 5 of 13 rows, both halves
    blank = set(range(BLOCKS)) - {0, 1, 4, 5, 12, 13, 20, 21, 24, 25}
    s = Sim(resync, skip_blank, blank)
    block = 0
    for _ in range(ticks):
        # renderer work available this tick, in blocks: mean `supply`
        slots = int(supply) + (1 if rng.random() < supply - int(supply) else 0)
        s.render(slots)
        s.advance_to(block)
        block = (block + 1) % BLOCKS
    return 100.0 * s.late / max(s.nonblank, 1)


print("renderer supply (blocks of render work per block tick) vs late %% of non-blank blocks")
print("%7s %12s %12s %14s %14s" % ("supply", "old", "resync", "skip-blank", "both"))
for supply in (0.3, 0.6, 0.9, 1.0, 1.1, 1.5, 2.0, 3.0):
    print("%7.1f %11.1f%% %11.1f%% %13.1f%% %13.1f%%" % (
        supply, run(False, False, supply), run(True, False, supply),
        run(False, True, supply), run(True, True, supply)))
