"""The jump-to-step box: the spinbox is editable, so it really can hold anything."""

from police_agent.gui.replay_controls import as_step


def test_a_typed_number_is_the_step():
    assert as_step("12") == 12


def test_anything_unreadable_falls_back_to_the_first_step():
    """Refusing to parse is not an error worth interrupting a replay for."""
    for typed in ("", "  ", "seven", "3.5", None):
        assert as_step(typed) == 1
