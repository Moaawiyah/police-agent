"""Tuning constants for `belief.py`'s update pipeline, split out to keep that
file -- the pipeline itself -- under the project's line budget. Re-exported
from `belief.py` (`from .belief_defaults import DEFAULT_SMELL_TRUST, ...`) so
existing `from police_agent.strategy.belief import DEFAULT_SMELL_TRUST`
imports elsewhere in the codebase keep working unchanged.
"""

# Weight a scent reading carries against the prior -- private, lives in game.toml, not agreed.
DEFAULT_SMELL_TRUST = 4.0

# Convexity of intensity->likelihood curve; above 1 a faint (relative to this reading's own
# peak) cell is starved harder than a fresh one.
DEFAULT_SMELL_POWER = 3.0

# Sliver of the posterior re-mixed to uniform each observation. Consecutive scent readings
# are the same decaying trail sampled again -- without this a cell stays overweighted.
DEFAULT_LEAK = 0.03

# Extra multiplicative shrink applied, every observation, to any cell that did
# NOT clear the support bar this turn (see DEFAULT_STALE_SUPPORT). 1.0 disables
# it -- an unsupported cell is then untouched here, today's behaviour. A cell
# that stays unsupported for several turns in a row gets this applied each of
# those turns, so it compounds (stale_decay**n) with no separate counter needed
# -- repeatedly multiplying is the compounding. Kept as a direct shrink on the
# cell itself (not a change to _leak_toward_uniform's rate) so it rides the same
# single normalize() the boost step already relies on, rather than needing its
# own -- an earlier version that scaled the *leak rate* per cell instead broke
# leak's mass-conservation and, once renormalized, was pulling stale cells back
# UP through the same global rescale that repairs the total; this shrinks
# straight into the numerator, which normalize() then divides through cleanly.
# Swept on BeliefGrid(7): one strong hit at (3,3), then real evidence at a
# fixed far cell (0,0) every turn for 30 turns, reading the (0,0)/(3,3) ratio:
# 1.0->522, 0.9->596, 0.85->635, 0.8->675, 0.7->759, 0.5->947 -- monotonic and
# correctly signed at every point. 0.85 is a noticeable-but-not-extreme pick
# (+21.6% over disabled), not a round-number guess.
DEFAULT_STALE_DECAY = 0.85
# The reading (peak-relative within its own packet, same quantity smell_power
# shapes) a cell must clear to count as supported this turn. Below it, staleness
# still ages even though the wire packet lists the cell -- ScentField keeps a
# strong trail listed, if faintly, far longer than one turn, so "still in the
# packet" alone says little about freshness.
DEFAULT_STALE_SUPPORT = 0.1

# Below this the distribution has collapsed; dividing through would amplify float noise.
EPSILON = 1e-9
