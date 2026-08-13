"""Outbound calls to the sibling Thief process's own coordinator.

Mirrors `infra/mcp_client.py`'s connect-call-disconnect shape and its
"retry until the deadline, because two independently started processes
never begin at the same instant" reasoning -- except the peer here is our
own team's sibling process on `127.0.0.1`, not the opponent. Every outbound
message is signed via `security.py` before it leaves.
"""

import asyncio
import time

from fastmcp import Client

from police_agent.exceptions import TransportError
from police_agent.team_sync import messages, security


class TeamSyncClient:
    """One peer's view of the local team_sync link: push to the sibling's URL."""

    def __init__(
        self,
        sibling_url: str,
        secret: str | None,
        connect_timeout: float = 30.0,
        retry_interval: float = 1.0,
        call_timeout: float = 10.0,
    ) -> None:
        """Store the sibling's URL, the shared secret, and this link's timeouts."""
        self._url = sibling_url
        self._secret = secret
        self._connect_timeout = connect_timeout
        self._retry_interval = retry_interval
        self._call_timeout = call_timeout

    def _call(self, tool: str, message: dict) -> dict:
        """One MCP call: connect, invoke, disconnect -- a fresh session each time."""
        signed = security.sign_message(message, self._secret)

        async def invoke() -> dict:
            async with Client(
                self._url, timeout=self._call_timeout, init_timeout=self._call_timeout
            ) as client:
                result = await client.call_tool(tool, {"message": signed})
                return result.data if result.data is not None else {}

        return asyncio.run(invoke())

    def _send_with_retry(self, tool: str, message: dict) -> dict:
        """Retry a transient failure until the sibling answers or the connect
        deadline passes. An authenticated rejection (`ok: False`) is never
        transient -- the same bad secret will fail again -- so it raises
        immediately instead of burning the retry budget silently."""
        deadline = time.monotonic() + self._connect_timeout
        while True:
            try:
                response = self._call(tool, message)
            except Exception as exc:
                if time.monotonic() >= deadline:
                    raise TransportError(
                        f"Sibling team_sync coordinator unreachable at {self._url}: {exc}"
                    ) from exc
                time.sleep(self._retry_interval)
                continue
            if response.get("ok") is False:
                raise TransportError(
                    f"Sibling rejected {tool!r}: {response.get('error', 'unknown reason')} -- "
                    f"check that TEAM_SYNC_SECRET matches on both sibling processes"
                )
            return response

    def send_series_start(
        self, series_id: str, game_id: str, num_sub_games: int, first_sibling_subgame: int
    ) -> dict:
        """Announce a new series to the sibling Thief process.

        `first_sibling_subgame` is the earliest sub-game number the sibling
        owns (normally 2) -- the series-owner's equivalent of a handoff,
        since nothing else unlocks the sibling's very first sub-game.
        """
        message = messages.SeriesStart(
            series_id=series_id,
            game_id=game_id,
            num_sub_games=num_sub_games,
            sub_game_number=first_sibling_subgame,
            sender_role="police",
        ).to_dict()
        return self._send_with_retry(messages.SERIES_START, message)

    def send_handoff(self, series_id: str, completed_subgame: int, next_subgame: int) -> dict:
        """Tell the sibling one sub-game settled and the next one is unlocked."""
        message = messages.SubgameHandoff(
            series_id=series_id,
            completed_subgame=completed_subgame,
            next_subgame=next_subgame,
            sub_game_number=next_subgame,
            sender_role="police",
        ).to_dict()
        return self._send_with_retry(messages.HANDOFF, message)

    def send_status_request(self, series_id: str) -> dict:
        """Ask the sibling where it currently stands (a resync after a restart)."""
        message = messages.StatusRequest(series_id=series_id, sender_role="police").to_dict()
        return self._send_with_retry(messages.STATUS_REQUEST, message)

    def send_ack(self, series_id: str, ack_for_message_id: str, sub_game_number: int) -> dict:
        """Acknowledge the sibling's settled `subgame_result`."""
        message = messages.Ack(
            series_id=series_id,
            ack_for_message_id=ack_for_message_id,
            sub_game_number=sub_game_number,
            sender_role="police",
        ).to_dict()
        return self._send_with_retry(messages.ACK, message)
