"""What the police actually broadcasts once the scent field is wired in.

The unit tests prove the field computes the right numbers; these prove the turn
loop is really carrying them, which is the part that was a no-op until now.
"""

from police_agent.peer.runtime import PoliceRuntime
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turns


def sent_grids(turns: int) -> list[dict]:
    """Play a short sub-game and return the scent grid from each turn sent."""
    transport = FakeTransport(incoming=thief_turns(turns))
    PoliceRuntime(config_with(), transport).run()
    return [message["smell_grid"] for message in transport.sent_turns]


def test_the_police_no_longer_broadcasts_an_empty_grid():
    assert all(grid for grid in sent_grids(3))


def test_the_broadcast_is_a_field_and_not_a_single_cell():
    """A point mass would name the police's exact position (Appendix He, 27)."""
    for grid in sent_grids(3):
        assert len(grid) > 1


def test_the_freshest_deposit_leads_at_the_agreed_strength():
    for grid in sent_grids(3):
        assert max(grid.values()) == 0.9  # the fixed centre intensity, undecayed


def test_the_trail_fades_behind_the_police():
    first, second = sent_grids(2)

    assert any(second[cell] < first[cell] for cell in first if cell in second)
