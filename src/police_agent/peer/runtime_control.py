"""Bidirectional-control integration for the turn loop, kept out of runtime.py.

`pump` enables on request, drains inbound control, and broadcasts this peer's
live status; `check` turns control intents into game effects. Quit and an
opponent's quit abandon the sub-game the same way the existing Stop button
already does. A restart -- locally requested, or peer-requested and already
approved -- raises `RestartRequested` for the GUI to catch: it is the one
signal that unwinds the whole call stack rather than just setting a result,
because restarting means tearing down this runtime and building a fresh one,
not merely ending this one.
"""

from police_agent.domain.rules import ABORTED
from police_agent.exceptions import RestartRequested
from police_agent.peer.control_link import (
    GAME_OVER,
    PAUSED,
    PLAYING,
    QUIT,
    STOPPED,
    THINKING,
    WAITING,
)

__all__ = ["pump", "check", "GAME_OVER", "PLAYING", "THINKING", "WAITING"]


def _status_for(runtime, base: str) -> str:
    controls = runtime.controls
    if controls.quit_requested:
        return QUIT
    if controls.stopped:
        return STOPPED
    if controls.paused:
        return PAUSED
    return base


def pump(runtime, base: str) -> None:
    """Enable on request, process inbound control, and broadcast my status."""
    if runtime.controls.enable_requested and not runtime.link.i_enabled:
        runtime.link.enable()
    runtime.link.drain()
    runtime.link.broadcast_status(_status_for(runtime, base), 1)


def check(runtime) -> None:
    """React to control intents. Raises RestartRequested to rebuild the match."""
    if runtime.controls.quit_requested:
        runtime.link.send_quit()
        runtime._result = (ABORTED, None)
        return
    if runtime.link.opponent_quit:
        runtime._result = (ABORTED, None)
        return
    if runtime.controls.restart_requested:  # locally initiated
        runtime.controls.clear_restart()
        runtime.link.send_restart()
        raise RestartRequested()
    if runtime.link.take_pending_restart():  # peer-initiated, already approved
        raise RestartRequested()
