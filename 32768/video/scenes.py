"""Manim scenes for the PR #32768 explainer.

Render all:  manim -qh scenes.py S1 S2 S3 S4 S5 S6 S7
Each scene plays audio/sN.wav and pads to its length from durations.json.
Curves come from data/*.csv, extracted from the real log12 and the SITL
barodrift_arm.BIN in ../data/arm-only.
"""
import csv
import json
from pathlib import Path

from manim import *

HERE = Path(__file__).parent
DUR = json.loads((HERE / "audio" / "durations.json").read_text())

BG = "#0f151b"
INK = "#e3e9ee"
MUTED = "#93a2af"
RULE = "#2a3742"
BARO = "#f0a63a"
PR = "#3cc6d4"
MASTER = "#f0707b"
OK = "#5fcf85"
FONT = "Ubuntu"
MONO = "DejaVu Sans Mono"

config.background_color = BG


def T(s, size=30, color=INK, font=FONT, **kw):
    return Text(s, font=font, font_size=size, color=color, **kw)


def read_csv(name):
    with open(HERE / "data" / name) as f:
        return list(csv.DictReader(f))


def copter(color=INK, scale=1.0):
    arm = Line(LEFT * 0.6, RIGHT * 0.6, color=color, stroke_width=6)
    body = RoundedRectangle(width=0.4, height=0.22, corner_radius=0.06, color=color, fill_color=color, fill_opacity=1)
    props = VGroup(*[Line(LEFT * 0.25, RIGHT * 0.25, color=color, stroke_width=4).move_to(arm.get_end() * s + UP * 0.12) for s in (-1, 1)])
    masts = VGroup(*[Line(arm.get_end() * s, arm.get_end() * s + UP * 0.12, color=color, stroke_width=4) for s in (-1, 1)])
    return VGroup(arm, body, masts, props).scale(scale)


class Narrated(Scene):
    key = "s1"

    def setup(self):
        self.add_sound(str(HERE / "audio" / f"{self.key}.wav"))
        self.used = 0.0

    def p(self, *anims, t=1.0, **kw):
        self.play(*anims, run_time=t, **kw)
        self.used += t

    def w(self, t):
        self.wait(t)
        self.used += t

    def finish(self):
        self.wait(max(DUR[self.key] - self.used, 0) + 0.6)


class S1(Narrated):
    key = "s1"

    def construct(self):
        title = T("Baro drift at arm", 64, font=FONT, weight=BOLD)
        sub = T("ArduPilot PR #32768  -  Copter / EKF3", 26, MUTED).next_to(title, DOWN, buff=0.3)
        self.p(Write(title), FadeIn(sub), t=1.6)
        self.w(0.8)
        self.p(VGroup(title, sub).animate.scale(0.5).to_edge(UP), t=0.8)

        ground = Line(LEFT * 5, RIGHT * 5, color=RULE, stroke_width=4).shift(DOWN * 1.6)
        quad = copter(scale=1.4).next_to(ground, UP, buff=0)
        gps = T("waiting for GPS lock...", 26, MUTED).next_to(quad, UP, buff=0.8)
        self.p(Create(ground), FadeIn(quad), t=0.8)
        self.p(FadeIn(gps), t=0.6)

        tube = RoundedRectangle(width=0.35, height=2.4, corner_radius=0.17, color=MUTED).shift(RIGHT * 4 + DOWN * 0.2)
        level = ValueTracker(42)
        fill = always_redraw(lambda: Rectangle(width=0.22, height=2.2 * (level.get_value() - 30) / 40,
                                               color=BARO, fill_color=BARO, fill_opacity=1, stroke_width=0)
                             .align_to(tube, DOWN).shift(UP * 0.1).set_x(tube.get_x()))
        temp = always_redraw(lambda: T(f"{level.get_value():.0f} C", 28, BARO, font=MONO).next_to(tube, LEFT, buff=0.3))
        self.add(tube, fill, temp)
        self.p(level.animate.set_value(62), quad.animate.set_color(BARO), t=3.4)
        self.finish()


class S2(Narrated):
    key = "s2"

    def construct(self):
        rows = read_csv("log12_baro.csv")
        pts = [(float(r["time_s"]), float(r["Alt"]), float(r["Temp"])) for r in rows]

        ax = Axes(x_range=[0, 210, 50], y_range=[-1.4, 0.3, 0.2], x_length=10.5, y_length=5,
                  axis_config={"color": MUTED, "include_tip": False}).shift(DOWN * 0.3)
        yl = VGroup(*[T(f"{v:+.1f}" if v else "0.0", 18, MUTED, font=MONO).next_to(ax.c2p(0, v), LEFT, buff=0.15)
                      for v in (0.0, -0.4, -0.8, -1.2)])
        xl = VGroup(*[T(f"{s} s", 18, MUTED, font=MONO).next_to(ax.c2p(s, -1.4), DOWN, buff=0.15) for s in (0, 50, 100, 150, 200)])
        head = T("Real 5-inch quad on the bench, motors off  (log12)", 26).to_edge(UP)
        ylab = T("height, m", 20, MUTED).next_to(ax, UP, buff=0.1).align_to(ax, LEFT)
        self.p(FadeIn(head), Create(ax), FadeIn(yl), FadeIn(xl), FadeIn(ylab), t=1.4)

        truth = DashedLine(ax.c2p(0, 0), ax.c2p(206, 0), color=INK, stroke_width=2)
        truth_l = T("where the quad actually is", 20, INK).next_to(ax.c2p(206, 0), UP, buff=0.1).align_to(ax.c2p(206, 0), RIGHT)
        self.p(Create(truth), FadeIn(truth_l), t=0.8)

        baro = ax.plot_line_graph([p[0] for p in pts], [p[1] for p in pts], line_color=BARO,
                                  add_vertex_dots=False, stroke_width=4)
        t = ValueTracker(0)

        def at(tv):
            best = pts[0]
            for p in pts:
                if p[0] <= tv:
                    best = p
            return best
        readout = always_redraw(lambda: VGroup(
            T(f"baro: {at(t.get_value())[1]:+.2f} m", 26, BARO, font=MONO),
            T(f"board: {at(t.get_value())[2]:.1f} C", 26, MUTED, font=MONO),
        ).arrange(DOWN, aligned_edge=LEFT).move_to(ax.c2p(150, -0.45)))
        self.add(readout)
        self.play(Create(baro, rate_func=linear), t.animate(rate_func=linear).set_value(206), run_time=8.0)
        self.used += 8.0

        end = ax.c2p(205, pts[-1][1])
        brace = BraceBetweenPoints(ax.c2p(206, 0), end, direction=RIGHT, color=BARO)
        lab = T("1.17 m", 30, BARO, font=MONO, weight=BOLD).next_to(brace, RIGHT, buff=0.1)
        self.p(GrowFromCenter(brace), FadeIn(lab), t=0.8)
        self.finish()


class S3(Narrated):
    key = "s3"

    def construct(self):
        head = T("ArduPilot today: GPS fix, home already set", 30, MASTER).to_edge(UP)
        self.p(FadeIn(head), t=0.8)

        sea = Line(LEFT * 6, LEFT * 0.5, color=RULE).shift(DOWN * 2.8)
        sea_l = T("sea level", 18, MUTED).next_to(sea, DOWN, buff=0.1).align_to(sea, LEFT)
        ground = Line(LEFT * 6, LEFT * 0.5, color=INK, stroke_width=4).shift(UP * 0.2)
        quad = copter(scale=1.0).next_to(ground, UP, buff=0).shift(LEFT * 3.2)
        self.p(Create(sea), FadeIn(sea_l), Create(ground), FadeIn(quad), t=1.2)

        home = Dot(color=MASTER, radius=0.12).move_to(quad.get_bottom() + DOWN * 1.1)
        home_l = T("home, as filed", 20, MASTER).next_to(home, RIGHT, buff=0.2)
        arrow = Arrow(quad.get_bottom(), home.get_center(), buff=0.05, color=MASTER, stroke_width=4)
        gap = T("drift: 1.17 m", 20, MASTER, font=MONO).next_to(arrow, LEFT, buff=0.2)
        self.w(2.5)
        self.p(GrowArrow(arrow), FadeIn(home), FadeIn(home_l), FadeIn(gap), t=1.4)

        screen = RoundedRectangle(width=4.6, height=1.5, corner_radius=0.1, color=MUTED).move_to(RIGHT * 3.3 + UP * 1.6)
        alt = T("ALT  0.00 m", 40, INK, font=MONO).move_to(screen)
        cap = T("ground station", 18, MUTED).next_to(screen, UP, buff=0.1)
        self.w(1.5)
        self.p(Create(screen), FadeIn(cap), Write(alt), t=1.4)
        tick = T("looks right", 22, OK).next_to(screen, DOWN, buff=0.15)
        self.p(FadeIn(tick), t=0.5)
        self.w(1.5)

        items = VGroup(*[T(s, 24, INK) for s in ("height above sea level: off by 1.17 m",
                                                 "terrain following",
                                                 "altitude fences",
                                                 "comparison with GPS altitude")]
                       ).arrange(DOWN, aligned_edge=LEFT, buff=0.28).move_to(RIGHT * 3.3 + DOWN * 1.3)
        items[0].set_color(MASTER)
        for it in items:
            self.p(FadeIn(it, shift=RIGHT * 0.2), t=0.7)
        self.finish()


class S4(Narrated):
    key = "s4"

    def construct(self):
        ekf = read_csv("sitl_xkf1.csv")
        ts = [float(r["time_s"]) for r in ekf]
        h = [-float(r["PD"]) for r in ekf]
        vd = [float(r["VD"]) for r in ekf]

        head = T("This PR: re-zero the height at every arm", 30, PR).to_edge(UP)
        sub = T("SITL, 9.5 m of drift injected (stress case)", 20, MUTED).next_to(head, DOWN, buff=0.15)
        self.p(FadeIn(head), FadeIn(sub), t=1.0)

        ax = Axes(x_range=[0, 86, 20], y_range=[-1, 10, 2], x_length=10.5, y_length=3.2,
                  axis_config={"color": MUTED, "include_tip": False}).shift(UP * 0.3)
        ax2 = Axes(x_range=[0, 86, 20], y_range=[-0.35, 0.05, 0.1], x_length=10.5, y_length=1.6,
                   axis_config={"color": MUTED, "include_tip": False}).next_to(ax, DOWN, buff=0.45)
        l1 = T("EKF height, m", 20, PR).next_to(ax, UP, buff=0.05).align_to(ax, LEFT)
        l2 = T("EKF vertical speed (down), m/s", 20, MASTER).next_to(ax2, UP, buff=0.05).align_to(ax2, LEFT)
        yl = VGroup(*[T(str(v), 16, MUTED, font=MONO).next_to(ax.c2p(0, v), LEFT, buff=0.12) for v in (0, 4, 8)],
                    *[T(f"{v:.1f}", 16, MUTED, font=MONO).next_to(ax2.c2p(0, v), LEFT, buff=0.12) for v in (0.0, -0.3)])
        self.p(Create(ax), Create(ax2), FadeIn(l1), FadeIn(l2), FadeIn(yl), t=1.2)

        arm_i = next(i for i, t in enumerate(ts) if t > 79.8)
        pre_h = ax.plot_line_graph(ts[:arm_i], h[:arm_i], line_color=PR, add_vertex_dots=False, stroke_width=4)
        pre_v = ax2.plot_line_graph(ts[:arm_i], vd[:arm_i], line_color=MASTER, add_vertex_dots=False, stroke_width=3)
        self.play(Create(pre_h, rate_func=linear), Create(pre_v, rate_func=linear), run_time=6.0)
        self.used += 6.0

        phantom = T("phantom descent  -0.29 m/s", 20, MASTER, font=MONO).next_to(ax2.c2p(48, -0.30), LEFT, buff=0.2)
        self.p(FadeIn(phantom), t=0.6)
        self.w(1.6)

        armx = ax.c2p(79.8, 0)[0]
        arm_line = DashedLine([armx, ax.get_top()[1], 0], [armx, ax2.get_bottom()[1], 0], color=INK)
        arm_l = T("ARM", 24, INK, weight=BOLD).next_to(arm_line, UP, buff=0.05)
        self.p(Create(arm_line), FadeIn(arm_l), t=0.6)
        post_h = ax.plot_line_graph(ts[arm_i - 1:], h[arm_i - 1:], line_color=PR, add_vertex_dots=False, stroke_width=4)
        post_v = ax2.plot_line_graph(ts[arm_i - 1:], vd[arm_i - 1:], line_color=MASTER, add_vertex_dots=False, stroke_width=3)
        self.p(Create(post_h), Create(post_v), t=0.8)
        flash = Circle(radius=0.35, color=PR).move_to(ax.c2p(80.5, 0))
        self.p(Create(flash), t=0.4)
        one = T("one sample", 22, PR).next_to(ax.c2p(80, 0), LEFT, buff=0.4).shift(UP * 0.35)
        self.p(FadeIn(one), FadeOut(flash), t=0.6)
        self.w(3.0)
        after = T("after arm: |speed| < 0.015 m/s", 20, OK, font=MONO).next_to(ax2, DOWN, buff=0.15).align_to(ax2, RIGHT)
        self.p(FadeIn(after), t=0.6)
        self.finish()


class S5(Narrated):
    key = "s5"

    def construct(self):
        head = T("Every arm means a second problem", 30).to_edge(UP)
        self.p(FadeIn(head), t=0.8)

        hill = VMobject(color=INK, stroke_width=4).set_points_as_corners(
            [LEFT * 6 + UP * 1.0, LEFT * 2.5 + UP * 1.0, LEFT * 0.5 + DOWN * 2.0, RIGHT * 6 + DOWN * 2.0])
        sea = Line(LEFT * 6, RIGHT * 6, color=RULE).shift(DOWN * 3.0)
        origin = VGroup(Triangle(color=BARO, fill_opacity=1).scale(0.18).rotate(PI), T("EKF origin", 20, BARO))
        origin[1].next_to(origin[0], UP, buff=0.1)
        origin.next_to(LEFT * 4.5 + UP * 1.0, UP, buff=0.05)
        quad = copter(scale=0.9).next_to(LEFT * 4.5 + UP * 1.0, UP, buff=0).shift(RIGHT * 1.2)
        self.p(Create(hill), Create(sea), FadeIn(origin), FadeIn(quad), t=1.4)
        self.w(3.0)

        self.p(quad.animate.next_to(RIGHT * 3 + DOWN * 2.0, UP, buff=0), t=2.0)
        descent = DoubleArrow(RIGHT * 4.3 + UP * 1.0, RIGHT * 4.3 + DOWN * 2.0, buff=0, color=MUTED)
        dl = T("came down", 20, MUTED).next_to(descent, RIGHT, buff=0.1)
        self.p(GrowFromCenter(descent), FadeIn(dl), t=0.8)
        self.w(0.6)

        old = T("old reset: move the origin", 22, MASTER).to_edge(LEFT).shift(DOWN * 1.2)
        ghost = origin.copy()
        self.p(FadeIn(old), ghost.animate.next_to(RIGHT * 3 + DOWN * 2.0, UP, buff=1.0).set_color(MASTER), t=1.6)
        jump = T("height above sea level\njumps by the descent", 20, MASTER).next_to(old, DOWN, aligned_edge=LEFT)
        self.p(FadeIn(jump), t=0.8)
        self.w(2.6)

        self.p(FadeOut(ghost), FadeOut(old), FadeOut(jump), t=0.6)
        new = T("now: origin stays put", 22, PR).to_edge(LEFT).shift(DOWN * 1.2)
        new2 = T("drift comes out of\nthe reference height", 20, PR).next_to(new, DOWN, aligned_edge=LEFT)
        new3 = T("with GPS: re-anchored\nto GPS altitude", 18, MUTED).next_to(new2, DOWN, aligned_edge=LEFT)
        self.p(FadeIn(new), Indicate(origin, color=PR), t=1.0)
        self.p(FadeIn(new2), t=0.8)
        self.p(FadeIn(new3), t=0.6)
        self.finish()


class S6(Narrated):
    key = "s6"

    def construct(self):
        head = T("Refused where it would do harm", 30).to_edge(UP)
        self.p(FadeIn(head), t=1.0)
        self.w(0.8)

        cards = VGroup()
        for txt in ("disarmed in the air,\nnot at rest since",
                    "vertical speed\n1 m/s or more",
                    "height not from\nbaro or GPS"):
            box = RoundedRectangle(width=3.6, height=1.6, corner_radius=0.1, color=MUTED)
            lab = T(txt, 24, INK, line_spacing=0.8).move_to(box)
            cards.add(VGroup(box, lab))
        cards.arrange(RIGHT, buff=0.35).shift(UP * 1.2)
        for c in cards:
            stamp = T("REFUSED", 22, MASTER, weight=BOLD).next_to(c, DOWN, buff=0.15)
            self.p(FadeIn(c, shift=UP * 0.2), FadeIn(stamp), t=0.7)
            self.w(1.3)
        self.w(1.0)

        def faller(x, color):
            q = copter(color=color, scale=0.8).move_to([x, -1.2, 0])
            return q
        m_q = faller(-3.2, MASTER)
        p_q = faller(3.2, PR)
        m_l = T("ArduPilot today", 22, MASTER).next_to(m_q, UP, buff=0.3)
        p_l = T("this PR", 22, PR).next_to(p_q, UP, buff=0.3)
        self.p(FadeIn(m_q), FadeIn(p_q), FadeIn(m_l), FadeIn(p_l), t=0.8)
        self.w(1.8)

        vm = ValueTracker(15.6)
        vp = ValueTracker(15.6)
        m_v = always_redraw(lambda: T(f"{vm.get_value():4.1f} m/s down", 26, MASTER, font=MONO).next_to(m_q, DOWN, buff=0.3))
        p_v = always_redraw(lambda: T(f"{vp.get_value():4.1f} m/s down", 26, PR, font=MONO).next_to(p_q, DOWN, buff=0.3))
        self.add(m_v, p_v)
        rearm = T("re-arm while falling", 24, INK).move_to(DOWN * 3.3)
        self.p(FadeIn(rearm), t=0.6)
        self.p(vm.animate.set_value(0.4), m_q.animate.shift(DOWN * 0.15), t=0.25)
        zeroed = T("zeroed", 22, MASTER, weight=BOLD).next_to(m_v, RIGHT, buff=0.2)
        self.p(FadeIn(zeroed), t=0.5)
        self.w(1.6)
        self.p(vp.animate.set_value(0.0), p_q.animate.shift(DOWN * 0.6), rate_func=smooth, t=3.0)
        caught = T("carried through, ALT_HOLD stops the fall", 22, PR).next_to(p_v, DOWN, buff=0.15)
        self.p(FadeIn(caught), t=0.6)
        self.finish()


class S7(Narrated):
    key = "s7"

    def construct(self):
        a = T("Clears drift built up on the ground", 34, PR)
        b = T("In-flight drift: needs a better temperature calibration - a separate fix", 24, MUTED)
        c = T("github.com/ArduPilot/ardupilot/pull/32768", 28, INK, font=MONO)
        g = VGroup(a, b, c).arrange(DOWN, buff=0.6)
        self.p(FadeIn(a, shift=UP * 0.2), t=1.0)
        self.w(1.8)
        self.p(FadeIn(b), t=0.8)
        self.w(3.4)
        self.p(Write(c), t=1.4)
        self.finish()
