"""ControlLink: the enable-handshake and status/restart/quit signalling."""

from police_agent.peer.control_link import QUIT, ControlLink
from police_agent.peer.controls import GameControls
from tests.peer.fake_transport import FakeTransport


def link(**overrides) -> ControlLink:
    controls = overrides.pop("controls", None) or GameControls()
    transport = overrides.pop("transport", None) or FakeTransport()
    return ControlLink("police", transport, controls, **overrides)


class TestEnable:
    def test_starts_inactive_on_both_sides(self):
        assert not link().active

    def test_enabling_locally_is_not_enough_alone(self):
        control_link = link()
        control_link.enable()
        assert control_link.i_enabled
        assert not control_link.active

    def test_enabling_announces_it_on_the_wire(self):
        transport = FakeTransport()
        control_link = link(transport=transport)
        control_link.enable()
        assert transport.sent_controls == [
            {
                "kind": "enable",
                "sender": "police",
                "sub_game_number": 1,
                "status": "",
                "payload": None,
            }
        ]

    def test_becomes_active_once_the_peer_also_enables(self):
        transport = FakeTransport(incoming_controls=[{"kind": "enable", "sender": "thief"}])
        control_link = link(transport=transport)
        control_link.enable()
        control_link.drain()
        assert control_link.active


class TestStatus:
    def test_broadcasts_nothing_before_i_enable(self):
        transport = FakeTransport()
        link(transport=transport).broadcast_status("THINKING", 1)
        assert transport.sent_controls == []

    def test_broadcasts_once_enabled(self):
        transport = FakeTransport()
        control_link = link(transport=transport)
        control_link.enable()
        transport.sent_controls.clear()
        control_link.broadcast_status("THINKING", 1)
        assert transport.sent_controls[0]["kind"] == "status"
        assert transport.sent_controls[0]["status"] == "THINKING"

    def test_never_repeats_the_same_status(self):
        transport = FakeTransport()
        control_link = link(transport=transport)
        control_link.enable()
        transport.sent_controls.clear()
        control_link.broadcast_status("THINKING", 1)
        control_link.broadcast_status("THINKING", 1)
        assert len(transport.sent_controls) == 1

    def test_records_the_opponents_broadcast_status(self):
        transport = FakeTransport(
            incoming_controls=[
                {"kind": "status", "sender": "thief", "status": "PLAYING", "sub_game_number": 1}
            ]
        )
        control_link = link(transport=transport)
        control_link.drain()
        assert control_link.opponent["status"] == "PLAYING"


class TestRestart:
    def test_a_restart_from_an_inactive_peer_is_not_granted(self):
        transport = FakeTransport(incoming_controls=[{"kind": "restart", "sender": "thief"}])
        control_link = link(transport=transport)
        control_link.drain()
        assert not control_link.take_pending_restart()

    def test_a_restart_once_both_sides_are_active_is_auto_approved(self):
        transport = FakeTransport(
            incoming_controls=[
                {"kind": "enable", "sender": "thief"},
                {"kind": "restart", "sender": "thief"},
            ]
        )
        control_link = link(transport=transport)
        control_link.enable()
        control_link.drain()
        assert control_link.take_pending_restart()

    def test_take_pending_restart_is_a_one_shot_consume(self):
        transport = FakeTransport(
            incoming_controls=[
                {"kind": "enable", "sender": "thief"},
                {"kind": "restart", "sender": "thief"},
            ]
        )
        control_link = link(transport=transport)
        control_link.enable()
        control_link.drain()
        control_link.take_pending_restart()
        assert not control_link.take_pending_restart()

    def test_send_restart_reaches_the_wire(self):
        transport = FakeTransport()
        link(transport=transport).send_restart()
        assert transport.sent_controls[0]["kind"] == "restart"


class TestQuit:
    def test_an_opponent_quit_is_recorded(self):
        transport = FakeTransport(incoming_controls=[{"kind": "quit", "sender": "thief"}])
        control_link = link(transport=transport)
        control_link.drain()
        assert control_link.opponent_quit
        assert control_link.opponent["status"] == QUIT

    def test_send_quit_reaches_the_wire(self):
        transport = FakeTransport()
        link(transport=transport).send_quit()
        assert transport.sent_controls[0]["kind"] == "quit"


class TestUnknownAndTolerance:
    def test_an_unknown_kind_does_not_raise(self):
        transport = FakeTransport(
            incoming_controls=[{"kind": "flibbertigibbet", "sender": "thief"}]
        )
        link(transport=transport).drain()  # must not raise

    def test_a_transport_without_control_methods_is_silently_skipped(self):
        class BareTransport:
            pass

        control_link = link(transport=BareTransport())
        assert control_link.drain() == []
        control_link.enable()  # must not raise despite no send_control
