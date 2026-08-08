"""Play the whole agreed series of sub-games over one held connection.

`game.num_games` (1-6, Appendix F) is a signed term both peers already agree
on at the handshake; this is what actually plays it out. The transport (and
the MCP server bound to it) is built once by the caller and never torn down
between sub-games -- only the per-game state is new each time, via a fresh
`PoliceRuntime`. `GameControls` is shared across every sub-game so a pause,
stop, or bidirectional-enable made from the GUI survives into the next one.
"""

from police_agent.exceptions import ConfigError
from police_agent.peer.controls import GameControls
from police_agent.peer.runtime import PoliceRuntime

__all__ = ["series_count", "run_series"]


def series_count(config) -> int:
    """The agreed number of sub-games, validated the way the reference does."""
    value = config.get("game.num_games", 1)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 6:
        raise ConfigError("game.num_games must be an integer from 1 through 6")
    return value


def run_series(
    config,
    transport,
    brain=None,
    threat=None,
    scent=None,
    hint_writer=None,
    analyst=None,
    listener=None,
    controls=None,
    league: bool = False,
) -> list[dict]:
    """Play every sub-game of the agreed series in order and return each summary.

    A restart requested mid-sub-game (`RestartRequested`) is not caught here:
    it unwinds the whole series back to the caller, which is the same signal
    the GUI already rebuilds a fresh run from -- there is no narrower "just
    this sub-game" restart yet, only "the whole series, from sub-game one."
    """
    controls = controls or GameControls()
    summaries: list[dict] = []
    for sub_game_number in range(1, series_count(config) + 1):
        runtime = PoliceRuntime(
            config,
            transport,
            brain=brain,
            threat=threat,
            scent=scent,
            hint_writer=hint_writer,
            analyst=analyst,
            listener=listener,
            controls=controls,
            league=league,
            sub_game_number=sub_game_number,
        )
        summaries.append(runtime.run())
    return summaries
