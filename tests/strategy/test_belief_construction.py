"""Building a `BeliefGrid` from the agreed terms and this peer's own config.

Split out of test_belief.py to keep both files inside the 150-line rule. The
board size is a signed, agreed term; trust/power/leak/staleness are private
tuning read from this peer's own config, each falling back to the shipped
default when unset.
"""

from police_agent.peer.terms import terms_from_config
from police_agent.strategy.belief import BeliefGrid
from tests.conftest import config_with


class TestConstruction:
    def test_it_takes_the_board_from_the_agreed_terms_and_trust_from_the_private_file(self):
        config = config_with(belief__smell_trust=9.0)

        belief = BeliefGrid.from_config(terms_from_config(config), config)

        assert len(belief.as_matrix()) == 7
        assert belief._smell_trust == 9.0

    def test_an_unset_trust_falls_back_to_the_shipped_default(self, config):
        belief = BeliefGrid.from_config(terms_from_config(config), config)

        assert belief._smell_trust == 4.0

    def test_power_and_leak_also_default_to_the_shipped_values(self, config):
        belief = BeliefGrid.from_config(terms_from_config(config), config)

        assert belief._smell_power == 3.0
        assert belief._leak == 0.03

    def test_power_and_leak_are_overridable_from_the_private_file(self):
        config = config_with(belief__smell_power=3.0, belief__leak=0.1)

        belief = BeliefGrid.from_config(terms_from_config(config), config)

        assert belief._smell_power == 3.0
        assert belief._leak == 0.1

    def test_stale_decay_and_support_also_default_to_the_shipped_values(self, config):
        belief = BeliefGrid.from_config(terms_from_config(config), config)

        assert belief._stale_decay == 0.85
        assert belief._stale_support == 0.1

    def test_stale_decay_and_support_are_overridable_from_the_private_file(self):
        config = config_with(belief__stale_decay=0.5, belief__stale_support=0.2)

        belief = BeliefGrid.from_config(terms_from_config(config), config)

        assert belief._stale_decay == 0.5
        assert belief._stale_support == 0.2
