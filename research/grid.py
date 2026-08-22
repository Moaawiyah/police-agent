"""The swept ranges, and the value each constant actually ships with.

Ranges bracket the shipped value on both sides rather than starting at it: a
sweep that only looked upward could not tell "well chosen" from "as low as we
ever tried". Where a constant has a natural boundary the range includes it --
`leak = 0.0` disables the leak, `stale_decay = 1.0` disables staleness,
`WIDE_REACH = 0` forbids every wall -- because the clearest evidence a mechanism
earns its place is what happens with it switched off.
"""

# name -> (values, shipped default)
BELIEF = {
    "smell_trust": ([0.5, 1.0, 2.0, 4.0, 8.0, 16.0], 4.0),
    "smell_power": ([1.0, 2.0, 3.0, 4.0, 6.0], 3.0),
    "leak": ([0.0, 0.01, 0.03, 0.08, 0.15], 0.03),
    "stale_decay": ([0.5, 0.7, 0.85, 0.95, 1.0], 0.85),
    "stale_support": ([0.0, 0.05, 0.1, 0.2, 0.4], 0.1),
}

STRATEGY = {
    "TOP_K": ([1, 2, 3, 5, 8], 3),
    "ESCAPE_WEIGHT": ([0.0, 0.25, 0.5, 1.0, 2.0], 0.5),
    "WIDE_REACH": ([0, 1, 2, 3, 4, 6, 12], 4),
    "MIN_GAIN_FRACTION": ([0.1, 0.22, 0.35, 0.5], 0.22),
    "MIN_GAIN_FLOOR": ([1, 2, 4, 8], 2),
}
