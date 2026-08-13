"""HMAC sign/verify: the shared-secret half of team_sync's defense-in-depth."""

from police_agent.team_sync import security


def test_a_message_signed_with_the_right_secret_verifies():
    message = {"series_id": "s1", "sub_game_number": 1}

    signed = security.sign_message(message, "shared-secret")

    assert signed["hmac"]
    assert security.verify_message(signed, "shared-secret") is True


def test_a_message_signed_with_the_wrong_secret_is_rejected():
    signed = security.sign_message({"series_id": "s1"}, "shared-secret")

    assert security.verify_message(signed, "a-different-secret") is False


def test_a_corrupted_signature_is_rejected():
    signed = security.sign_message({"series_id": "s1"}, "shared-secret")
    signed["hmac"] = signed["hmac"][:-1] + ("0" if signed["hmac"][-1] != "0" else "1")

    assert security.verify_message(signed, "shared-secret") is False


def test_tampering_with_the_body_after_signing_is_rejected():
    signed = security.sign_message({"series_id": "s1", "sub_game_number": 1}, "shared-secret")
    signed["sub_game_number"] = 2

    assert security.verify_message(signed, "shared-secret") is False


def test_no_secret_configured_disables_auth_rather_than_crashing():
    """Local dev / the test suite must work with no `TEAM_SYNC_SECRET` set."""
    signed = security.sign_message({"series_id": "s1"}, None)

    assert signed["hmac"] == ""
    assert security.verify_message(signed, None) is True


def test_secret_from_env_reads_the_documented_variable(monkeypatch):
    monkeypatch.setenv(security.ENV_VAR, "abc")
    assert security.secret_from_env() == "abc"

    monkeypatch.delenv(security.ENV_VAR, raising=False)
    assert security.secret_from_env() is None


def test_a_non_dict_message_never_verifies():
    assert security.verify_message("not-a-dict", "shared-secret") is False
