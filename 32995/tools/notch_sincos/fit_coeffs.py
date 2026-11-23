#!/usr/bin/env python3
"""Fit sin(x) = x*(1 + x^2*P(x^2)) and cos(x) = 1 + x^2*Q(x^2) on [0, pi/4].

Minimax by Lawson reweighting of a least squares fit, with the leading term held
at exactly 1 so that sin stays relatively accurate near zero and cos(0) is 1.
Coefficients are then rounded to float, and the error reported after rounding.
"""
import numpy as np

N = 6001
xs = (np.pi / 8) * (1 - np.cos(np.linspace(0, np.pi, N)))
xs = xs[xs > 0]


def lawson(basis, target, iterations=400):
    w = np.ones_like(target) / len(target)
    best = None
    best_err = np.inf
    for _ in range(iterations):
        sw = np.sqrt(w)
        c, *_ = np.linalg.lstsq(basis * sw[:, None], target * sw, rcond=None)
        e = np.abs(basis @ c - target)
        if e.max() < best_err:
            best_err, best = e.max(), c.copy()
        w = w * (e + 1e-30)
        w /= w.sum()
    return best


def report(name, c, fn, leading):
    cf = np.array(c, dtype=np.float32).astype(np.float64)
    x2 = xs * xs
    poly = np.zeros_like(xs)
    for a in cf[::-1]:
        poly = poly * x2 + a
    value = leading(xs, poly)
    print(f'{name}: degree terms {len(cf)}, max abs error after float rounding {np.abs(value - fn(xs)).max():.2e}')
    print('   ', ', '.join(f'{float(np.float32(a)):.9e}f' for a in cf))


x2 = xs * xs
for terms in (2, 3, 4):
    # sin(x) - x = x^3 * P(x^2)
    basis = np.column_stack([xs**3 * x2**k for k in range(terms)])
    c = lawson(basis, np.sin(xs) - xs)
    report('sin', c, np.sin, lambda x, p: x + x**3 * p)
for terms in (2, 3, 4, 5):
    # cos(x) - 1 = x^2 * Q(x^2)
    basis = np.column_stack([x2 * x2**k for k in range(terms)])
    c = lawson(basis, np.cos(xs) - 1)
    report('cos', c, np.cos, lambda x, p: 1 + x2 * p)
