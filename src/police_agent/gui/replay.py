"""The Visual Replay Player facade and its saved-log state."""

from police_agent.gui import replay_actions
from police_agent.gui.replay_controls import build_controls
from police_agent.gui.replay_data import normalize_log, opponent_positions
from police_agent.gui.window import PeerWindow
from police_agent.strategy.belief import DEFAULT_SMELL_TRUST, BeliefGrid

DEFAULT_STEP_SECONDS = 0.5


class ReplayApp:
    """Hold replay state and delegate playback actions to the small action module."""

    def __init__(self, config, log_data: dict, opponent_log: dict | None = None, window=None):
        self._size = int(config.require("board.size"))
        self._trust = float(config.get("belief.smell_trust", DEFAULT_SMELL_TRUST))
        view = normalize_log(log_data)
        self._records, self._history = view["records"], view["history"]
        self._my_log, self._role = view["my_log"], view["role"]
        self._result, self._winner = view["result"], view["winner"]
        self._audit = view["audit"]
        self._opponent = opponent_positions(opponent_log)
        self._playing = False
        self._reset_state()
        self._window = window or self._open_window(config, view)
        self._window.add_menu({"log_role": self._role, "result": self._result})
        reliability = view["reliability"]
        self._window.set_label("reliability", "-" if reliability is None else f"{reliability:.2f}")

    def _open_window(self, config, view: dict) -> PeerWindow:
        window = PeerWindow(
            f"REPLAY - {view['group']} - {self._role} - {view['duration_seconds']}s",
            self._size,
            float(config.get("gui.step_seconds", DEFAULT_STEP_SECONDS)),
        )
        build_controls(self, window.root)
        return window

    def _reset_state(self) -> None:
        self._belief = BeliefGrid(self._size, self._trust)
        self._barriers: set = set()
        self._visited: set = set()
        self._index = 0

    def _total_steps(self) -> int:
        return max(len(self._my_log), len(self._history), len(self._opponent))

    def advance(self) -> None:
        replay_actions.advance(self)

    def _apply_my_step(self, index: int) -> None:
        replay_actions.apply_my_step(self, index)

    def _apply_opponent_step(self, index: int) -> None:
        replay_actions.apply_opponent_step(self, index)

    def _render(self, index: int, total: int) -> None:
        replay_actions.render(self, index, total)

    def restart(self) -> None:
        replay_actions.restart(self)

    def _render_empty(self) -> None:
        replay_actions.render_empty(self)

    def goto(self, step: int) -> None:
        replay_actions.goto(self, step)

    def toggle(self) -> None:
        replay_actions.toggle(self)

    def _tick(self) -> None:
        replay_actions.tick(self)

    def run(self) -> None:
        replay_actions.run(self)
