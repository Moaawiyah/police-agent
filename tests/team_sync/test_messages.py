"""The control envelopes: unique message ids, and a stable wire shape."""

from police_agent.team_sync import messages


def test_series_start_round_trips_through_to_dict():
    msg = messages.SeriesStart(
        series_id="s1", game_id="A-vs-B", num_sub_games=6, sub_game_number=2, sender_role="police"
    ).to_dict()

    assert msg["type"] == messages.SERIES_START
    assert msg["schema_version"] == messages.SCHEMA_VERSION
    assert msg["series_id"] == "s1"
    assert msg["sub_game_number"] == 2  # the sibling's `wait_for_unlock` keys on this
    assert msg["hmac"] == ""


def test_each_message_gets_its_own_message_id():
    first = messages.SeriesStart(
        series_id="s1", game_id="g", num_sub_games=6, sub_game_number=2, sender_role="police"
    )
    second = messages.SeriesStart(
        series_id="s1", game_id="g", num_sub_games=6, sub_game_number=2, sender_role="police"
    )

    assert first.message_id != second.message_id


def test_handoff_carries_the_completed_and_next_subgame_numbers():
    msg = messages.SubgameHandoff(
        series_id="s1",
        completed_subgame=1,
        next_subgame=2,
        sub_game_number=2,
        sender_role="police",
    ).to_dict()

    assert (msg["completed_subgame"], msg["next_subgame"]) == (1, 2)
    assert msg["sub_game_number"] == 2  # the sibling's `wait_for_unlock` keys on this
    assert msg["type"] == messages.HANDOFF


def test_status_response_names_the_state_and_current_subgame():
    msg = messages.StatusResponse(
        series_id="s1", state="playing", current_subgame=3, sender_role="police"
    ).to_dict()

    assert (msg["state"], msg["current_subgame"]) == ("playing", 3)


def test_ack_names_the_message_it_acknowledges():
    msg = messages.Ack(
        series_id="s1", ack_for_message_id="abc123", sub_game_number=2, sender_role="police"
    ).to_dict()

    assert msg["ack_for_message_id"] == "abc123"


def test_status_request_carries_just_the_series_and_sender():
    msg = messages.StatusRequest(series_id="s1", sender_role="thief").to_dict()

    assert msg["type"] == messages.STATUS_REQUEST
    assert msg["sender_role"] == "thief"
