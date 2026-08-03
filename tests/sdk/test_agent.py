"""The SDK facade: settings resolution, wiring, and one match played through it."""

import json

import pytest

from police_agent.constants import Role
from police_agent.domain.rules import ABORTED
from police_agent.exceptions import ConfigError
from police_agent.infra.tunnel import NgrokTunnel
from police_agent.peer.controls import GameControls
from police_agent.sdk import MatchOptions, PoliceAgentSDK
from tests.conftest import CONFIG_DIR, config_with
from tests.peer.fake_transport import FakeTransport, thief_turn

NETWORKED = {"network__my_port": 8801, "network__opponent_url": "http://127.0.0.1:8802/mcp"}
UNWIRED = object()  # distinguishes "no transport given" from "inject None"


def agent_with(transport=UNWIRED, listener=None, options=None, **overrides) -> PoliceAgentSDK:
    """An SDK on the agreed terms, wired to a test double instead of a socket."""
    return PoliceAgentSDK(
        options,
        config=config_with(**{**NETWORKED, **overrides}),
        transport=FakeTransport() if transport is UNWIRED else transport,
        listener=listener,
    )


def test_the_settings_come_from_the_config_when_nothing_overrides_them():
    agent = agent_with()

    assert (agent.host, agent.port) == ("127.0.0.1", 8801)
    assert agent.opponent_url == "http://127.0.0.1:8802/mcp"


def test_the_caller_may_override_the_port_and_the_opponent():
    """Two peers on one machine is the development case; without overrides both
    would read the same private config and try to bind the same port."""
    options = MatchOptions(host="0.0.0.0", port=9001, opponent_url="http://elsewhere/mcp")

    agent = agent_with(options=options)

    assert (agent.host, agent.port) == ("0.0.0.0", 9001)
    assert agent.opponent_url == "http://elsewhere/mcp"


def test_a_missing_port_is_reported_by_name():
    agent = PoliceAgentSDK(config=config_with(), transport=FakeTransport())

    with pytest.raises(ConfigError, match="network.my_port"):
        _ = agent.port


def test_a_missing_opponent_url_is_reported_by_name():
    agent = PoliceAgentSDK(config=config_with(), transport=FakeTransport())

    with pytest.raises(ConfigError, match="network.opponent_url"):
        _ = agent.opponent_url


def test_the_config_is_loaded_from_the_options_directory_when_none_is_given():
    agent = PoliceAgentSDK(MatchOptions(config_dir=CONFIG_DIR))

    assert agent.config.require("board.size") == 7


def test_an_injected_transport_is_never_replaced_by_a_socket(monkeypatch):
    """The seam that keeps the whole loop testable: if `connect` could reach past
    an injected double, every SDK test would need a live port."""
    monkeypatch.setattr("police_agent.sdk.agent.start_peer_server", _forbidden("started a server"))
    double = FakeTransport()

    agent = agent_with(transport=double)

    assert agent.connect() is double


def test_connect_opens_this_peers_mailbox_and_dials_the_opponent(monkeypatch):
    opened, dialled = _record_wiring(monkeypatch)

    transport = agent_with(transport=None).connect()

    assert opened == [(Role.POLICE, "127.0.0.1", 8801)]
    assert dialled[0][0] == "http://127.0.0.1:8802/mcp"
    assert transport is dialled[0][2]


def test_the_wire_deadlines_come_from_the_agreed_terms():
    """Both peers read them from the byte-identical game.json, so the two sides
    wait the same length of time; a number frozen into the code would not."""
    agent = agent_with(network__watchdog_timeout_seconds=90, network__response_timeout_seconds=45)

    assert agent.transport_timeouts() == {"connect_timeout": 90.0, "reply_timeout": 45.0}


def test_the_deadlines_fall_back_when_the_terms_name_neither():
    """The shipped game.json names both, so these numbers should never decide a
    match -- but a partial file must not leave the transport with a None budget."""
    agent = agent_with(
        network__watchdog_timeout_seconds=None, network__response_timeout_seconds=None
    )

    assert agent.transport_timeouts() == {"connect_timeout": 60.0, "reply_timeout": 30.0}


def test_connecting_twice_opens_one_server(monkeypatch):
    """The second bind would fail on the port the first is holding."""
    opened, _ = _record_wiring(monkeypatch)
    agent = agent_with(transport=None)

    assert agent.connect() is agent.connect()
    assert len(opened) == 1


def test_a_default_run_has_no_public_address_at_all(monkeypatch):
    _record_wiring(monkeypatch)
    agent = agent_with(transport=None)

    agent.connect()

    assert agent.public_url is None


def test_the_tunnel_publishes_my_port_on_my_reserved_domain(monkeypatch):
    """The domain is private, so it comes from game.toml: no opponent verifies it."""
    _record_wiring(monkeypatch)
    asked: list = []

    def open_tunnel(port, domain=None):
        asked.append((port, domain))
        return NgrokTunnel(f"https://{domain}")

    monkeypatch.setattr("police_agent.sdk.agent.open_tunnel", open_tunnel)
    options = MatchOptions(tunnel=True)
    agent = agent_with(transport=None, options=options, network__tunnel_domain="cops.ngrok.app")

    agent.connect()

    assert asked == [(8801, "cops.ngrok.app")]
    assert agent.public_url == "https://cops.ngrok.app/mcp"  # the /mcp mount, not the origin


def test_the_runtime_is_the_match_and_is_not_rebuilt():
    agent = agent_with()

    assert agent.runtime is agent.runtime


def test_play_returns_the_match_summary():
    agent = agent_with(transport=FakeTransport(incoming=[thief_turn(1)]))

    summary = agent.play()

    assert summary["role"] == "police"
    assert summary["steps"] == 1


def test_a_listener_sees_the_game_end():
    events: list[dict] = []

    agent_with(transport=FakeTransport(incoming=[thief_turn(1)]), listener=events.append).play()

    assert [event["type"] for event in events][-1] == "game_over"


def test_save_summary_writes_the_whole_record(tmp_path):
    """The report and the replay viewer are both rebuilt from this file, so a
    record trimmed to the headline result would not support either."""
    agent = agent_with(transport=FakeTransport(incoming=[thief_turn(1)]))
    summary = agent.play()

    path = agent.save_summary(summary, tmp_path / "result.json")

    assert json.loads(path.read_text(encoding="utf-8")) == summary


def test_a_saved_record_reads_back_for_the_replay_player(tmp_path):
    agent = agent_with(transport=FakeTransport(incoming=[thief_turn(1)]))
    path = agent.save_summary(agent.play(), tmp_path / "result.json")

    assert agent.load_summary(path)["role"] == "police"


def test_a_missing_log_names_the_file_rather_than_raising_an_os_error():
    agent = agent_with()

    with pytest.raises(ConfigError, match="Match log not found"):
        agent.load_summary("nowhere/result.json")


def test_a_log_that_is_not_json_says_so(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ConfigError, match="not valid JSON"):
        agent_with().load_summary(path)


def test_controls_reach_the_runtime_so_the_windows_buttons_are_real():
    """The GUI cannot pass these at construction -- it needs an SDK to build its
    window from before it has a window to steer with -- so they are settable."""
    controls = GameControls()
    controls.stop()
    agent = agent_with(transport=FakeTransport(incoming=[thief_turn(1)]))
    agent.controls = controls

    assert agent.play()["result"] == ABORTED


def _forbidden(what: str):
    def fail(*args, **kwargs):
        raise AssertionError(what)

    return fail


def _record_wiring(monkeypatch) -> tuple[list, list]:
    """Replace the socket-touching constructors with recorders, and ban ngrok."""
    opened: list = []
    dialled: list = []

    def start(role, host, port):
        opened.append((role, host, port))
        return "inboxes"

    def transport(url, inboxes, **timeouts):
        dialled.append((url, inboxes, FakeTransport(), timeouts))
        return dialled[-1][2]

    monkeypatch.setattr("police_agent.sdk.agent.start_peer_server", start)
    monkeypatch.setattr("police_agent.sdk.agent.McpTransport", transport)
    # Tunnelling is opt-in, so every test using this helper also proves that a
    # default run starts no child process and publishes nothing to the internet.
    monkeypatch.setattr("police_agent.sdk.agent.open_tunnel", _forbidden("started ngrok"))
    return opened, dialled
