"""Opening an ngrok tunnel, with nothing installed and no packet leaving the machine.

One branch here is a tunnel coming up; every other is a way a league match
cannot be played at all (Appendix He rule 10), so ngrok is faked whole -- the
binary, the child process, the agent API -- rather than its failure paths being
left to a manual check nobody performs on the morning of a match.

Error paths live in `test_tunnel_errors.py`; closing and the bare agent-API
helpers live in `test_tunnel_lifecycle.py` -- split out to keep each file
under the project's line budget, sharing `fake_ngrok.py`'s `FakeNgrok`.
"""

from police_agent.infra.tunnel import open_tunnel
from tests.infra.fake_ngrok import DOMAIN, PUBLIC, FakeNgrok, published


def test_the_public_address_comes_from_ngroks_own_agent_api(monkeypatch):
    # And it is the /mcp endpoint, not the bare origin, that is any use to them.
    FakeNgrok(monkeypatch, published(8801, PUBLIC))

    opened = open_tunnel(8801)

    assert (opened.public_url, opened.mcp_url) == (PUBLIC, f"{PUBLIC}/mcp")


def test_the_command_line_asks_for_the_reserved_domain_and_carries_no_secret(monkeypatch):
    """The token lives in ngrok's own config and nowhere near this repository."""
    ngrok = FakeNgrok(monkeypatch, published(8801, PUBLIC))

    open_tunnel(8801, DOMAIN)

    assert f"--domain={DOMAIN}" in ngrok.commands[0]
    assert not [arg for arg in ngrok.commands[0] if "token" in arg.lower()]


def test_ngrok_picks_the_address_when_no_domain_is_reserved(monkeypatch):
    """The ephemeral case: it plays, but on a different URL after every restart."""
    ngrok = FakeNgrok(monkeypatch, published(8801, "https://a1b2.ngrok-free.app"))

    assert open_tunnel(8801).public_url == "https://a1b2.ngrok-free.app"
    assert not [arg for arg in ngrok.commands[0] if arg.startswith("--domain")]


def test_it_keeps_polling_until_the_tunnel_is_really_published(monkeypatch):
    # The agent API answers long before it has anything to forward.
    FakeNgrok(monkeypatch, published(8801, PUBLIC)).publish_after = 3

    assert open_tunnel(8801).public_url == PUBLIC


def test_a_tunnel_already_on_my_port_is_adopted_rather_than_duplicated(monkeypatch):
    """A second agent would only fight the first for the domain and the 4040 API.

    The https URL wins: ngrok may publish both schemes for one forwarded port.
    """
    published_both = published(8801, "http://insecure.example", PUBLIC)
    ngrok = FakeNgrok(monkeypatch, published_both, already_up=True)

    adopted = open_tunnel(8801, DOMAIN)
    adopted.close()  # closing must not kill a tunnel we did not start

    assert (adopted.public_url, ngrok.commands, ngrok.processes) == (PUBLIC, [], [])


def test_a_tunnel_forwarding_to_another_port_is_not_mine(monkeypatch):
    # The development case: the thief's tunnel is up, and is no use to me.
    ngrok = FakeNgrok(monkeypatch, published(8801, PUBLIC))
    ngrok.reported = published(8802, "https://thief.example")

    assert open_tunnel(8801).public_url == PUBLIC
    assert len(ngrok.commands) == 1
